"""向量模块.

包含词频向量化器和相似度计算等组件。
"""

from .tf_vectorizer import QwenVectorizer
from .similarity import cosine_similarity

__all__ = [
    'QwenVectorizer',
    'cosine_similarity',
]
