"""Qwen 向量化器模块."""

from typing import List

from llm.llm import call_qwen_embedding


class QwenVectorizer:
    """Qwen 向量化器.

    使用通义千问的 Embedding API 将文本转换为向量。
    """

    def __init__(self, model: str = "text-embedding-v4"):
        """初始化 Qwen 向量化器.

        Args:
            model: Embedding 模型名称
        """
        self.model = model

    def embed(self, text: str) -> List[float]:
        """将文本转换为向量.

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        if not text:
            return []
        return call_qwen_embedding(text, model=self.model)
