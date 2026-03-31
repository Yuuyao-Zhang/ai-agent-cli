"""命名空间模块.

该模块实现了 Namespace 类，用于任务间的变量隔离。
每个任务拥有自己的命名空间，防止变量冲突。
"""

from typing import Any, Dict, Optional


class Namespace:
    """命名空间类.

    提供任务级别的变量隔离，支持嵌套命名空间（父子关系）。

    Attributes:
        name: 命名空间名称
        parent: 父命名空间（可选）
        _variables: 变量字典
    """

    def __init__(self, name: str, parent: Optional["Namespace"] = None):
        """初始化命名空间.

        Args:
            name: 命名空间名称
            parent: 父命名空间（可选）
        """
        self.name = name
        self.parent = parent
        self._variables: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """设置变量值.

        Args:
            key: 变量名
            value: 变量值
        """
        self._variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取变量值.

        如果在当前命名空间找不到，会递归查找父命名空间。

        Args:
            key: 变量名
            default: 默认值

        Returns:
            变量值，如果找不到则返回默认值
        """
        if key in self._variables:
            return self._variables[key]
        if self.parent:
            return self.parent.get(key, default)
        return default

    def has(self, key: str) -> bool:
        """检查变量是否存在.

        Args:
            key: 变量名

        Returns:
            存在返回 True，否则返回 False
        """
        if key in self._variables:
            return True
        if self.parent:
            return self.parent.has(key)
        return False

    def delete(self, key: str) -> bool:
        """删除变量.

        Args:
            key: 变量名

        Returns:
            删除成功返回 True，不存在返回 False
        """
        if key in self._variables:
            del self._variables[key]
            return True
        return False

    def clear(self) -> None:
        """清空所有变量."""
        self._variables.clear()

    def get_all(self) -> Dict[str, Any]:
        """获取所有变量.

        Returns:
            变量字典的副本
        """
        result = {}
        if self.parent:
            result.update(self.parent.get_all())
        result.update(self._variables)
        return result

    def fork(self, child_name: str) -> "Namespace":
        """创建子命名空间.

        Args:
            child_name: 子命名空间名称

        Returns:
            新的子 Namespace 实例
        """
        return Namespace(child_name, parent=self)
