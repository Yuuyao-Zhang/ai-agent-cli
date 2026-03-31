"""记忆模块初始化.

统一记忆系统，包含短期、中期、长期三层记忆，
以及提示词模板管理、钩子系统整合等功能。
"""

from .types import (
    MemoryType,
    MemoryEntry,
    MemoryStats,
    SummaryEntry,
    PromptTemplate
)
from .manager import MemoryManager
from .stores import (
    MemoryStore,
    ShortTermStore,
    MidTermStore,
    LongTermStore
)
from .unified_manager import UnifiedMemoryManager, create_memory_manager
from .prompts import PromptManager, prompt_manager
from .memory_system import MemorySystem
from .retriever import (
    RetrievalTrigger,
    QueryRewriter,
    Reranker,
    Retriever
)
from .vector import QwenVectorizer, cosine_similarity

__all__ = [
    "MemoryType",
    "MemoryEntry",
    "MemoryStats",
    "SummaryEntry",
    "PromptTemplate",
    "MemoryManager",
    "MemoryStore",
    "ShortTermStore",
    "MidTermStore",
    "LongTermStore",
    "UnifiedMemoryManager",
    "create_memory_manager",
    "PromptManager",
    "prompt_manager",
    "MemorySystem",
    "RetrievalTrigger",
    "QueryRewriter",
    "Reranker",
    "Retriever",
    "QwenVectorizer",
    "cosine_similarity"
]
