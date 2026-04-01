"""统一记忆系统管理器.

整合三层记忆存储、钩子系统(AOP)和LLM调用。
"""

import os
import re
import time
from typing import List, Dict, Optional, Tuple
from state.session import Session
from common.config import config
from llm.context import estimate_tokens
from llm.llm import call_qwen
from engine.hooks import HookChain, HookContext, HookType

from .types import MemoryStats
from .stores import ShortTermStore, MidTermStore, LongTermStore
from .prompts import prompt_manager
from memory.vector.tf_vectorizer import QwenVectorizer


class TokenPredictor:
    """Token预算预测器."""

    def __init__(self, window_size: int = 5):
        """初始化Token预测器.

        Args:
            window_size: 历史记录窗口大小
        """
        self.history: List[int] = []
        self.window_size = window_size

    def add_sample(self, tokens: int):
        """添加一次Token消耗样本.

        Args:
            tokens: 本次消耗的Token数
        """
        self.history.append(tokens)
        if len(self.history) > self.window_size:
            self.history.pop(0)

    def predict_next(self) -> int:
        """预测下一次交互的Token消耗(简单移动平均).

        Returns:
            预测的Token数
        """
        if not self.history:
            return 500  # 默认预估
        return sum(self.history) // len(self.history)


class UnifiedMemoryManager:
    """统一记忆管理器.

    整合短期、中期、长期记忆，钩子系统和LLM调用。
    """

    def __init__(self, session: Session, session_id: str = "default"):
        """初始化统一记忆管理器.

        Args:
            session: 会话对象
            session_id: 会话ID
        """
        self.session = session
        self.session_id = self._sanitize_session_id(session_id)
        self.token_predictor = TokenPredictor()
        self.hooks = HookChain()
        self.storage_dir = os.path.join(os.getcwd(), ".my_agent", "memory")
        os.makedirs(self.storage_dir, exist_ok=True)

        # 配置参数
        self.summary_threshold = 0.8  # 达到80%预算时触发压缩
        self.window_size = 10  # 保持最近N轮对话不被摘要
        self.summary_interval = 10  # 每10轮生成一次摘要

        # 初始化三层记忆存储
        self.short_term = ShortTermStore(max_rounds=config.app.max_turns_per_agent)
        self.mid_term = MidTermStore(
            db_path=os.path.join(self.storage_dir, f"memory_{self.session_id}_mid.db")
        )
        self.long_term = LongTermStore(
            index_path=os.path.join(self.storage_dir, f"memory_{self.session_id}_vectors.pkl"),
            log_path=os.path.join(self.storage_dir, f"memory_{self.session_id}_logs.jsonl")
        )

        self._round_counter = len(self.session.history)

        self.llm_client = None
        self._vectorizer = QwenVectorizer()
        self._hydrate_short_term()

    @property
    def max_tokens(self) -> int:
        """从常量动态获取最大Token数.

        Returns:
            最大Token数
        """
        return config.app.max_total_tokens_per_agent

    def set_llm_client(self, client):
        """设置LLM客户端.

        Args:
            client: LLM客户端
        """
        self.llm_client = client

    def add_message(self, role: str, content: str):
        """添加新消息并触发记忆管理.

        Args:
            role: 消息角色(user/assistant)
            content: 消息内容
        """
        # 执行前置钩子
        hook_ctx = HookContext(
            hook_type=HookType.PRE_LLM,
            task_desc="add_message",
            session=self.session
        )
        self.hooks.execute(HookType.PRE_LLM, hook_ctx)

        self._round_counter += 1
        round_id = self._round_counter

        # 1. 估算Token
        tokens = estimate_tokens(content)
        if role == "assistant":
            self.token_predictor.add_sample(tokens)

        # 2. 存入Session和短期记忆
        self.session.add_message(role, content)
        self.short_term.add(round_id, content, role)

        # 3. 简单向量化并存入长期记忆
        # 注意：这里暂时使用简单哈希作为占位符
        vector = self._simple_vectorize(content)
        self.long_term.store_vector(round_id, vector, {
            "session_id": self.session_id,
            "role": role
        })
        self.long_term.store_raw_log(round_id, {
            "round_id": round_id,
            "session_id": self.session_id,
            "content": content,
            "role": role,
            "timestamp": time.time()
        })

        # 4. 定期生成中期记忆摘要
        if self._round_counter % self.summary_interval == 0:
            self._generate_mid_summary(round_id - self.summary_interval + 1, round_id)

        # 5. 检查是否需要压缩
        self._check_and_compress()

        # 执行后置钩子
        hook_ctx = HookContext(
            hook_type=HookType.POST_LLM,
            task_desc="add_message",
            session=self.session
        )
        self.hooks.execute(HookType.POST_LLM, hook_ctx)

    def get_context(self, query: Optional[str] = None) -> List[Dict[str, str]]:
        """获取构建Prompt用的上下文.

        Args:
            query: 查询文本，用于检索相关记忆

        Returns:
            消息列表，用于构建LLM的Prompt
        """
        messages = []

        # 1. 如果有长期记忆摘要，作为System Prompt
        if self.session.global_summary:
            messages.append({
                "role": "system",
                "content": f"之前对话摘要:\n{self.session.global_summary}"
            })

        # 2. 如果有查询，从三层记忆中检索相关内容
        if query:
            relevant_context, references, searched_types = self._retrieve_relevant(query)
            self.session.set("_memory_context_cache", {
                "query": query,
                "context": relevant_context,
                "references": references,
                "searched_types": searched_types,
            })
            if relevant_context:
                messages.append({
                    "role": "system",
                    "content": f"相关历史:\n{relevant_context}"
                })
        else:
            self.session.set("_memory_context_cache", {
                "query": "",
                "context": "",
                "references": [],
                "searched_types": [],
            })

        # 3. 获取短期记忆(活跃窗口)
        start_idx = self.session.summarized_index
        recent_msgs = self.session.history[start_idx:]

        # 4. 应用上下文剪枝
        pruned_msgs = self._prune_context(recent_msgs)
        messages.extend(pruned_msgs)

        return messages

    def _retrieve_relevant(self, query: str) -> Tuple[str, List[str], List[str]]:
        """检索相关记忆.

        Args:
            query: 查询文本

        Returns:
            相关记忆字符串
        """
        context_parts = []
        references: List[str] = []
        searched_types = ["短期记忆", "中期记忆", "长期记忆"]

        short_results = self._search_short_term(query, top_k=3)
        short_round_ids = {item["round_id"] for item in short_results}
        if short_results:
            context_parts.append("=== 短期记忆命中 ===")
            for item in short_results:
                context_parts.append(
                    f"[短期记忆 | 轮次 {item['round_id']} | {item['role']} | score {item['score']:.2f}] {self._truncate_text(item['content'])}"
                )
                references.append(
                    self._format_memory_reference(
                        "短期记忆",
                        f"轮次 {item['round_id']} | {item['role']}",
                        item["score"],
                    )
                )

        mid_results = self._search_mid_term(query, top_k=3)
        if mid_results:
            context_parts.append("\n=== 中期记忆命中 ===")
            for item in mid_results:
                context_parts.append(
                    f"[中期记忆 | 轮次 {item['round_start']}-{item['round_end']} | {item['created_at'][:10]} | score {item['score']:.2f}] {self._truncate_text(item['summary'])}"
                )
                references.append(
                    self._format_memory_reference(
                        "中期记忆",
                        f"轮次 {item['round_start']}-{item['round_end']} | {item['created_at'][:10]}",
                        item["score"],
                    )
                )

        long_results = self._search_long_term(query, short_round_ids=short_round_ids, top_k=3)
        if long_results:
            context_parts.append("\n=== 长期记忆命中 ===")
            for item in long_results:
                context_parts.append(
                    f"[长期记忆 | 轮次 {item['round_id']} | {item['role']} | score {item['score']:.2f}] {self._truncate_text(item['content'])}"
                )
                references.append(
                    self._format_memory_reference(
                        "长期记忆",
                        f"轮次 {item['round_id']} | {item['role']}",
                        item["score"],
                    )
                )

        deduped_references = []
        seen = set()
        for ref in references:
            if ref in seen:
                continue
            seen.add(ref)
            deduped_references.append(ref)

        return "\n".join(context_parts) if context_parts else "", deduped_references[:6], searched_types

    def _check_and_compress(self):
        """检查Token预算并执行压缩."""
        raw_history = self.session.history
        start_idx = self.session.summarized_index
        active_msgs = raw_history[start_idx:]

        current_tokens = sum(estimate_tokens(m["content"]) for m in active_msgs)
        predicted_next = self.token_predictor.predict_next()

        if current_tokens + predicted_next > self.max_tokens * self.summary_threshold:
            self._summarize_window(active_msgs)

    def _summarize_window(self, msgs: List[Dict[str, str]]):
        """滑动窗口摘要算法.

        Args:
            msgs: 待摘要的消息列表
        """
        if len(msgs) <= 2:
            return  # 消息太少不摘要

        # 保留最近4条作为活跃窗口，压缩前面的
        to_summarize = msgs[:-4]
        if not to_summarize:
            return

        # 提取文本
        text_block = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])

        # 使用提示词模板
        prompt = prompt_manager.render(
            "conversation_summary",
            existing_summary=self.session.global_summary or "",
            conversation=text_block
        )

        try:
            # 调用LLM生成摘要
            messages_list = [{"role": "user", "content": prompt}]
            new_summary = call_qwen(messages_list)

            if new_summary and new_summary.strip():
                self.session.global_summary = new_summary
                current_idx = self.session.summarized_index
                self.session.summarized_index = current_idx + len(to_summarize)
                print(f"[Memory] 已压缩 {len(to_summarize)} 条消息。")
        except Exception as e:
            print(f"[Memory] 摘要生成失败: {e}")

    def _generate_mid_summary(self, round_start: int, round_end: int):
        """生成中期记忆摘要.

        Args:
            round_start: 起始轮次
            round_end: 结束轮次
        """
        # 获取范围内的原始日志
        logs = []
        for rid in range(round_start, round_end + 1):
            log = self.long_term.get_raw_log(rid)
            if log:
                logs.append(f"{log.get('role', 'unknown')}: {log.get('content', '')}")

        if not logs:
            return

        conversation_text = "\n".join(logs)
        prompt = prompt_manager.render(
            "conversation_summary",
            existing_summary="",
            conversation=conversation_text
        )

        try:
            messages_list = [{"role": "user", "content": prompt}]
            summary = call_qwen(messages_list)

            if summary:
                self.mid_term.update_summary(
                    session_id=self.session_id,
                    round_start=round_start,
                    round_end=round_end,
                    summary=summary
                )
        except Exception as e:
            print(f"[Memory] 中期摘要生成失败: {e}")

    def _prune_context(self, msgs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """应用上下文剪枝策略.

        Args:
            msgs: 原始消息列表

        Returns:
            剪枝后的消息列表
        """
        pruned = []
        for msg in msgs:
            content = msg["content"]
            if msg["role"] == "user" and "Tool Results" in content and len(content) > 1000:
                content = content[:200] + "\n...[输出已裁剪]...\n" + content[-200:]
                pruned.append({"role": msg["role"], "content": content})
            else:
                pruned.append(msg)
        return pruned

    def _simple_vectorize(self, text: str, dim: int = 128) -> List[float]:
        """简单向量化文本.

        优先使用Qwen向量化器，失败时使用SHA256哈希作为后备方案。

        Args:
            text: 待向量化的文本
            dim: 向量维度（后备方案使用）

        Returns:
            向量列表
        """
        vec = self._vectorizer.embed(text)
        if vec:
            return vec
        import hashlib
        hb = hashlib.sha256(text.encode('utf-8')).digest()
        v = []
        for i in range(dim):
            bi = i % len(hb)
            val = (hb[bi] / 255.0) * 2 - 1
            v.append(val)
        return v

    @staticmethod
    def _sanitize_session_id(session_id: str) -> str:
        """清理会话ID，使其适合作为文件名.

        移除非法字符，只保留字母、数字、下划线、点和连字符。

        Args:
            session_id: 原始会话ID

        Returns:
            清理后的会话ID
        """
        sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id or "default")
        return sanitized.strip("._") or "default"

    def _hydrate_short_term(self):
        """从会话历史中恢复短期记忆.

        将最近的对话历史加载到短期记忆存储中。
        """
        recent_history = self.session.history[-self.short_term.max_rounds:]
        start_round = max(1, self._round_counter - len(recent_history) + 1)
        for offset, msg in enumerate(recent_history):
            self.short_term.add(
                round_id=start_round + offset,
                content=msg["content"],
                role=msg["role"],
            )

    @staticmethod
    def _tokenize_text(text: str) -> List[str]:
        """简单的文本分词.

        将文本分割为英文单词、数字或中文字符。

        Args:
            text: 待分词的文本

        Returns:
            分词结果列表
        """
        return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text.lower())

    def _score_text_match(self, query: str, text: str) -> float:
        """计算文本与查询的匹配分数.

        基于词集交叠度计算Jaccard相似度。

        Args:
            query: 查询文本
            text: 待匹配的文本

        Returns:
            匹配分数，范围 [0.0, 1.0]
        """
        query_tokens = set(self._tokenize_text(query))
        text_tokens = set(self._tokenize_text(text))
        if not query_tokens or not text_tokens:
            return 0.0
        overlap = query_tokens & text_tokens
        return len(overlap) / max(len(query_tokens), 1)

    @staticmethod
    def _truncate_text(text: str, limit: int = 120) -> str:
        """截断文本并添加省略号.

        先规范化空白，然后截断到指定长度。

        Args:
            text: 待截断的文本
            limit: 最大长度

        Returns:
            截断后的文本
        """
        normalized = " ".join(str(text).split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."

    @staticmethod
    def _format_memory_reference(memory_type: str, label: str, score: float) -> str:
        """格式化记忆引用信息.

        Args:
            memory_type: 记忆类型（短期/中期/长期）
            label: 记忆标签
            score: 相关度分数

        Returns:
            格式化的引用字符串
        """
        return f"{memory_type} | {label} | Score {score:.2f}"

    def _search_short_term(self, query: str, top_k: int = 3) -> List[Dict[str, object]]:
        """在短期记忆中搜索相关内容.

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            搜索结果列表，每项包含round_id、role、content、score
        """
        scored = []
        for item in self.short_term.get_recent():
            score = self._score_text_match(query, item.get("content", ""))
            if score <= 0:
                continue
            scored.append({
                "round_id": item.get("round_id", 0),
                "role": item.get("role", "unknown"),
                "content": item.get("content", ""),
                "score": score,
            })
        scored.sort(key=lambda item: (item["score"], item["round_id"]), reverse=True)
        return scored[:top_k]

    def _search_mid_term(self, query: str, top_k: int = 3) -> List[Dict[str, object]]:
        """在中期记忆中搜索相关内容.

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        scored = []
        for item in self.mid_term.search_summaries("", self.session_id):
            score = self._score_text_match(query, item.get("summary", ""))
            if score <= 0:
                continue
            enriched = dict(item)
            enriched["score"] = score
            scored.append(enriched)
        scored.sort(key=lambda item: (item["score"], item.get("round_end", 0)), reverse=True)
        return scored[:top_k]

    def _search_long_term(
        self,
        query: str,
        short_round_ids: Optional[set] = None,
        top_k: int = 3,
    ) -> List[Dict[str, object]]:
        """在长期记忆中搜索相关内容.

        使用向量相似度搜索，并排除已在短期记忆中的内容。

        Args:
            query: 查询文本
            short_round_ids: 短期记忆的轮次ID集合（用于去重）
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        query_vector = self._simple_vectorize(query)
        short_round_ids = short_round_ids or set()
        scored = []
        for item in self.long_term.search_vectors(query_vector, top_k=10):
            metadata = item.get("metadata", {})
            if metadata.get("session_id") != self.session_id:
                continue
            round_id = item.get("round_id", 0)
            if round_id in short_round_ids:
                continue
            raw_log = self.long_term.get_raw_log(round_id)
            if not raw_log:
                continue
            scored.append({
                "round_id": round_id,
                "role": raw_log.get("role", metadata.get("role", "unknown")),
                "content": raw_log.get("content", ""),
                "score": float(item.get("score", 0.0)),
            })
        scored.sort(key=lambda item: (item["score"], item["round_id"]), reverse=True)
        return scored[:top_k]

    def get_stats(self) -> MemoryStats:
        """获取记忆统计信息.

        Returns:
            记忆统计对象
        """
        return MemoryStats(
            long_term_summary_len=len(self.session.global_summary) if self.session.global_summary else 0,
            short_term_count=len(self.session.history) - self.session.summarized_index,
            mid_term_count=len(self.mid_term.search_summaries("", self.session_id))
        )

    def clear(self):
        """清空所有记忆."""
        self.short_term.clear()
        self.mid_term.clear()
        self.long_term.clear()
        self._round_counter = 0
        self.session.global_summary = ""
        self.session.summarized_index = 0
        self.session.set("_memory_context_cache", {
            "query": "",
            "context": "",
            "references": [],
            "searched_types": [],
        })


# 全局工厂函数
def create_memory_manager(session: Session, session_id: str = "default") -> UnifiedMemoryManager:
    """创建统一记忆管理器.

    Args:
        session: 会话对象
        session_id: 会话ID

    Returns:
        统一记忆管理器实例
    """
    return UnifiedMemoryManager(session, session_id)
