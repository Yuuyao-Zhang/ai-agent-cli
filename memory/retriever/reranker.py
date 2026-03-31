"""重排序器模块.

基于混合评分策略重排序候选结果：
1. 向量相似度（语义匹配）
2. 关键词密度（精确匹配）
3. 时效性（时间相关性）
"""

from typing import List, Dict, Any


class Reranker:
    """重排序器类."""

    def __init__(self,
                 vector_weight: float = 0.5,
                 keyword_weight: float = 0.3,
                 recency_weight: float = 0.2):
        """初始化重排序器.

        Args:
            vector_weight: 向量相似度权重
            keyword_weight: 关键词密度权重
            recency_weight: 时效性权重
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.recency_weight = recency_weight

    def rerank(self, queries: List[str], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """重排序候选.

        Args:
            queries: 字符串列表（原始查询 + 变体）
            candidates: 包含内容、分数等的字典列表

        Returns:
            重排序后的候选列表
        """
        if not candidates:
            return []

        max_round_id = max((c.get('round_id', 0) for c in candidates), default=1)

        # 从所有查询变体中收集所有唯一词进行广泛匹配
        all_query_words = set()
        for q in queries:
            all_query_words.update(q.lower().split())

        reranked_results = []

        for item in candidates:
            # 1. 向量分数（已计算）
            vec_score = item.get('score', 0.0)

            # 2. 关键词密度分数（跨任何查询变体的最大匹配）
            content_lower = item.get('content', '').lower()
            content_words = set(content_lower.split())

            if not content_words or not all_query_words:
                kw_score = 0.0
            else:
                # 对所有查询变体的联合进行Jaccard相似度
                # 如果任何同义词匹配，这会给予分数
                # intersection = len(all_query_words.intersection(content_words))

                # 更好的方法：对每个单独查询的最大查询覆盖率？
                # 覆盖率 = 交集 / 长度(查询)

                max_coverage = 0.0
                for q in queries:
                    q_words = set(q.lower().split())
                    if not q_words:
                        continue
                    inter = len(q_words.intersection(content_words))
                    # 使用查询长度作为分母（覆盖率）
                    # 这会提升匹配长文档的短查询
                    score = inter / len(q_words)
                    if score > max_coverage:
                        max_coverage = score

                kw_score = max_coverage

            # 3. 时效性分数（线性衰减）
            # 较新的消息获得更高分数
            round_id = item.get('round_id', 0)
            # 将round_id标准化到0-1相对于候选中的最大轮次
            recency_score = round_id / max_round_id if max_round_id > 0 else 0.0

            # 混合分数
            final_score = (
                (vec_score * self.vector_weight) +
                (kw_score * self.keyword_weight) +
                (recency_score * self.recency_weight)
            )

            # 存储详细分数用于调试
            item['_debug_scores'] = {
                'vector': vec_score,
                'keyword': kw_score,
                'recency': recency_score,
                'final': final_score
            }
            item['rerank_score'] = final_score
            reranked_results.append(item)

        # 按最终分数降序排序
        reranked_results.sort(key=lambda x: x['rerank_score'], reverse=True)

        return reranked_results
