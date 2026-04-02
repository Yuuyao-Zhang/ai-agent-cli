"""向量数据库模块.

基于 Qwen Embedding 的向量数据库实现，提供知识的存储、检索和相似度搜索功能。
使用余弦相似度算法计算向量距离，支持元数据和标签管理。
"""

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from llm.llm import call_qwen_embedding


@dataclass
class KnowledgeEntry:
    """知识条目数据类.

    Attributes:
        id: 唯一标识符
        content: 知识内容文本
        metadata: 元数据字典
        tags: 标签列表
        timestamp: 时间戳
    """

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    timestamp: float = 0.0


class VectorDatabase:
    """基于 Qwen Embedding 的向量数据库.

    提供知识的添加、搜索、删除和列表功能，支持相似度检索。
    """

    def __init__(self, storage_dir: str = "vectordb"):
        """初始化向量数据库.

        Args:
            storage_dir: 数据存储目录
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.entries: Dict[str, KnowledgeEntry] = {}
        self.embeddings: Dict[str, List[float]] = {}

        self._load()

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度.

        Args:
            vec1: 第一个向量
            vec2: 第二个向量

        Returns:
            相似度分数，范围 [-1, 1]
        """
        if not vec1 or not vec2:
            return 0.0
        if len(vec1) != len(vec2):
            min_len = min(len(vec1), len(vec2))
            if min_len == 0:
                return 0.0
            vec1 = vec1[:min_len]
            vec2 = vec2[:min_len]

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    @staticmethod
    def _generate_id(content: str) -> str:
        """根据内容生成哈希ID.

        Args:
            content: 内容文本

        Returns:
            16位哈希ID
        """
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]

    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        entry_id: Optional[str] = None
    ) -> str:
        """添加知识条目.

        Args:
            content: 知识内容
            metadata: 元数据
            tags: 标签列表
            entry_id: 可选的显式条目 ID

        Returns:
            知识条目 ID
        """
        entry_id = entry_id or VectorDatabase._generate_id(content)

        if entry_id in self.entries:
            return entry_id

        embedding = call_qwen_embedding(content)
        if not embedding:
            return ""

        entry = KnowledgeEntry(
            id=entry_id,
            content=content,
            metadata=metadata or {},
            tags=tags or [],
            timestamp=time.time(),
        )

        self.entries[entry_id] = entry
        self.embeddings[entry_id] = embedding
        self._save()

        return entry_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        tags: Optional[List[str]] = None
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """搜索相关知识条目.

        Args:
            query: 查询文本
            top_k: 返回最相关的 K 个结果
            tags: 标签过滤

        Returns:
            (知识条目, 相似度) 列表，按相似度降序排列
        """
        if not self.entries:
            return []

        query_vec = call_qwen_embedding(query)
        if not query_vec:
            return []

        results = []
        for entry_id, entry in self.entries.items():
            if tags and not any(tag in entry.tags for tag in tags):
                continue

            entry_vec = self.embeddings.get(entry_id, [])
            if not entry_vec:
                continue
            similarity = VectorDatabase._cosine_similarity(query_vec, entry_vec)

            if similarity > 0:
                results.append((entry, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """获取知识条目.

        Args:
            entry_id: 条目 ID

        Returns:
            知识条目，如果不存在则返回 None
        """
        return self.entries.get(entry_id)

    def delete(self, entry_id: str) -> bool:
        """删除知识条目.

        Args:
            entry_id: 条目 ID

        Returns:
            是否删除成功
        """
        if entry_id not in self.entries:
            return False

        del self.entries[entry_id]
        if entry_id in self.embeddings:
            del self.embeddings[entry_id]
        self._save()
        return True

    def list_all(self) -> List[KnowledgeEntry]:
        """列出所有知识条目.

        Returns:
            知识条目列表
        """
        return list(self.entries.values())

    def _save(self) -> None:
        """保存数据到文件."""
        data = {
            "entries": [
                {
                    "id": e.id,
                    "content": e.content,
                    "metadata": e.metadata,
                    "tags": e.tags,
                    "timestamp": e.timestamp,
                }
                for e in self.entries.values()
            ],
            "embeddings": self.embeddings,
        }

        with open(self.storage_dir / "data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """从文件加载数据."""
        data_file = self.storage_dir / "data.json"
        if not data_file.exists():
            return

        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                entry = KnowledgeEntry(
                    id=entry_data["id"],
                    content=entry_data["content"],
                    metadata=entry_data.get("metadata", {}),
                    tags=entry_data.get("tags", []),
                    timestamp=entry_data.get("timestamp", 0.0),
                )
                self.entries[entry.id] = entry

            stored_embeddings = data.get("embeddings", {})
            if isinstance(stored_embeddings, dict):
                self.embeddings = {
                    key: value for key, value in stored_embeddings.items()
                    if isinstance(value, list)
                }

            if not self.embeddings and self.entries:
                for entry_id, entry in self.entries.items():
                    embedding = call_qwen_embedding(entry.content)
                    if embedding:
                        self.embeddings[entry_id] = embedding
                self._save()
        except Exception as e:
            print(f"[Warning] Failed to load vector DB: {e}")
