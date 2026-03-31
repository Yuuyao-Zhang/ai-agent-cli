"""渐进式检索引擎.

实现高级RAG检索策略：查询重写 + 重排序。
"""

from typing import Any
from ..stores.short_term import ShortTermStore
from ..stores.mid_term import MidTermStore
from ..stores.long_term import LongTermStore
from ..vector.tf_vectorizer import QwenVectorizer
from .trigger import RetrievalTrigger
from .rewriter import QueryRewriter
from .reranker import Reranker


class Retriever:
    """渐进式检索器."""

    def __init__(self, short_term: ShortTermStore,
                 mid_term: MidTermStore,
                 long_term: LongTermStore,
                 vectorizer: QwenVectorizer,
                 similarity_threshold: float = 0.5):
        """初始化检索器.

        Args:
            short_term: 短期存储
            mid_term: 中期存储
            long_term: 长期存储
            vectorizer: 向量化器
            similarity_threshold: 相似度阈值
        """
        self.short_term = short_term
        self.mid_term = mid_term
        self.long_term = long_term
        self.vectorizer = vectorizer
        self.trigger = RetrievalTrigger()
        self.similarity_threshold = similarity_threshold

        # 高级RAG组件
        self.rewriter = QueryRewriter()  # 稍后需要注入LLM客户端
        self.reranker = Reranker(
            vector_weight=0.5,
            keyword_weight=0.3,
            recency_weight=0.2
        )

    def set_llm_client(self, client: Any) -> None:
        """注入LLM客户端到重写器.

        Args:
            client: LLM客户端对象
        """
        self.rewriter.llm_client = client

    def retrieve(self, query: str, session_id: str = "default") -> str:
        """渐进式检索策略（高级RAG：重写+重排序）.

        1. 检查触发词
        2. 重写查询 -> 多种变体
        3. L1: 在所有变体的摘要（中期）中搜索
        4. L2: 对所有变体进行向量搜索（长期）-> 聚合候选
        5. 重排序候选
        6. L3: 获取顶部重排序匹配的原始日志

        Args:
            query: 查询内容
            session_id: 会话ID

        Returns:
            相关上下文字符串
        """
        # 步骤1: 检查触发词
        if not self.trigger.should_retrieve(query):
            return ""

        context_parts = []

        # 步骤2: 查询重写
        queries = self.rewriter.rewrite(query)
        # 去重查询，同时保留顺序
        unique_queries = list(dict.fromkeys(queries))

        # 步骤3: L1 - 中期摘要搜索（为了节省时间只对原始查询，还是所有？）
        all_summaries = []
        seen_summary_ids = set()

        for q in unique_queries:
            sums = self.mid_term.search_summaries(q, session_id)
            for s in sums:
                if s['id'] not in seen_summary_ids:
                    all_summaries.append(s)
                    seen_summary_ids.add(s['id'])

        if all_summaries:
            context_parts.append("=== 相关摘要 ===")
            for s in all_summaries[:3]:  # 限制为前3个摘要
                context_parts.append(f"[{s['created_at'][:10]}] {s['summary']}")

        # 步骤4: L2 - 向量搜索和聚合
        candidates = {}  # 映射 round_id -> candidate_item

        for q in unique_queries:
            query_vector = self.vectorizer.embed(q)
            # 检索更多候选（top_k=10）以允许重排序器筛选
            vector_results = self.long_term.search_vectors(query_vector, top_k=10)

            for v in vector_results:
                rid = v['round_id']
                # 如果多次看到同一轮（来自不同的查询变体），
                # 保留最高的向量分数。
                if rid not in candidates or v['score'] > candidates[rid]['score']:
                    # 我们需要为重排序关键词评分获取内容
                    # 乐观地检查内容是否在元数据中，否则现在获取原始日志？
                    # 当前向量存储在search_vectors中不返回内容，只返回元数据。
                    # 我们需要获取原始日志内容以进行关键词重排序。
                    raw_log = self.long_term.get_raw_log(rid)
                    if raw_log:
                        v['content'] = raw_log.get('content', '')
                        v['role'] = raw_log.get('role', 'unknown')
                        candidates[rid] = v

        candidate_list = list(candidates.values())

        # 步骤5: 重排序
        # 使用所有唯一查询进行重排序以捕获同义词
        reranked_results = self.reranker.rerank(unique_queries, candidate_list)

        # 按最终分数阈值筛选（可选，或者只取前K）
        final_results = [
            r for r in reranked_results
            if r['rerank_score'] >= self.similarity_threshold
        ]

        if final_results:
            context_parts.append("\n=== 相关对话历史 ===")

            # 重排序后取前5个
            for v in final_results[:5]:
                round_id = v['round_id']
                role = v.get('role', 'unknown')
                content = v.get('content', '')
                # 调试信息
                # context_parts.append(
                #     f"[调试] 分数: {v['rerank_score']:.2f} "
                #     f"(向量:{v['_debug_scores']['vector']:.2f})"
                # )
                context_parts.append(f"[轮次 {round_id}] {role}: {content}")

        if not context_parts:
            return ""

        return "\n".join(context_parts)
