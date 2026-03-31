"""向量相似度计算模块."""

import math
from typing import List


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算余弦相似度.
    
    Args:
        vec1: 向量1
        vec2: 向量2
        
    Returns:
        相似度分数 (0.0-1.0)
    """
    if len(vec1) != len(vec2) or len(vec1) == 0:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)
