"""终端缓冲区模块.

该模块实现了终端输出的 Ring Buffer，用于截取最后 N 行注入 Prompt，
让模型能够看到最近的操作历史，防止遗忘。
"""

from collections import deque

from common.constant import MAX_BUFFER_LINES


class TerminalBuffer:
    """终端缓冲区类.

    使用双端队列实现 Ring Buffer，自动维护最大行数限制。

    Attributes:
        buffer: 存储终端输出的双端队列
    """

    def __init__(self, max_lines: int = MAX_BUFFER_LINES):
        """初始化终端缓冲区.

        Args:
            max_lines: 缓冲区最大行数，默认为 MAX_BUFFER_LINES
        """
        self.buffer = deque(maxlen=max_lines)

    def write(self, text: str) -> None:
        """写入终端输出，支持多行.

        Args:
            text: 要写入的文本
        """
        for line in text.splitlines():
            self.buffer.append(line)

    def get_snapshot(self) -> str:
        """获取当前缓冲区的快照.

        Returns:
            缓冲区中的所有行，每行之间用换行符分隔
        """
        return "\n".join(self.buffer)

    def clear(self) -> None:
        """清空缓冲区."""
        self.buffer.clear()


# 全局单例
_global_terminal = TerminalBuffer()


def log_output(text: str) -> None:
    """记录终端输出.

    Args:
        text: 要记录的文本
    """
    _global_terminal.write(text)


def get_recent_output() -> str:
    """获取最近的终端输出快照.

    Returns:
        缓冲区中的所有行，每行之间用换行符分隔
    """
    return _global_terminal.get_snapshot()
