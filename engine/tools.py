"""工具执行模块.

该模块实现了各种工具的执行功能，包括 Bash 命令执行、文件读写、
文件编辑和 To-do 管理等操作。
"""

import json
import subprocess
import os
import shlex
from typing import Any

from todo.store import to_do_store
from todo.render import renderer
from mcp.registry import registry


def _validate_args(inst_type: str, args: Any) -> tuple[bool, str]:
    """验证指令参数的有效性.

    根据指令类型检查参数格式和内容是否符合要求。

    Args:
        inst_type: 指令类型 (bash, read, write, edit, todo, tool)
        args: 指令参数

    Returns:
        (是否有效, 错误信息或空字符串) 的元组
    """
    if inst_type in ["bash", "read", "todo", "tool"]:
        if not isinstance(args, str):
            return False, f"Error: '{inst_type}' expects a string argument."
        if inst_type == "bash" and (not args.strip() or len(args) > 10000):
            return False, "Error: Invalid bash command."
        if inst_type == "read" and not args.strip():
            return False, "Error: read requires a file path."
        if inst_type in ["todo", "tool"] and not args.strip():
            return False, f"Error: '{inst_type}' requires JSON string content."
        return True, ""
    if inst_type == "write":
        if not isinstance(args, (tuple, list)) or len(args) != 2:
            return False, "Error: write requires (path, content)."
        if not isinstance(args[0], str) or not isinstance(args[1], str):
            return False, "Error: write path and content must be strings."
        if not args[0].strip():
            return False, "Error: write requires a valid file path."
        return True, ""
    if inst_type == "edit":
        if not isinstance(args, (tuple, list)) or len(args) != 3:
            return False, "Error: edit requires (path, old, new)."
        if not all(isinstance(a, str) for a in args):
            return False, "Error: edit arguments must be strings."
        if not args[0].strip():
            return False, "Error: edit requires a valid file path."
        return True, ""
    return True, ""


def validate_path(path: str, cwd: str = None) -> str:
    """验证路径是否安全（在工作目录内）.

    确保路径在允许的工作目录范围内，防止目录遍历攻击。

    Args:
        path: 待验证的路径
        cwd: 工作目录，默认为当前目录

    Returns:
        安全的绝对路径

    Raises:
        ValueError: 当路径超出工作目录范围时
    """
    if cwd is None:
        cwd = os.getcwd()

    # 转换为绝对路径
    abs_cwd = os.path.abspath(cwd)
    abs_path = os.path.abspath(os.path.join(abs_cwd, path))

    # 检查是否在工作目录内
    if not abs_path.startswith(abs_cwd):
        raise ValueError(f"Path access denied: {path} is outside working directory {cwd}")

    return abs_path


def is_command_safe(command: str) -> bool:
    """简单检查命令安全性.

    通过黑名单机制检查命令是否包含危险操作。

    Args:
        command: 待检查的命令字符串

    Returns:
        命令安全返回True，否则返回False
    """
    # 禁止的命令列表
    DENY_LIST = [
        "rm -rf", "mkfs", "dd", ":(){:|:&};:", "wget", "curl", "nc", "bash -i",
        "python -c", "perl -e", "ruby -e", "php -r", "eval", "exec"
    ]
    # 简单的包含检查
    for bad_cmd in DENY_LIST:
        if bad_cmd in command:
            return False
    return True


def run_bash(command: str, cwd: str = None) -> str:
    """执行 Bash 命令并返回输出.

    Args:
        command: 要执行的 Bash 命令字符串
        cwd: 工作目录

    Returns:
        格式化后的输出，包含标准输出(STDOUT)和标准错误(STDERR)
    """
    if cwd is None:
        cwd = os.getcwd()

    if not is_command_safe(command):
        return f"Error: Command '{command}' is not allowed for security reasons."

    try:
        # 再次确认 cwd 存在且安全
        cwd = validate_path(".", cwd)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
            cwd=cwd
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def run_read(path: str, cwd: str = None) -> str:
    """读取文件内容.

    Args:
        path: 文件路径
        cwd: 工作目录

    Returns:
        文件内容或错误信息
    """
    try:
        safe_path = validate_path(path, cwd)
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"File Content ({path}):\n{content}"
    except Exception as e:
        return f"Error reading {path}: {str(e)}"


