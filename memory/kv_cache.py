"""语义 KV-Cache 模块.

该模块实现了一个基于语义相似度的键值缓存系统 (Semantic KV-Cache)。
虽然这不是 Transformer 底层的 KV-Cache，但在 Agent 系统层面，它起到了
"缓存思考结果，避免重复计算" 的作用。

实现原理：
1. Key (键): 输入 Prompt 的向量表示 (使用 Qwen Embedding)
2. Value (值): LLM 的响应结果
3. 机制: 当新请求到来时，计算其 Embedding，查找缓存中相似度最高的 Key。
   如果相似度超过阈值，直接返回缓存的 Value。
"""

import time
import json
import os
import hashlib
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

# 复用现有的 VectorIndex
from skill.vector_index import VectorIndex
from skill.types import Skill, DisclosureLevel


@dataclass
class CacheEntry:
    """缓存条目."""
    query_text: str
    response_text: str
    timestamp: float
    access_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticKVCache:
    """语义键值缓存管理器."""

    def __init__(self, cache_dir: str = ".cache", threshold: float = 0.95):
        """初始化缓存管理器.

        Args:
            cache_dir: 缓存存储目录
            threshold: 语义相似度阈值 (0.0 - 1.0)，超过此值才视为命中
        """
        self.cache_dir = cache_dir
        self.threshold = threshold
        self.entries: Dict[str, CacheEntry] = {}
        self.vector_index = VectorIndex()

        # 简单的内存中索引，用于重建 VectorIndex
        # 这里我们将 CacheEntry 伪装成 Skill 对象以便复用 VectorIndex 的接口
        self._virtual_skills: List[Skill] = []

        self._load_cache()

    def _load_cache(self):
        """从磁盘加载缓存."""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            return

        cache_file = os.path.join(self.cache_dir, "kv_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, item in data.items():
                        self.entries[key] = CacheEntry(
                            query_text=item["query_text"],
                            response_text=item["response_text"],
                            timestamp=item["timestamp"],
                            access_count=item.get("access_count", 1),
                            metadata=item.get("metadata", {})
                        )
                self._rebuild_index()
            except Exception as e:
                print(f"[KV-Cache] 加载失败：{e}")

    def _save_cache(self):
        """保存缓存到磁盘."""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

        cache_file = os.path.join(self.cache_dir, "kv_cache.json")
        data = {
            k: {
                "query_text": v.query_text,
                "response_text": v.response_text,
                "timestamp": v.timestamp,
                "access_count": v.access_count,
                "metadata": v.metadata
            }
            for k, v in self.entries.items()
        }
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[KV-Cache] 保存失败：{e}")

    def _rebuild_index(self):
        """重建向量索引."""
        self._virtual_skills = []
        for key, entry in self.entries.items():
            # 将 CacheEntry 包装成 Skill 对象
            # Skill.name -> key (hash)
            # Skill.description -> query_text
            # 其他字段留空
            skill = Skill(
                name=key,
                description=entry.query_text,
                summary="", content="", parameters=[], examples=[], hints=[],
                dependencies=[], tags=[], category="cache"
            )
            self._virtual_skills.append(skill)

        self.vector_index.rebuild(self._virtual_skills)

    def get(self, query: str) -> Optional[str]:
        """查找缓存.

        Args:
            query: 查询文本 (Prompt)

        Returns:
            缓存的响应文本，未命中返回 None
        """
        if not self.entries:
            return None

        # 使用 VectorIndex 搜索
        # search 返回 List[Tuple[Skill, float]]
        results = self.vector_index.search(query, top_k=1, level=DisclosureLevel.BRIEF)

        if not results:
            return None

        best_skill, score = results[0]

        if score >= self.threshold:
            entry = self.entries.get(best_skill.name)
            if entry:
                entry.access_count += 1
                entry.timestamp = time.time()  # 更新访问时间
                self._save_cache()  # 简单起见，每次命中都保存访问计数
                return entry.response_text

        return None

    def set(self, query: str, response: str):
        """写入缓存.

        Args:
            query: 查询文本
            response: 响应文本
        """
        # 生成唯一 Key (MD5 of query)
        key = hashlib.md5(query.encode("utf-8")).hexdigest()

        self.entries[key] = CacheEntry(
            query_text=query,
            response_text=response,
            timestamp=time.time()
        )

        self._save_cache()
        self._rebuild_index()


# 全局单例
kv_cache = SemanticKVCache()
