"""知识管理器模块.

集成向量数据库，提供知识的添加、检索、索引等功能。
"""

import hashlib
import re
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path

from common.config import config
from knowledge.vector_db import VectorDatabase, KnowledgeEntry


class KnowledgeManager:
    """知识管理器.

    提供知识的索引、存储和检索功能。
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        auto_sync_paths: Optional[List[str]] = None
    ):
        """初始化知识管理器.

        Args:
            storage_dir: 向量数据库存储目录
        """
        self.storage_dir = storage_dir or config.get_vector_db_dir()
        self.vector_db = VectorDatabase(self.storage_dir)
        self.default_knowledge_dir = Path(__file__).resolve().parent / "library"
        if auto_sync_paths is None:
            auto_sync_paths = [str(self.default_knowledge_dir)]
        self.auto_sync_paths = [Path(path).resolve() for path in auto_sync_paths]
        self.chunk_size = 220
        self.chunk_overlap = 40

    @staticmethod
    def _extract_query_terms(query: str) -> List[str]:
        """从查询中提取有效关键词.

        使用正则表达式匹配英文标识符和中文字词，过滤停用词。

        Args:
            query: 查询文本

        Returns:
            有效关键词列表
        """
        raw_terms = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]{2,}", query)
        stop_words = {
            "python", "什么", "什么意思", "什么是", "如何", "怎么", "请问",
            "一下", "介绍", "以及", "这个", "那个", "一个", "一些", "做什么的"
        }
        normalized = []
        seen = set()
        for term in raw_terms:
            key = term.lower()
            if key in stop_words or term in stop_words:
                continue
            if key in seen:
                continue
            seen.add(key)
            normalized.append(term)
        return normalized

    @staticmethod
    def _text_overlap_score(text: str, query_terms: List[str]) -> float:
        """计算文本与查询词的重叠分数.

        统计查询词在文本中的出现次数，每个词的贡献最多为1.0。

        Args:
            text: 待评估的文本
            query_terms: 查询关键词列表

        Returns:
            重叠分数，范围 [0, ∞)
        """
        if not text or not query_terms:
            return 0.0
        lowered = text.lower()
        score = 0.0
        for term in query_terms:
            if term.lower() in lowered:
                score += min(len(term), 12) / 12
        return score

    @staticmethod
    def _estimate_code_ratio(text: str) -> float:
        """估算文本中的代码占比.

        通过识别代码特征（如关键字、括号、代码块标记等）来估算代码比例。

        Args:
            text: 待分析的文本

        Returns:
            代码占比，范围 [0.0, 1.0]
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return 0.0
        code_like = 0
        for line in lines:
            if (
                line.startswith(("def ", "class ", "return ", "import ", "from ", "if ", "for ", "while "))
                or line.endswith((":", "{", "}", ")"))
                or "```" in line
                or "=" in line
            ):
                code_like += 1
        return code_like / len(lines)

    def _score_parent_result(self, query_terms: List[str], entry: KnowledgeEntry, score: float) -> float:
        """对父级章节结果做重排评分.

        基于标题、路径和内容的词重叠度调整原始相似度分数，并对目录等内容进行惩罚。

        Args:
            query_terms: 查询关键词列表
            entry: 知识条目（章节类型）
            score: 原始相似度分数

        Returns:
            调整后的重排分数
        """
        metadata = entry.metadata or {}
        heading_path = metadata.get("heading_path", "")
        section_title = metadata.get("section_title", "")
        text = entry.content[:800]
        heading_score = self._text_overlap_score(section_title, query_terms)
        path_score = self._text_overlap_score(heading_path, query_terms)
        content_score = self._text_overlap_score(text, query_terms)
        adjusted = score
        adjusted += heading_score * 0.18
        adjusted += path_score * 0.10
        adjusted += content_score * 0.06
        if section_title == "目录" or "目录" in heading_path:
            adjusted -= 0.35
        if heading_score + path_score + content_score < 0.12:
            adjusted -= 0.18
        return adjusted

    def _score_chunk_result(
        self,
        query_terms: List[str],
        result: Dict[str, Any],
        parent_score: float = 0.0
    ) -> float:
        """对 chunk 结果做重排与去噪评分.

        综合考虑标题、路径、内容、父级章节得分以及代码占比等因素，对原始相似度进行调整。

        Args:
            query_terms: 查询关键词列表
            result: chunk 结果字典
            parent_score: 父级章节的重排分数

        Returns:
            调整后的重排分数，保留4位小数
        """
        heading_path = result.get("heading_path", "")
        section_title = result.get("section_title", "")
        content = result.get("content", "")
        code_ratio = self._estimate_code_ratio(content)
        section_score = self._text_overlap_score(section_title, query_terms)
        path_score = self._text_overlap_score(heading_path, query_terms)
        content_score = self._text_overlap_score(content[:500], query_terms)

        adjusted = result["score"]
        adjusted += parent_score * 0.18
        adjusted += section_score * 0.16
        adjusted += path_score * 0.10
        adjusted += content_score * 0.06

        if "目录" in heading_path or section_title == "目录":
            adjusted -= 0.35
        if code_ratio > 0.65 and section_score + path_score < 0.12:
            adjusted -= 0.10
        if len(content.strip()) < 60:
            adjusted -= 0.08
        if section_score + path_score + content_score < 0.12:
            adjusted -= 0.22
        return round(adjusted, 4)

    @staticmethod
    def _dedupe_and_diversify_results(results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """按 section 去重并做轻量多样性控制.

        优先选择不同章节的结果，避免结果集中在少数章节。

        Args:
            results: 待去重的结果列表
            top_k: 最多返回的结果数量

        Returns:
            去重和多样化后的结果列表
        """
        selected = []
        seen_sections = set()
        deferred = []
        for result in results:
            section_id = result.get("section_id")
            if section_id and section_id in seen_sections:
                deferred.append(result)
                continue
            if section_id:
                seen_sections.add(section_id)
            selected.append(result)
            if len(selected) >= top_k:
                return selected
        for result in deferred:
            selected.append(result)
            if len(selected) >= top_k:
                break
        return selected

    def format_source_references(self, results: List[Dict[str, Any]], limit: int = 3) -> List[str]:
        """格式化知识来源引用.

        将搜索结果格式化为可读性强的引用列表，去重并限制数量。

        Args:
            results: 搜索结果列表
            limit: 最多返回的引用数量

        Returns:
            格式化的引用字符串列表
        """
        references = []
        seen = set()
        for result in results[:limit]:
            source_name = result.get("name", "unknown")
            heading_path = result.get("heading_path") or result.get("section_title") or "未命名片段"
            chunk_index = int(result.get("chunk_index", 0)) + 1
            chunk_count = int(result.get("chunk_count", 1))
            ref = f"{source_name} | {heading_path} | Chunk {chunk_index}/{chunk_count}"
            if ref in seen:
                continue
            seen.add(ref)
            references.append(ref)
        return references

    @staticmethod
    def _normalize_extensions(extensions: Optional[List[str]]) -> Optional[List[str]]:
        """规范化文件扩展名列表.

        确保所有扩展名都以点开头，去除空白字符。

        Args:
            extensions: 原始扩展名列表

        Returns:
            规范化后的扩展名列表，或 None
        """
        if not extensions:
            return None
        normalized = []
        for ext in extensions:
            cleaned = ext.strip()
            if not cleaned:
                continue
            normalized.append(cleaned if cleaned.startswith(".") else f".{cleaned}")
        return normalized or None

    @staticmethod
    def _normalize_path(path: Path) -> str:
        """规范化路径为绝对路径字符串.

        Args:
            path: 路径对象

        Returns:
            规范化的绝对路径字符串
        """
        return str(path.resolve())

    @staticmethod
    def _clean_chunk_text(text: str) -> str:
        """清理分块文本.

        去除首尾空白，将连续3个及以上换行符压缩为2个。

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        return re.sub(r"\n{3,}", "\n\n", text.strip())

    def _build_chunk_id(self, file_path: Path, chunk_index: int, chunk_text: str) -> str:
        """构建稳定的 chunk ID.

        基于文件路径、索引和内容生成MD5哈希，取前16位作为ID。

        Args:
            file_path: 文件路径对象
            chunk_index: chunk 索引
            chunk_text: chunk 内容

        Returns:
            16字符的哈希ID
        """
        raw = f"{self._normalize_path(file_path)}::{chunk_index}::{chunk_text}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _detect_section_title(paragraph: str, fallback: str) -> str:
        """从段落中提取章节标题.

        取第一行并去除Markdown标题标记作为标题。

        Args:
            paragraph: 段落文本
            fallback: 无法提取时的默认标题

        Returns:
            提取的章节标题
        """
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            return fallback
        first_line = lines[0].lstrip("#").strip()
        return first_line or fallback

    def _build_section_id(self, file_path: Path, path_titles: List[str], level: int, order: int) -> str:
        """构建稳定的章节 ID.

        基于文件路径、层级、顺序和标题路径生成MD5哈希。

        Args:
            file_path: 文件路径对象
            path_titles: 标题路径列表
            level: 标题层级
            order: 出现顺序

        Returns:
            16字符的哈希ID
        """
        raw = f"{self._normalize_path(file_path)}::{level}::{order}::{' > '.join(path_titles)}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    def _parse_markdown_sections(self, file_path: Path, text: str) -> List[Dict[str, Any]]:
        """按 Markdown 标题层级解析章节树.

        使用栈结构构建嵌套的章节树，同时处理代码块中的内容。

        Args:
            file_path: 文件路径对象
            text: Markdown 文本内容

        Returns:
            章节列表（不包含根节点）
        """
        lines = text.splitlines()
        root_title = file_path.stem
        root_section: Dict[str, Any] = {
            "section_id": self._build_section_id(file_path, [root_title], 0, 0),
            "title": root_title,
            "level": 0,
            "path_titles": [root_title],
            "parent_section_id": None,
            "ancestor_section_ids": [],
            "content_lines": [],
            "children": [],
            "order": 0,
        }
        sections: List[Dict[str, Any]] = []
        stack: List[Dict[str, Any]] = [root_section]
        heading_order = 0
        in_code_block = False
        heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                current_section = stack[-1]
                current_section["content_lines"].append(line)
                in_code_block = not in_code_block
                continue

            if not in_code_block:
                heading_match = heading_pattern.match(line)
                if heading_match:
                    level = len(heading_match.group(1))
                    title = heading_match.group(2).strip()
                    while stack and stack[-1]["level"] >= level:
                        stack.pop()
                    parent = stack[-1] if stack else root_section
                    heading_order += 1
                    section = {
                        "section_id": self._build_section_id(
                            file_path,
                            parent["path_titles"] + [title],
                            level,
                            heading_order,
                        ),
                        "title": title,
                        "level": level,
                        "path_titles": parent["path_titles"] + [title],
                        "parent_section_id": parent["section_id"],
                        "ancestor_section_ids": (
                            parent.get("ancestor_section_ids", [])
                            + ([parent["section_id"]] if parent["level"] > 0 else [])
                        ),
                        "content_lines": [],
                        "children": [],
                        "order": heading_order,
                    }
                    parent["children"].append(section)
                    sections.append(section)
                    stack.append(section)
                    continue

            current_section = stack[-1]
            current_section["content_lines"].append(line)

        def finalize(section: Dict[str, Any]) -> None:
            own_content = self._clean_chunk_text("\n".join(section["content_lines"]))
            child_contents = []
            for child in section["children"]:
                finalize(child)
                if child.get("aggregated_content"):
                    child_contents.append(child["aggregated_content"])
            section["own_content"] = own_content
            section["aggregated_content"] = self._clean_chunk_text(
                "\n\n".join([part for part in [own_content, *child_contents] if part])
            )
            section["heading_path"] = " > ".join(section["path_titles"])

        finalize(root_section)
        return sections

    def _chunk_text(
        self,
        text: str,
        section_title: str = "全文",
        heading_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """将文本切分为适合检索的块.

        使用段落优先策略，结合重叠窗口进行切分，确保语义完整性。

        Args:
            text: 待切分的文本
            section_title: 所属章节标题
            heading_path: 标题路径

        Returns:
            chunk 列表，每个包含 content、char_start、char_end 等信息
        """
        cleaned_text = self._clean_chunk_text(text)
        if not cleaned_text:
            return []

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned_text) if part.strip()]
        chunks: List[Dict[str, Any]] = []
        current = ""
        chunk_start = 0
        cursor = 0

        def flush_chunk() -> None:
            nonlocal current, chunk_start
            chunk_text = self._clean_chunk_text(current)
            if not chunk_text:
                return
            char_end = chunk_start + len(chunk_text)
            chunks.append({
                "content": chunk_text,
                "char_start": chunk_start,
                "char_end": char_end,
                "section_title": section_title,
                "heading_path": heading_path or section_title,
            })
            if len(chunk_text) > self.chunk_overlap:
                overlap_text = chunk_text[-self.chunk_overlap:]
                if "\n" in overlap_text:
                    overlap_text = overlap_text.split("\n", 1)[-1].lstrip()
                elif " " in overlap_text:
                    overlap_text = overlap_text.split(" ", 1)[-1].lstrip()
                current = overlap_text
                chunk_start = max(0, char_end - len(overlap_text))
            else:
                current = ""
                chunk_start = char_end

        for paragraph in paragraphs:
            paragraph_text = self._clean_chunk_text(paragraph)
            paragraph_start = cleaned_text.find(paragraph_text, cursor)
            if paragraph_start == -1:
                paragraph_start = cursor
            cursor = paragraph_start + len(paragraph_text)

            if not current:
                chunk_start = paragraph_start

            candidate = f"{current}\n\n{paragraph_text}" if current else paragraph_text
            if current and len(candidate) > self.chunk_size:
                flush_chunk()
                if not current:
                    chunk_start = paragraph_start
                candidate = f"{current}\n\n{paragraph_text}" if current else paragraph_text

            while len(candidate) > self.chunk_size:
                head = candidate[:self.chunk_size]
                split_at = head.rfind("\n")
                if split_at < self.chunk_size // 2:
                    split_at = self.chunk_size
                current = candidate[:split_at]
                flush_chunk()
                candidate = (
                    f"{current}\n\n{candidate[split_at:].lstrip()}"
                    if current else candidate[split_at:].lstrip()
                )
                if not current:
                    chunk_start = max(paragraph_start, cursor - len(candidate))

            current = candidate

        if current:
            flush_chunk()

        for index, chunk in enumerate(chunks):
            chunk["chunk_index"] = index
            chunk["chunk_count"] = len(chunks)

        return chunks

    def _find_entries_by_path(self, file_path: Path) -> List[KnowledgeEntry]:
        """根据文件路径查找知识条目.

        Args:
            file_path: 文件路径对象

        Returns:
            匹配的知识条目列表
        """
        normalized_path = self._normalize_path(file_path)
        return [
            entry for entry in self.vector_db.list_all()
            if entry.metadata.get("type") == "file"
            and entry.metadata.get("path") == normalized_path
        ]

    def _delete_entries_by_path(self, file_path: Path) -> int:
        """删除指定文件路径的所有知识条目.

        Args:
            file_path: 文件路径对象

        Returns:
            删除的条目数量
        """
        deleted_count = 0
        for entry in self._find_entries_by_path(file_path):
            if self.vector_db.delete(entry.id):
                deleted_count += 1
        return deleted_count

    def _is_file_index_current(self, file_path: Path) -> bool:
        """检查文件索引是否是最新的.

        通过比较文件修改时间判断是否需要重新索引。

        Args:
            file_path: 文件路径对象

        Returns:
            索引是最新的返回 True，否则返回 False
        """
        entries = self._find_entries_by_path(file_path)
        if not entries:
            return False

        current_mtime = file_path.stat().st_mtime
        for entry in entries:
            indexed_mtime = entry.metadata.get("source_mtime")
            if indexed_mtime == current_mtime:
                return True
        return False

    def index_file(self, file_path: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """索引单个文件.

        Args:
            file_path: 文件路径
            tags: 标签列表

        Returns:
            知识条目 ID，如果索引失败则返回 None
        """
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            return None

        try:
            self._delete_entries_by_path(path)

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            sections = self._parse_markdown_sections(path, content)
            if not sections:
                return None

            base_metadata = {
                "type": "file",
                "path": self._normalize_path(path),
                "name": path.name,
                "extension": path.suffix,
                "source_mtime": path.stat().st_mtime,
            }

            file_tags = list(tags or [])
            file_tags.append(f"file:{path.name}")
            if path.suffix:
                file_tags.append(f"ext:{path.suffix[1:]}")

            indexed_ids: List[str] = []
            for section in sections:
                aggregated_content = section.get("aggregated_content", "")
                if aggregated_content and len(aggregated_content) >= 40:
                    section_metadata = {
                        **base_metadata,
                        "node_type": "section",
                        "section_id": section["section_id"],
                        "parent_section_id": section["parent_section_id"],
                        "heading_level": section["level"],
                        "section_title": section["title"],
                        "heading_path": section["heading_path"],
                    }
                    section_tags = list(file_tags)
                    section_tags.extend([
                        "node:section",
                        f"section:{section['section_id']}",
                        f"level:{section['level']}",
                    ])
                    if section["parent_section_id"]:
                        section_tags.append(f"parent:{section['parent_section_id']}")
                    section_document = (
                        f"Heading Path: {section['heading_path']}\n\n"
                        f"{aggregated_content[:1200]}"
                    )
                    section_entry_id = self.vector_db.add(
                        content=section_document,
                        metadata=section_metadata,
                        tags=section_tags,
                        entry_id=self._build_chunk_id(path, section["order"], section_document),
                    )
                    if section_entry_id:
                        indexed_ids.append(section_entry_id)

                own_content = section.get("own_content", "")
                if not own_content:
                    continue
                chunks = self._chunk_text(
                    own_content,
                    section_title=section["title"],
                    heading_path=section["heading_path"],
                )
                ancestor_ids = section.get("ancestor_section_ids", [])
                for chunk in chunks:
                    metadata = {
                        **base_metadata,
                        "node_type": "chunk",
                        "section_id": section["section_id"],
                        "parent_section_id": section["parent_section_id"],
                        "heading_level": section["level"],
                        "section_title": chunk["section_title"],
                        "heading_path": chunk["heading_path"],
                        "chunk_index": chunk["chunk_index"],
                        "chunk_count": chunk["chunk_count"],
                        "char_start": chunk["char_start"],
                        "char_end": chunk["char_end"],
                    }
                    chunk_tags = list(file_tags)
                    chunk_tags.extend([
                        "node:chunk",
                        f"chunk:{chunk['chunk_index'] + 1}",
                        f"section:{section['section_id']}",
                    ])
                    for ancestor_id in ancestor_ids + [section["section_id"]]:
                        chunk_tags.append(f"ancestor:{ancestor_id}")
                    entry_id = self.vector_db.add(
                        content=chunk["content"],
                        metadata=metadata,
                        tags=chunk_tags,
                        entry_id=self._build_chunk_id(path, chunk["chunk_index"], chunk["content"]),
                    )
                    if entry_id:
                        indexed_ids.append(entry_id)

            return indexed_ids[0] if indexed_ids else None
        except Exception as e:
            print(f"[Warning] Failed to index file {file_path}: {e}")
            return None

    def index_directory(self, dir_path: str,
                        extensions: Optional[List[str]] = None,
                        recursive: bool = True) -> int:
        """索引整个目录.

        Args:
            dir_path: 目录路径
            extensions: 要索引的文件扩展名列表（如 [".py", ".md"]）
            recursive: 是否递归索引子目录

        Returns:
            成功索引的文件数量
        """
        path = Path(dir_path).resolve()
        if not path.exists() or not path.is_dir():
            return 0

        normalized_extensions = self._normalize_extensions(extensions)
        count = 0
        glob_pattern = "**/*" if recursive else "*"

        for file_path in path.glob(glob_pattern):
            if not file_path.is_file():
                continue

            if normalized_extensions:
                if file_path.suffix not in normalized_extensions:
                    continue

            if self.index_file(str(file_path)):
                count += 1

        return count

    def sync_directory(self, dir_path: str,
                       extensions: Optional[List[str]] = None,
                       recursive: bool = True,
                       tags: Optional[List[str]] = None) -> Dict[str, int]:
        """同步目录到知识库.

        智能同步：新增文件索引、更新修改的文件、删除不存在的文件。

        Args:
            dir_path: 目录路径
            extensions: 要同步的文件扩展名列表
            recursive: 是否递归处理子目录
            tags: 标签列表

        Returns:
            同步统计字典，包含 indexed、updated、removed、skipped 字段
        """
        path = Path(dir_path).resolve()
        if not path.exists() or not path.is_dir():
            return {"indexed": 0, "updated": 0, "removed": 0, "skipped": 0}

        normalized_extensions = self._normalize_extensions(extensions)
        glob_pattern = "**/*" if recursive else "*"
        target_files: List[Path] = []
        for file_path in path.glob(glob_pattern):
            if not file_path.is_file():
                continue
            if normalized_extensions and file_path.suffix not in normalized_extensions:
                continue
            target_files.append(file_path.resolve())

        expected_paths = {self._normalize_path(file_path) for file_path in target_files}
        removed = 0
        for entry in list(self.vector_db.list_all()):
            entry_path = entry.metadata.get("path")
            if (
                entry.metadata.get("type") == "file"
                and isinstance(entry_path, str)
                and entry_path.startswith(f"{self._normalize_path(path)}")
                and entry_path not in expected_paths
            ):
                if self.vector_db.delete(entry.id):
                    removed += 1

        indexed = 0
        updated = 0
        skipped = 0
        for file_path in sorted(target_files):
            has_existing = bool(self._find_entries_by_path(file_path))
            if self._is_file_index_current(file_path):
                skipped += 1
                continue
            entry_id = self.index_file(str(file_path), tags=tags)
            if not entry_id:
                continue
            if has_existing:
                updated += 1
            else:
                indexed += 1

        return {
            "indexed": indexed,
            "updated": updated,
            "removed": removed,
            "skipped": skipped,
        }

    def sync_auto_sources(self,
                          extensions: Optional[List[str]] = None,
                          tags: Optional[List[str]] = None) -> Dict[str, int]:
        """同步默认知识目录.

        同步所有配置的自动同步路径。

        Args:
            extensions: 要同步的文件扩展名列表
            tags: 标签列表

        Returns:
            同步统计字典，包含 indexed、updated、removed、skipped 字段
        """
        summary = {"indexed": 0, "updated": 0, "removed": 0, "skipped": 0}
        for path in self.auto_sync_paths:
            result = self.sync_directory(
                str(path),
                extensions=extensions or [".md", ".txt"],
                recursive=True,
                tags=tags
            )
            for key in summary:
                summary[key] += result.get(key, 0)
        return summary

    def add_knowledge(self, content: str,
                      metadata: Optional[Dict[str, Any]] = None,
                      tags: Optional[List[str]] = None) -> str:
        """添加知识.

        Args:
            content: 知识内容
            metadata: 元数据
            tags: 标签列表

        Returns:
            知识条目 ID
        """
        return self.vector_db.add(content, metadata, tags)

    def search(self, query: str, top_k: int = 5,
               tags: Optional[List[str]] = None) -> List[Tuple[KnowledgeEntry, float]]:
        """搜索知识.

        Args:
            query: 查询文本
            top_k: 返回最相关的 K 个结果
            tags: 标签过滤

        Returns:
            (知识条目, 相似度) 列表
        """
        self.sync_auto_sources()
        raw_results = self.vector_db.search(query, max(top_k * 4, 12), tags)
        filtered_results = []
        for entry, score in raw_results:
            node_type = entry.metadata.get("node_type")
            if node_type == "section":
                continue
            filtered_results.append((entry, score))
            if len(filtered_results) >= top_k:
                break
        return filtered_results

    def search_chunks(self, query: str, top_k: int = 5,
                      tags: Optional[List[str]] = None,
                      min_score: float = 0.0) -> List[Dict[str, Any]]:
        """搜索并返回面向 RAG 的 chunk 结果.

        执行向量搜索、重排序、去重，返回结构化的结果。

        Args:
            query: 查询文本
            top_k: 返回结果数量
            tags: 标签过滤
            min_score: 最小分数阈值

        Returns:
            结构化的 chunk 结果列表
        """
        query_terms = self._extract_query_terms(query)
        formatted_results = []
        raw_results = self.vector_db.search(query, max(top_k * 4, 12), tags)
        for entry, score in raw_results:
            if score < min_score:
                continue
            metadata = entry.metadata or {}
            if metadata.get("node_type") == "section":
                continue
            formatted_results.append({
                "entry": entry,
                "content": entry.content,
                "score": score,
                "path": metadata.get("path", ""),
                "name": metadata.get("name", ""),
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
                "chunk_index": metadata.get("chunk_index", 0),
                "chunk_count": metadata.get("chunk_count", 1),
                "char_start": metadata.get("char_start", 0),
                "char_end": metadata.get("char_end", 0),
                "section_id": metadata.get("section_id", ""),
                "parent_section_id": metadata.get("parent_section_id", ""),
                "heading_level": metadata.get("heading_level", 0),
                "metadata": metadata,
                "tags": entry.tags,
            })
        for result in formatted_results:
            result["rerank_score"] = self._score_chunk_result(query_terms, result)
        formatted_results.sort(key=lambda item: item.get("rerank_score", item["score"]), reverse=True)
        return self._dedupe_and_diversify_results(formatted_results, top_k)

    def search_hierarchical(self, query: str, top_k: int = 4,
                            parent_top_k: int = 3,
                            min_score: float = 0.2) -> List[Dict[str, Any]]:
        """执行基于标题层级的父子检索.

        先检索相关章节，再在这些章节的子chunk中进行精搜，结合层级信息重排。

        Args:
            query: 查询文本
            top_k: 最终返回结果数量
            parent_top_k: 最多考虑的父章节数量
            min_score: 最小分数阈值

        Returns:
            结构化的 chunk 结果列表
        """
        self.sync_auto_sources()
        query_terms = self._extract_query_terms(query)

        parent_candidates = self.vector_db.search(query, max(parent_top_k * 4, 12), tags=["node:section"])
        parent_results = []
        seen_parent_ids = set()
        for entry, score in parent_candidates:
            metadata = entry.metadata or {}
            if score < min_score:
                continue
            if metadata.get("section_title") == "目录":
                continue
            section_id = metadata.get("section_id")
            if not section_id or section_id in seen_parent_ids:
                continue
            seen_parent_ids.add(section_id)
            parent_results.append({
                "entry": entry,
                "score": score,
                "rerank_score": self._score_parent_result(query_terms, entry, score),
                "section_id": section_id,
                "section_title": metadata.get("section_title", ""),
                "heading_path": metadata.get("heading_path", ""),
            })
        parent_results.sort(key=lambda item: item.get("rerank_score", item["score"]), reverse=True)
        parent_results = parent_results[:parent_top_k]

        combined_results = []
        seen_chunk_ids = set()
        for parent in parent_results:
            child_results = self.search_chunks(
                query,
                top_k=max(top_k * 2, 6),
                tags=[f"ancestor:{parent['section_id']}"],
                min_score=min_score
            )
            for child in child_results:
                entry_id = child["entry"].id
                if entry_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(entry_id)
                child["matched_parent_section"] = parent["section_title"]
                child["matched_parent_path"] = parent["heading_path"]
                child["parent_score"] = parent["score"]
                child["parent_rerank_score"] = parent["rerank_score"]
                child["hierarchy_score"] = self._score_chunk_result(
                    query_terms,
                    child,
                    parent_score=parent["rerank_score"]
                )
                combined_results.append(child)
                if len([item for item in combined_results if item.get("section_id") == child.get("section_id")]) >= 2:
                    break

        if not combined_results:
            return self.search_chunks(query, top_k=top_k, min_score=min_score)

        combined_results.sort(key=lambda item: item.get("hierarchy_score", item["score"]), reverse=True)
        diversified = self._dedupe_and_diversify_results(combined_results, top_k)
        if not diversified:
            return diversified
        best_score = diversified[0].get("hierarchy_score", diversified[0]["score"])
        threshold = max(min_score, best_score * 0.72)
        filtered = [
            item for item in diversified
            if item.get("hierarchy_score", item["score"]) >= threshold
        ]
        return filtered[:top_k]

    def get_context_for_prompt(self, query: str, top_k: int = 3,
                               min_score: float = 0.35) -> str:
        """获取用于 Prompt 的上下文.

        Args:
            query: 查询文本
            top_k: 返回最相关的 K 个结果

        Returns:
            格式化的上下文字符串
        """
        results = self.search_hierarchical(query, top_k=top_k, min_score=min_score)
        if not results:
            return ""

        context_parts = ["[Knowledge Base Context]"]
        for i, result in enumerate(results, 1):
            source_name = result["name"] or "unknown"
            section_title = result["section_title"] or "未命名片段"
            chunk_index = int(result["chunk_index"]) + 1
            chunk_count = int(result["chunk_count"])
            context_parts.append(
                f"[Knowledge {i}] "
                f"(Relevance: {result['score']:.2f}, "
                f"Source: {source_name}, "
                f"Section: {section_title}, "
                f"Path: {result.get('heading_path', section_title)}, "
                f"Chunk: {chunk_index}/{chunk_count})\n"
                f"{result['content'][:500]}"
                + ("..." if len(result["content"]) > 500 else "")
            )

        return "\n\n".join(context_parts)

    def list_all(self) -> List[KnowledgeEntry]:
        """列出所有知识条目.

        Returns:
            知识条目列表
        """
        return self.vector_db.list_all()

    def delete(self, entry_id: str) -> bool:
        """删除知识条目.

        Args:
            entry_id: 条目 ID

        Returns:
            是否删除成功
        """
        return self.vector_db.delete(entry_id)


# 全局知识管理器实例
knowledge_manager = KnowledgeManager()