def run_write(path: str, content: str, cwd: str = None) -> str:
    """写入文件内容 (覆盖).

    Args:
        path: 文件路径
        content: 要写入的内容
        cwd: 工作目录

    Returns:
        成功消息或错误信息
    """
    try:
        safe_path = validate_path(path, cwd)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to {path}: {str(e)}"


def run_edit(path: str, old: str, new: str, cwd: str = None) -> str:
    """基于字符串替换的简单编辑.

    Args:
        path: 文件路径
        old: 要替换的旧内容
        new: 替换后的新内容
        cwd: 工作目录

    Returns:
        成功消息或错误信息
    """
    try:
        safe_path = validate_path(path, cwd)
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old not in content:
            return f"Error: Old content not found in {path}"
        new_content = content.replace(old, new, 1)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully edited {path}"
    except Exception as e:
        return f"Error editing {path}: {str(e)}"


def run_todo(json_content: str) -> str:
    """执行 To-do 管理操作.

    Args:
        json_content: JSON 格式的 To-do 列表数据

    Returns:
        执行结果摘要
    """
    try:
        todos = json.loads(json_content)
        if isinstance(todos, dict):
            todos = [todos]

        to_do_store.bulk_update(todos)
        print(renderer.render(to_do_store.get_all()))

        return f"Successfully updated {len(todos)} todo items."
    except json.JSONDecodeError:
        return "Error: Invalid JSON format for todo items"
    except Exception as e:
        return f"Error updating todos: {str(e)}"


def run_mcp_tool(json_content: str) -> str:
    """执行 MCP 工具调用.

    Args:
        json_content: JSON 字符串, 包含 {"name": "tool_name", "args": {...}}

    Returns:
        工具执行结果
    """
    try:
        data = json.loads(json_content)
        name = data.get("name")
        args = data.get("args", {})
        
        if not name:
            return "Error: Tool name required in content"

        tool = registry.get_tool(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        result = tool(args)
        return f"Tool '{name}' Output:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON format for tool call"
    except Exception as e:
        return f"Error executing tool: {str(e)}"


def execute_instruction(inst_type: str, args: Any, cwd: str = None) -> str:
    """根据指令类型分发执行.

    Args:
        inst_type: 指令类型 (bash, read, write, edit, subtask, todo, tool)
        args: 指令参数 (可能是字符串或元组)
        cwd: 工作目录

    Returns:
        执行结果或错误信息
    """
    if inst_type == "subtask":
        return "Subtask initiated..."

    ok, msg = _validate_args(inst_type, args)
    if not ok:
        return msg

    handlers = {
        "bash": lambda cmd: run_bash(cmd, cwd),
        "read": lambda path: run_read(path, cwd),
        "write": lambda args: run_write(args[0], args[1], cwd),
        "edit": lambda args: run_edit(args[0], args[1], args[2], cwd),
        "todo": lambda content: run_todo(content),
        "tool": lambda content: run_mcp_tool(content),
    }

    handler = handlers.get(inst_type)
    if handler:
        return handler(args)
    else:
        # 尝试直接作为工具名调用 (fallback)
        tool = registry.get_tool(inst_type)
        if tool:
            try:
                # 尝试解析参数
                tool_args = args
                if isinstance(args, str):
                    try:
                        tool_args = json.loads(args)
                    except json.JSONDecodeError:
                        # 无法解析为 JSON，尝试作为单参数输入
                        # 假设简单字符串对应 "input" 或 "query"
                        tool_args = {"input": args}
                
                # 确保参数是字典 (因为 remote_wrapper 和大多数工具都需要 dict/kwargs)
                if not isinstance(tool_args, dict):
                     # 如果工具本身接受非 dict 参数 (不太常见，但为了健壮性)
                     # 我们这里还是强制要求 dict，或者尝试直接传
                     # 但为了安全起见，先报错
                     return f"Error: Arguments for tool '{inst_type}' must be a dictionary or JSON string."

                result = tool(tool_args)
                return f"Tool '{inst_type}' Output:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
            except Exception as e:
                return f"Error executing tool '{inst_type}': {str(e)}"

        return f"Unknown command type: {inst_type}"
