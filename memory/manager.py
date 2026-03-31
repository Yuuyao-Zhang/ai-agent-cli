"""记忆管理器模块.

实现分层记忆、滑动窗口摘要、KV-Cache 剪枝与 Token 预算预测。
"""

from typing import List, Dict

from common.constant import MAX_TOTAL_TOKENS_PER_AGENT
from llm.context import estimate_tokens
from llm.llm import call_qwen
from memory.types import MemoryStats
from state.session import Session


class TokenPredictor:
    """Token 预算预测器."""

    def __init__(self, window_size: int = 5):
        """初始化 Token 预测器.

        Args:
            window_size: 历史记录窗口大小
        """
        self.history: List[int] = []
        self.window_size = window_size

    def add_sample(self, tokens: int):
        """添加一次 Token 消耗样本.

        Args:
            tokens: 本次消耗的 Token 数
        """
        self.history.append(tokens)
        if len(self.history) > self.window_size:
            self.history.pop(0)

    def predict_next(self) -> int:
        """预测下一次交互的 Token 消耗 (简单移动平均).

        Returns:
            预测的 Token 数
        """
        if not self.history:
            return 500  # 默认预估
        return sum(self.history) // len(self.history)


class MemoryManager:
    """分层记忆管理器."""

    def __init__(self, session: Session):
        """初始化记忆管理器.

        Args:
            session: 会话对象
        """
        self.session = session
        self.token_predictor = TokenPredictor()

        # 配置直接从常量读取，避免重复存储
        self.summary_threshold = 0.8  # 达到 80% 预算时触发压缩
        self.window_size = 10  # 保持最近 N 轮对话不被摘要

    @property
    def max_tokens(self) -> int:
        """从常量动态获取最大 Token 数.

        Returns:
            最大 Token 数
        """
        return MAX_TOTAL_TOKENS_PER_AGENT

    def add_message(self, role: str, content: str):
        """添加新消息并触发内存管理.

        Args:
            role: 消息角色 (user/assistant)
            content: 消息内容
        """
        # 1. 估算 Token
        tokens = estimate_tokens(content)
        if role == "assistant":
            self.token_predictor.add_sample(tokens)

        # 2. 存入 Session (Raw History)
        # 注意：Session 依然保存完整历史以供 Checkpoint，MemoryManager 负责视图构建
        self.session.add_message(role, content)

        # 3. 检查是否需要压缩
        self._check_and_compress()

    def get_context(self) -> List[Dict[str, str]]:
        """获取构建 Prompt 用的上下文 (包含摘要 + 短期记忆).

        Returns:
            消息列表，用于构建 LLM 的 Prompt
        """
        messages = []

        # 1. 如果有长期记忆摘要，作为 System Prompt 或第一条 User 消息的上下文
        if self.session.global_summary:
            messages.append({
                "role": "system",
                "content": f"之前对话摘要:\n{self.session.global_summary}"
            })

        # 2. 获取短期记忆 (从 Session 倒序获取，直到 Token 限制或窗口限制)
        raw_history = self.session.history

        start_idx = self.session.summarized_index
        recent_msgs = raw_history[start_idx:]

        # KV-Cache 剪枝：如果 recent_msgs 依然太长，丢弃中间的辅助性消息
        pruned_msgs = self._prune_context(recent_msgs)

        messages.extend(pruned_msgs)
        return messages

    def _check_and_compress(self):
        """检查 Token 预算并执行压缩."""
        raw_history = self.session.history
        start_idx = self.session.summarized_index
        active_msgs = raw_history[start_idx:]

        current_tokens = sum(estimate_tokens(m["content"]) for m in active_msgs)
        predicted_next = self.token_predictor.predict_next()

        # 如果当前上下文 + 预测的下一次输出 > 阈值，则触发压缩
        if current_tokens + predicted_next > self.max_tokens * self.summary_threshold:
            self._summarize_window(active_msgs)

    def _summarize_window(self, msgs: List[Dict[str, str]]):
        """滑动窗口摘要算法.

        Args:
            msgs: 待摘要的消息列表
        """
        if len(msgs) <= 2:
            return  # 消息太少不摘要

        # 保留最近 4 条作为活跃窗口，压缩前面的
        to_summarize = msgs[:-4]
        if not to_summarize:
            return

        # 提取文本
        text_block = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])

        # 调用 LLM 生成摘要
        prompt = [
            {"role": "system", "content": "你是一个摘要助手。请用中文简洁地总结以下对话。保留关键事实、决策和代码变更。"},
            {"role": "user", "content": f"已有摘要: {self.session.global_summary}\n\n新对话:\n{text_block}"}
        ]

        try:
            new_summary = call_qwen(prompt)
            if new_summary and new_summary.strip():
                self.session.global_summary = new_summary

                # 由于 Session 是 append-only 的，我们必须小心。
                current_idx = self.session.summarized_index
                self.session.summarized_index = current_idx + len(to_summarize)

                print("[Memory] 已压缩 {} 条消息。摘要已更新。".format(len(to_summarize)))
            else:
                # 摘要为空，不更新索引，避免历史消息"丢失"
                print("[Memory] 摘要返回空，跳过索引更新。")
        except Exception as e:
            print("[Memory] 摘要生成失败: {}".format(e))

    def _prune_context(self, msgs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """应用上下文剪枝策略 (Context Pruning).

        注意：这不同于 Semantic KV-Cache。这里是针对过长文本的截断处理，
        类似于 LLM 推理中的 "Attention Masking" 或 "Token Dropping" 策略，
        目的是在不影响整体语义的前提下减少 Token 消耗。

        去除低价值 Token，例如过长的工具输出或重复确认。

        Args:
            msgs: 原始消息列表

        Returns:
            剪枝后的消息列表
        """
        pruned = []
        for msg in msgs:
            content = msg["content"]
            # 1. 裁剪过长的工具输出
            if msg["role"] == "user" and "Tool Results" in content and len(content) > 1000:
                # 保留头尾
                content = content[:200] + "\n...[输出已裁剪]...\n" + content[-200:]
                pruned.append({"role": msg["role"], "content": content})
            # 2. 过滤无意义的短对话 (可选，暂不启用以免破坏逻辑)
            else:
                pruned.append(msg)
        return pruned

    def get_stats(self) -> MemoryStats:
        """获取记忆统计信息.

        Returns:
            记忆统计对象
        """
        return MemoryStats(
            long_term_summary_len=len(self.session.global_summary),
            short_term_count=len(self.session.history) - self.session.summarized_index
        )

