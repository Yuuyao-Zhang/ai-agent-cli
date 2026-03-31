"""长期记忆存储.

整合向量索引和原始日志存储。
"""

import json
import pickle
import os
from typing import List, Dict, Any, Optional
from .base import MemoryStore
from ..vector.similarity import cosine_similarity


class LongTermStore(MemoryStore):
    """长期记忆存储类."""

    def __init__(self, index_path: str = "vectors.pkl",
                 log_path: str = "logs.jsonl"):
        """初始化长期记忆存储.

        Args:
            index_path: 向量索引文件路径
            log_path: 原始日志文件路径
        """
        self.index_path = index_path
        self.log_path = log_path
        self.vectors = self._load_vectors()

    def _load_vectors(self) -> List[Dict[str, Any]]:
        """从磁盘加载向量.

        Returns:
            向量列表
        """
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return []
        return []

    def _save_vectors(self) -> None:
        """保存向量到磁盘."""
        # 确保目录存在
        dir_path = os.path.dirname(self.index_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        with open(self.index_path, 'wb') as f:
            pickle.dump(self.vectors, f)

    def store_vector(self, round_id: int, embedding: List[float],
                      metadata: Dict[str, Any]) -> bool:
        """存储向量.

        Args:
            round_id: 轮次ID
            embedding: 向量列表
            metadata: 元数据

        Returns:
            是否存储成功
        """
        self.vectors.append({
            "round_id": round_id,
            "embedding": embedding,
            "metadata": metadata
        })
        self._save_vectors()
        return True

    def store_raw_log(self, round_id: int, content: Dict[str, Any]) -> bool:
        """存储原始日志.

        Args:
            round_id: 轮次ID
            content: 日志内容

        Returns:
            是否存储成功
        """
        # 确保目录存在
        dir_path = os.path.dirname(self.log_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        with open(self.log_path, 'a', encoding='utf-8') as f:
            # 如果内容中没有round_id则添加
            if "round_id" not in content:
                content["round_id"] = round_id
            f.write(json.dumps(content, ensure_ascii=False) + '\n')
        return True

    def get_raw_log(self, round_id: int) -> Optional[Dict[str, Any]]:
        """获取原始日志.

        Args:
            round_id: 轮次ID

        Returns:
            原始日志内容
        """
        if not os.path.exists(self.log_path):
            return None

        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get("round_id") == round_id:
                        return record
                except json.JSONDecodeError:
                    continue
        return None

    def search_vectors(self, query_vector: List[float],
                       top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索向量.

        Args:
            query_vector: 查询向量
            top_k: 返回数量

        Returns:
            搜索结果列表
        """
        scored = []
        for item in self.vectors:
            # item["embedding"]应该是浮点数列表
            score = cosine_similarity(query_vector, item["embedding"])
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        # 返回top_k结果并添加分数
        return [{"score": s, **item} for s, item in scored[:top_k]]

    # MemoryStore接口实现
    def add(self, *args, **kwargs) -> bool:
        """通用add可以根据参数分派到向量或日志存储
        但为了清晰起见，应该使用特定的方法。
        这只是为了满足抽象基类的要求（如果需要）。

        Returns:
            是否添加成功
        """
        return False

    def get(self, *args, **kwargs) -> Any:
        """获取记忆.

        Returns:
            记忆内容
        """
        return None

    def clear(self) -> bool:
        """清空长期记忆.

        Returns:
            是否清空成功
        """
        self.vectors = []
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        return True
