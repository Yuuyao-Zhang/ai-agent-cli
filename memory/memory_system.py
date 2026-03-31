"""渐进式记忆系统 (Progressive Memory System).

实现短期、中期、长期三层记忆存储，以及智能检索系统。
"""

from typing import Dict, Any, Optional
from .stores.short_term import ShortTermStore
from .stores.mid_term import MidTermStore
from .stores.long_term import LongTermStore
from .retriever.engine import Retriever
from .vector.tf_vectorizer import QwenVectorizer


class MemorySystem:
    """渐进式记忆系统主类."""

    def __init__(self, session_id: str = "default",
                 short_term_size: int = 20,
                 db_path: str = "memory.db",
                 vector_path: str = "vectors.pkl",
                 log_path: str = "logs.jsonl"):
        """初始化记忆系统.

        Args:
            session_id: 会话ID
            short_term_size: 短期记忆最大轮数
            db_path: 中期记忆数据库路径
            vector_path: 长期记忆向量索引路径
            log_path: 长期记忆原始日志路径
        """
        self.session_id = session_id
        self.short_term = ShortTermStore(max_rounds=short_term_size)
        self.mid_term = MidTermStore(db_path=db_path)
        self.long_term = LongTermStore(index_path=vector_path, log_path=log_path)
        self.vectorizer = QwenVectorizer()
        self.retriever = Retriever(
            short_term=self.short_term,
            mid_term=self.mid_term,
            long_term=self.long_term,
            vectorizer=self.vectorizer
        )
        self._round_counter = 0
        self.llm_client = None  # 待注入

    def set_llm_client(self, client: Any) -> None:
        """注入 LLM 客户端用于生成摘要和查询重写.

        Args:
            client: LLM 客户端对象
        """
        self.llm_client = client
        self.retriever.set_llm_client(client)

    def add_memory(self, content: str, role: str = "user",
                   metadata: Optional[Dict] = None) -> int:
        """添加记忆到所有层级：短期、长期（向量+日志）.

        Args:
            content: 记忆内容
            role: 角色 (user/assistant)
            metadata: 附加元数据

        Returns:
            轮次ID
        """
        self._round_counter += 1
        round_id = self._round_counter

        # 1. 短期存储
        self.short_term.add(round_id, content, role)

        # 2. 长期存储 - 向量化
        embedding = self.vectorizer.embed(content)
        self.long_term.store_vector(round_id, embedding, {
            "session_id": self.session_id,
            "role": role,
            **(metadata or {})
        })

        # 3. 原始日志存储
        self.long_term.store_raw_log(round_id, {
            "round_id": round_id,
            "session_id": self.session_id,
            "content": content,
            "role": role,
            **(metadata or {})
        })

        # 4. 中期摘要 - 每10轮生成一次
        if self._round_counter % 10 == 0:
            self._generate_summary(round_id - 9, round_id)

        return round_id

    def get_context(self, query: str) -> str:
        """渐进式披露：根据查询获取相关上下文.

        Args:
            query: 查询内容

        Returns:
            相关上下文字符串
        """
        return self.retriever.retrieve(query, self.session_id)

    def _generate_summary(self, round_start: int, round_end: int) -> None:
        """为指定范围的轮次生成摘要（需要LLM）.

        Args:
            round_start: 起始轮次
            round_end: 结束轮次
        """
        if not self.llm_client:
            # 占位符：生产环境中，这将排队任务或调用LLM
            print(
                f"[MemorySystem] 警告：未设置LLM客户端。跳过轮次 {round_start}-{round_end} 的摘要生成。"
            )
            return

        # 获取范围内的原始日志
        logs = []
        for rid in range(round_start, round_end + 1):
            log = self.long_term.get_raw_log(rid)
            if log:
                logs.append(f"{log['role']}: {log['content']}")

        conversation_text = "\n".join(logs)

        # LLM 提示示例
        prompt = f"请简要总结以下对话：\n{conversation_text}"

        try:
            # 假设 llm_client 有简单的聊天接口
            # 这是模拟实现细节
            summary = self.llm_client.chat(prompt)

            # 将摘要存储在中期存储中
            self.mid_term.update_summary(
                session_id=self.session_id,
                round_start=round_start,
                round_end=round_end,
                summary=summary
            )
        except Exception as e:
            print(f"[MemorySystem] 生成摘要时出错：{e}")
