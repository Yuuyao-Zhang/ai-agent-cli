"""中期记忆存储.

使用SQLite数据库存储结构化摘要。
"""

import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from .base import MemoryStore


class MidTermStore(MemoryStore):
    """中期记忆存储类."""

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
                         time_range: Optional[Tuple[str, str]] = None) -> List[Dict[str, Any]]:
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
        
        # TODO：添加更复杂的查询逻辑，如模糊关键词匹配
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
