"""知识管理模块.

该模块提供向量数据库集成和知识管理功能。
"""

from knowledge.vector_db import VectorDatabase, KnowledgeEntry
from knowledge.manager import KnowledgeManager, knowledge_manager

__all__ = ["VectorDatabase", "KnowledgeEntry", "KnowledgeManager", "knowledge_manager"]
