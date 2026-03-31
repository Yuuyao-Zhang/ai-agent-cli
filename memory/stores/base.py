"""记忆存储基类.

所有记忆存储的抽象基类。
"""

from abc import ABC, abstractmethod
from typing import Any


class MemoryStore(ABC):
    """所有记忆存储的抽象基类."""

    @abstractmethod
    def add(self, *args, **kwargs) -> bool:
        """添加数据到存储.

        Returns:
            是否添加成功
        """
        pass

    @abstractmethod
    def get(self, *args, **kwargs) -> Any:
        """从存储检索数据.

        Returns:
            检索到的数据
        """
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空存储的所有数据.

        Returns:
            是否清空成功
        """
        pass
