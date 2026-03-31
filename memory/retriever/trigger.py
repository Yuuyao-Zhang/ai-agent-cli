"""检索触发器模块.

检测查询是否需要检索记忆的触发词。
"""


class RetrievalTrigger:
    """检索触发器类."""

    # 记忆召回的常见触发词
    TRIGGERS = [
        "之前", "记得", "第", "上次", "回顾", "以前", "说过",
        "before", "remember", "round", "last", "recall", "previously", "said"
    ]

    def should_retrieve(self, query: str) -> bool:
        """检查查询是否包含任何触发词，表示需要记忆检索.

        Args:
            query: 查询文本

        Returns:
            是否需要检索
        """
        if not query:
            return False

        query_lower = query.lower()
        # 简单关键词匹配
        # 可以用正则表达式增强，用于特定模式如"Round X"
        return any(t in query_lower for t in self.TRIGGERS)
