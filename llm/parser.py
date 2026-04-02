"""命令解析器模块.

该模块负责解析 LLM 响应，提取结构化指令。
支持 bash、read、write、edit、todo、subtask 等多种指令格式。
"""

import json
import re
from typing import Any


def _parse_json_commands(data: Any) -> list[tuple[str, Any]]:
    """从JSON数据中解析命令.

    支持多种JSON格式的命令解析。

    Args:
        data: JSON数据 (列表或字典)

    Returns:
        命令列表，每个元素为 (命令类型, 命令内容) 的元组
    """
    commands = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "tool" in item:
                tool = item["tool"]
                args = item.get("args")
                commands.append((tool, args))
        return commands

    if isinstance(data, dict) and "tool_calls" in data:
        for tool_call in data["tool_calls"]:
            if "function" in tool_call:
                name = tool_call["function"]["name"]
                args_str = tool_call["function"]["arguments"]
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    if name == "bash":
                        args = args.get("cmd") or args.get("command")
                    elif name == "write":
                        args = (args.get("path"), args.get("content"))
                    elif name == "edit":
                        args = (args.get("path"), args.get("old"), args.get("new"))
                    commands.append((name, args))
                except Exception:
                    pass
    return commands


def parse_commands(text: str) -> list[tuple[str, Any]]:
    """解析 LLM 响应，提取结构化指令.

    优先尝试解析 JSON 格式的结构化指令，如果失败则回退到正则匹配。

    JSON 格式示例：
    [
        {"tool": "bash", "args": "ls -la"},
        {"tool": "write", "args": ["file.txt", "content"]}
    ]
    或者
    {
        "tool_calls": [
            {"name": "bash", "arguments": {"cmd": "ls -la"}}
        ]
    }

    支持正则格式：
    - bash: ```bash ... ``` (兼容 shell, sh, zsh, powershell, cmd)
    - read: ```read <path>```
    - write: ```write <path> ... ```
    - edit: ```edit <path> <old> <new>```
    - todo: ```todo ... ``` (JSON content)
    - subtask: SUBTASK: <子任务描述>

    Args:
        text: LLM 响应文本

    Returns:
        指令列表，每个元素为 (指令类型, 指令内容) 的元组
    """
    text_stripped = text.strip()
    if text_stripped.startswith("{") or text_stripped.startswith("["):
        try:
            data = json.loads(text_stripped)
            commands = _parse_json_commands(data)
            if commands:
                return commands
        except json.JSONDecodeError:
            pass

    json_block_pattern = r"```json\s*(.*?)\s*```"
    for match in re.finditer(json_block_pattern, text, re.DOTALL | re.IGNORECASE):
        block = match.group(1).strip()
        try:
            data = json.loads(block)
            commands = _parse_json_commands(data)
            if commands:
                return commands
        except json.JSONDecodeError:
            continue

    bash_pattern = r"```(?:bash|shell|sh|zsh|powershell|cmd)\n(.*?)\n```"

    patterns = [
        ("bash", bash_pattern),
        ("read", r"```read\n(.*?)\n```"),
        ("write", r"```write (.*?)\n(.*?)\n```"),
        ("edit", r"```edit (.*?)\n<<OLD\n(.*?)\nOLD\n<<NEW\n(.*?)\nNEW\n```"),
        ("todo", r"```todo\n(.*?)\n```"),
        ("subtask", r"SUBTASK: (.*)")
    ]

    commands = []

    for cmd_type, pattern in patterns:
        for match in re.finditer(
            pattern,
            text,
            re.DOTALL | re.IGNORECASE if cmd_type == "bash" else re.DOTALL
        ):
            if cmd_type == "write":
                content = (match.group(1).strip(), match.group(2).strip())
            elif cmd_type == "edit":
                content = (
                    match.group(1).strip(),
                    match.group(2).strip(),
                    match.group(3).strip()
                )
            else:
                content = match.group(1).strip()

            commands.append((match.start(), cmd_type, content))

    commands.sort(key=lambda x: x[0])

    return [(cmd[1], cmd[2]) for cmd in commands]
