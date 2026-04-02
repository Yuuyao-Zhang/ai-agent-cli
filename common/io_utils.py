"""I/O 工具模块.

该模块提供了统一的输入输出抽象层，支持标准输入输出、颜色控制、
以及不同级别的日志输出（debug、info、error、success、warning）。
方便后续扩展（如 WebSocket 或 GUI 适配）。
"""

import platform
import sys
from typing import Optional

IS_WINDOWS = platform.system() == "Windows"


def safe_text(text: str, stream: Optional[object] = None) -> str:
    """安全处理文本，确保可以正确输出到指定流.

    处理可能包含不可打印字符的文本，确保在输出到控制台时不会出错。

    Args:
        text: 要处理的文本
        stream: 输出流，默认为标准输出 (sys.stdout)

    Returns:
        处理后的安全文本
    """
    if not isinstance(text, str):
        text = str(text)
    encoding = getattr(stream, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


class Colors:
    """ANSI 颜色代码类.

    Windows 兼容性：如果在 Windows 上且未明确处理，禁用颜色。
    注意：现代 Windows 终端支持 ANSI，但 cmd.exe 通常需要启用。
    为了安全/简单起见，我们在 Windows 上默认禁用颜色。

    Attributes:
        HEADER: 紫红色
        BLUE: 蓝色
        CYAN: 青色
        GREEN: 绿色
        YELLOW: 黄色
        RED: 红色
        RESET: 重置颜色
        BOLD: 粗体
        DIM: 暗色
    """

    if IS_WINDOWS:
        HEADER = ""
        BLUE = ""
        CYAN = ""
        GREEN = ""
        YELLOW = ""
        RED = ""
        RESET = ""
        BOLD = ""
        DIM = ""
    else:
        HEADER = "\033[95m"
        BLUE = "\033[94m"
        CYAN = "\033[96m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        RED = "\033[91m"
        RESET = "\033[0m"
        BOLD = "\033[1m"
        DIM = "\033[2m"


def output(text: str, stream=sys.stdout, color: str = None) -> None:
    """输出文本到指定流.

    Args:
        text: 要输出的文本
        stream: 输出流，默认为标准输出 (sys.stdout)
        color: 颜色代码，默认为 None (无颜色)
    """
    safe = safe_text(text, stream)
    if color:
        print(f"{color}{safe}{Colors.RESET}", file=stream)
    else:
        print(safe, file=stream)


def input_request(prompt: str = "") -> str:
    """请求用户输入.

    Args:
        prompt: 提示符文本，默认为空字符串

    Returns:
        用户输入的字符串
    """
    return input(f"{Colors.CYAN}{prompt}{Colors.RESET}")


def debug(msg: str) -> None:
    """输出调试信息.

    Args:
        msg: 调试消息
    """
    output(f"[DEBUG] {msg}", sys.stderr, Colors.DIM)


def info(msg: str) -> None:
    """输出信息.

    Args:
        msg: 信息消息
    """
    output(f"[INFO] {msg}", sys.stdout)


def error(msg: str) -> None:
    """输出错误信息.

    Args:
        msg: 错误消息
    """
    output(f"[ERROR] {msg}", sys.stderr, Colors.RED)


def success(msg: str) -> None:
    """输出成功信息.

    Args:
        msg: 成功消息
    """
    output(f"{msg}", sys.stdout, Colors.GREEN)


def warning(msg: str) -> None:
    """输出警告信息.

    Args:
        msg: 警告消息
    """
    output(f"[WARN] {msg}", sys.stdout, Colors.YELLOW)
