"""文件索引模块.

该模块实现了工作区文件树索引和 @file 引用解析功能。
支持递归生成目录树、解析文本中的文件引用并返回文件内容摘要。
"""

import os
import re
from typing import List

from common.constant import (
    FILE_TREE_MAX_DEPTH,
    FILE_TREE_MAX_LINES,
    FILE_REF_TRUNCATE_LENGTH,
    IGNORED_DIRS,
    IGNORED_FILE_PREFIX
)


def get_file_tree(
    root_dir: str = ".",
    max_depth: int = FILE_TREE_MAX_DEPTH,
    max_lines: int = FILE_TREE_MAX_LINES
) -> str:
    """递归生成目录树字符串，包含文件路径和文件名.

    Args:
        root_dir: 根目录路径 (默认当前目录)
        max_depth: 最大递归深度 (默认 FILE_TREE_MAX_DEPTH)
        max_lines: 最大行数限制 (默认 FILE_TREE_MAX_LINES)

    Returns:
        目录树字符串，每个目录或文件占一行，包含相对路径
    """
    tree_lines = []

    def _walk(path: str, depth: int, prefix: str = ""):
        """递归遍历目录.

        Args:
            path: 当前遍历的路径
            depth: 当前深度
            prefix: 前缀字符串，用于树形显示
        """
        if len(tree_lines) >= max_lines:
            return

        if depth > max_depth:
            return

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return

        entries = [
            e for e in entries
            if not e.startswith(IGNORED_FILE_PREFIX)
            and e not in IGNORED_DIRS
        ]

        for i, entry in enumerate(entries):
            if len(tree_lines) >= max_lines:
                tree_lines.append(
                    f"{prefix}... [Truncated, total files > {max_lines}]"
                )
                return

            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            full_path = os.path.join(path, entry)

            tree_lines.append(f"{prefix}{connector}{entry}")

            if os.path.isdir(full_path):
                extension = "    " if is_last else "│   "
                _walk(full_path, depth + 1, prefix + extension)

    tree_lines.append(os.path.abspath(root_dir))
    _walk(root_dir, 0)
    return "\n".join(tree_lines)


def resolve_file_ref(text: str, root_dir: str = ".") -> List[str]:
    """解析文本中的 @file 引用，返回文件内容摘要.

    格式: @filename

    Args:
        text: 包含 @file 引用的文本
        root_dir: 根目录路径，用于解析相对路径引用 (默认当前目录)

    Returns:
        包含文件内容摘要的列表，每个元素格式为：
        "File Reference 'filename':\ncontent_summary"
    """
    refs = re.findall(r"@([\w\.\-/]+)", text)
    results = []

    for filename in refs:
        path = os.path.join(root_dir, filename)
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > FILE_REF_TRUNCATE_LENGTH:
                    summary = content[:FILE_REF_TRUNCATE_LENGTH] + "\n...[Truncated]"
                else:
                    summary = content
                results.append(f"File Reference '{filename}':\n{summary}")
            except Exception:
                pass

    return results
