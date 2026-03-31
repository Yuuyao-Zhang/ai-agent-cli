"""查询重写模块.

使用基于LLM的查询扩展来改进召回率。
"""

from typing import List, Any


class QueryRewriter:
    """查询重写器类."""

    def __init__(self, llm_client: Any = None):
        """初始化查询重写器.

        Args:
            llm_client: LLM客户端
        """
        self.llm_client = llm_client

    def rewrite(self, query: str, num_variations: int = 3) -> List[str]:
        """使用LLM将原始查询重写为多个变体.

        Args:
            query: 原始查询
            num_variations: 变体数量

        Returns:
            包含原始查询的列表
        """
        variations = {query}
        query_lower = query.lower()

        # 添加基本的"remember"剥离，专注于内容
        for trigger in ["remember", "recall", "find"]:
            if trigger in query_lower:
                stripped = query_lower.replace(trigger, "").strip()
                if stripped:
                    variations.add(stripped)

        # 基于LLM的重写
        if self.llm_client:
            try:
                prompt = (
                    f"将以下搜索查询重写为 {num_variations} 个不同的版本，"
                    f"以提高检索召回率。专注于同义词和相关概念。"
                    f"只输出重写的查询，每行一个。\n\n"
                    f"查询: {query}"
                )

                # 检查llm_client是函数（如call_qwen）还是对象
                if callable(self.llm_client):
                    messages = [{"role": "user", "content": prompt}]
                    response = self.llm_client(messages)
                elif hasattr(self.llm_client, 'chat'):
                    response = self.llm_client.chat(prompt)
                else:
                    response = ""

                if response:
                    for line in response.strip().split('\n'):
                        line = line.strip()
                        # 如果有编号则移除（例如"1. query"）
                        if line and line[0].isdigit() and '. ' in line[:4]:
                            line = line.split('. ', 1)[1]
                        if line:
                            variations.add(line)

            except Exception:
                # 回退或记录错误
                # print(f"重写器错误: {e}")
                pass

        return list(variations)
