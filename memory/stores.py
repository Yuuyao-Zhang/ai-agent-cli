"""统一的记忆存储系统.

整合短期、中期、长期三层记忆存储。
"""

import collections
import sqlite3
import time
import pickle
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Deque
from abc import ABC, abstractmethod




class MemoryStore(ABC):
    """记忆存储基类."""

    @abstractmethod
    def add(self, *args, **kwargs) -> bool:
        """添加记忆条目."""
        pass

    @abstractmethod
    def get(self, *args, **kwargs) -> Any:
        """获取记忆条目."""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空所有记忆."""
        pass


class ShortTermStore(MemoryStore):
    """短期记忆存储.

    使用双端队列实现有限大小的活跃窗口。
    """

    def __init__(self, max_rounds: int = 20):
        """初始化短期记忆存储.

        Args:
            max_rounds: 最大轮数
        """
        self.max_rounds = max_rounds
        self.buffer: Deque[Dict[str, Any]] = collections.deque(maxlen=max_rounds)

    def add(self, round_id: int, content: str, role: str = "user") -> bool:
        """添加新的交互到短期记忆.

        Args:
            round_id: 轮次ID
            content: 内容
            role: 角色 (user/assistant)

        Returns:
            是否添加成功
        """
        self.buffer.append({
            "round_id": round_id,
            "content": content,
            "role": role,
            "timestamp": time.time()
        })
        return True

    def get(self, n: int = None) -> List[Dict[str, Any]]:
        """获取最近的n条交互.

        Args:
            n: 数量，默认为全部

        Returns:
            记忆条目列表
        """
        n = n or self.max_rounds
        if n > len(self.buffer):
            return list(self.buffer)
        return list(self.buffer)[-n:]

    def get_recent(self, n: int = None) -> List[Dict[str, Any]]:
        """get()的别名.

        Args:
            n: 数量

        Returns:
            记忆条目列表
        """
        return self.get(n)

    def clear(self) -> bool:
        """清空短期记忆.

        Returns:
            是否清空成功
        """
        self.buffer.clear()
        return True


class MidTermStore(MemoryStore):
    """中期记忆存储.

    使用SQLite数据库存储结构化摘要。
    """

    def __init__(self, db_path: str = "memory_mid.db"):
        """初始化中期记忆存储.

        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self) -> None:
        """初始化数据库表."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                round_start INTEGER NOT NULL,
                round_end INTEGER NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                keywords TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session ON summaries(session_id)')
        self.conn.commit()

    def update_summary(self, session_id: str, round_start: int,
                       round_end: int, summary: str, keywords: str = "") -> bool:
        """更新或创建摘要.

        Args:
            session_id: 会话ID
            round_start: 起始轮次
            round_end: 结束轮次
            summary: 摘要内容
            keywords: 关键词

        Returns:
            是否更新成功
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO summaries (session_id, round_start, round_end, summary, created_at, keywords)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, round_start, round_end, summary,
              datetime.now().isoformat(), keywords))
        self.conn.commit()
        return True

    def search_summaries(self, query: str, session_id: Optional[str] = None,
                         time_range: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """搜索摘要.

        Args:
            query: 查询文本
            session_id: 会话ID
            time_range: 时间范围 (start_time, end_time)

        Returns:
            匹配的摘要列表
        """
        cursor = self.conn.cursor()
        sql = "SELECT * FROM summaries WHERE 1=1"
        params = []

        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)

        if time_range:
            start_time, end_time = time_range
            sql += " AND created_at BETWEEN ? AND ?"
            params.extend([start_time, end_time])

        # 简单关键词匹配
        if query:
            keywords = query.split()
            if keywords:
                conditions = []
                for keyword in keywords:
                    conditions.append("(summary LIKE ? OR keywords LIKE ?)")
                    params.extend([f"%{keyword}%", f"%{keyword}%"])
                sql += " AND (" + " OR ".join(conditions) + ")"

        cursor.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # MemoryStore接口实现
    def add(self, *args, **kwargs) -> bool:
        """添加摘要.

        Returns:
            是否添加成功
        """
        return self.update_summary(*args, **kwargs)

    def get(self, *args, **kwargs) -> Any:
        """获取摘要.

        Returns:
            摘要列表
        """
        return self.search_summaries(*args, **kwargs)

    def clear(self) -> bool:
        """清空中期记忆.

        Returns:
            是否清空成功
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM summaries")
        self.conn.commit()
        return True


class LongTermStore(MemoryStore):
    """长期记忆存储.

    整合向量索引和原始日志存储。
    """

    def __init__(self, index_path: str = "vectors.pkl", log_path: str = "logs.jsonl"):
        """初始化长期记忆存储.

        Args:
            index_path: 向量索引文件路径
            log_path: 原始日志文件路径
        """
        self.index_path = index_path
        self.log_path = log_path
        self.vectors: Dict[int, List[float]] = {}
        self.metadata: Dict[int, Dict[str, Any]] = {}
        self.raw_logs: Dict[int, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """从磁盘加载数据."""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'rb') as f:
                    data = pickle.load(f)
                    self.vectors = data.get('vectors', {})
                    self.metadata = data.get('metadata', {})
            except Exception:
                pass

        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            log = json.loads(line)
                            self.raw_logs[log['round_id']] = log
            except Exception:
                pass

    def _save(self):
        """保存数据到磁盘."""
        with open(self.index_path, 'wb') as f:
            pickle.dump({
                'vectors': self.vectors,
                'metadata': self.metadata
            }, f)

    def store_vector(self, round_id: int, vector: List[float], meta: Dict[str, Any] = None):
        """存储向量.

        Args:
            round_id: 轮次ID
            vector: 向量列表
            meta: 元数据
        """
        self.vectors[round_id] = vector
        self.metadata[round_id] = meta or {}
        self._save()

    def store_raw_log(self, round_id: int, log: Dict[str, Any]):
        """存储原始日志.

        Args:
            round_id: 轮次ID
            log: 日志内容
        """
        self.raw_logs[round_id] = log
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log, ensure_ascii=False) + '\n')

    def search_vectors(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索向量.

        Args:
            query_vector: 查询向量
            top_k: 返回数量

        Returns:
            搜索结果列表
        """
        if not self.vectors:
            return []

        # 简单余弦相似度
        results = []
        for rid, vec in self.vectors.items():
            score = self._cosine_similarity(query_vector, vec)
            results.append({
                'round_id': rid,
                'score': score,
                **self.metadata.get(rid, {})
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def get_raw_log(self, round_id: int) -> Optional[Dict[str, Any]]:
        """获取原始日志.

        Args:
            round_id: 轮次ID

        Returns:
            原始日志内容
        """
        return self.raw_logs.get(round_id)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度.

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            相似度分数
        """
        return LongTermStore.calculate_cosine_similarity(vec1, vec2)

    @staticmethod
    def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度.

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            相似度分数
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    # MemoryStore接口实现
    def add(self, *args, **kwargs) -> bool:
        """添加长期记忆.

        Returns:
            是否添加成功
        """
        # 该方法需根据实际调用方式调整
        return True

    def get(self, *args, **kwargs) -> Any:
        """获取长期记忆.

        Returns:
            记忆内容
        """
        return self.search_vectors(*args, **kwargs)

    def clear(self) -> bool:
        """清空长期记忆.

        Returns:
            是否清空成功
        """
        self.vectors.clear()
        self.metadata.clear()
        self.raw_logs.clear()
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        return True
