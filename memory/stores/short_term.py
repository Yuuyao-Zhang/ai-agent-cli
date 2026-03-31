"""短期记忆存储.

使用双端队列实现有限大小的活跃窗口。
"""

import collections
from typing import List, Dict, Any
from .base import MemoryStore


class ShortTermStore(MemoryStore):
    """短期记忆存储类."""

    def __init__(self, max_rounds: int = 20):
        """初始化短期记忆存储.

        Args:
            max_rounds: 最大轮数
        """
        self.max_rounds = max_rounds
        self.buffer = collections.deque(maxlen=max_rounds)

    def add(self, round_id: int, content: str, role: str = "user") -> bool:
        """添加新的交互到短期记忆缓冲区.

        Args:
            round_id: 轮次ID
            content: 内容
            role: 角色 (user/assistant)

        Returns:
            是否添加成功
        """
        self.buffer.append({
            "round_id": round_id,
            "content": content,
            "role": role
        })
        return True

    def get(self, n: int = None) -> List[Dict[str, Any]]:
        """获取最近的n条交互.

        Args:
            n: 数量，默认为全部

        Returns:
            记忆条目列表
        """
        n = n or self.max_rounds
        # 如果n大于缓冲区大小，返回全部
        if n > len(self.buffer):
            return list(self.buffer)
        return list(self.buffer)[-n:]

    def get_recent(self, n: int = None) -> List[Dict[str, Any]]:
        """get()的别名，以匹配用户的潜在期望.

        Args:
            n: 数量

        Returns:
            记忆条目列表
        """
        return self.get(n)

    def clear(self) -> bool:
        """清空短期记忆.

        Returns:
            是否清空成功
        """
        self.buffer.clear()
        return True
