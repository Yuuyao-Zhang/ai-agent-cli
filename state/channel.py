"""任务间通信模块.

该模块实现了 Channel 类，用于任务之间的消息传递。
支持阻塞/非阻塞操作，可用于子任务与父任务之间的通信。

主要功能:
    1. 任务间消息传递
    2. 阻塞/非阻塞操作支持
    3. 队列大小限制
"""

import queue
from typing import Any, Optional


class Channel:
    """任务间通信通道类.

    用于在任务之间传递消息，支持同步和异步通信模式。

    Attributes:
        name: 通道名称，用于标识
        _queue: 内部队列对象
        closed: 通道是否已关闭
    """

    def __init__(self, name: str = "default", maxsize: int = 0):
        """初始化通信通道.

        Args:
            name: 通道标识符，默认为 "default"
            maxsize: 队列最大容量，0 表示无限制
        """
        self.name = name
        self._queue = queue.Queue(maxsize=maxsize)
        self.closed = False

    def send(
        self,
        data: Any,
        block: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """向通道发送数据.

        Args:
            data: 要发送的数据
            block: 是否阻塞等待，默认为 True
            timeout: 阻塞超时时间（秒），None 表示无限等待

        Returns:
            发送成功返回 True，失败返回 False

        Raises:
            ValueError: 如果通道已关闭
        """
        if self.closed:
            raise ValueError("Cannot send to a closed channel")
        try:
            self._queue.put(data, block=block, timeout=timeout)
            return True
        except queue.Full:
            return False

    def receive(
        self,
        block: bool = True,
        timeout: Optional[float] = None
    ) -> Any:
        """从通道接收数据.

        Args:
            block: 是否阻塞等待，默认为 True
            timeout: 阻塞超时时间（秒），None 表示无限等待

        Returns:
            接收到的数据

        Raises:
            ValueError: 如果通道已关闭且队列为空
            queue.Empty: 如果非阻塞且队列为空
        """
        if self.closed and self._queue.empty():
            raise ValueError("Cannot receive from a closed and empty channel")
        return self._queue.get(block=block, timeout=timeout)

    def close(self) -> None:
        """关闭通道.

        关闭后不能再发送数据，但可以继续接收已有数据。
        """
        self.closed = True

    def qsize(self) -> int:
        """返回队列中的项目数量.

        Returns:
            队列中的项目数量（近似值）
        """
        return self._queue.qsize()

    def empty(self) -> bool:
        """检查队列是否为空.

        Returns:
            队列为空返回 True，否则返回 False
        """
        return self._queue.empty()

    def full(self) -> bool:
        """检查队列是否已满.

        Returns:
            队列已满返回 True，否则返回 False
        """
        return self._queue.full()
