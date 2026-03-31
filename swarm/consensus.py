"""共识策略模块.

该模块实现了 ConsensusStrategy 类，提供多种聚合多个 Agent 结果的策略，
包括多数投票和 Map-Reduce 合并。
"""

from typing import List, Dict
from llm.llm import call_qwen


class ConsensusStrategy:
    """聚合多个 Agent 结果的策略."""

    @staticmethod
    def majority_vote_text(results: List[str], topic: str) -> str:
        """使用 LLM 从多个文本结果中综合出共识答案.

        Args:
            results: 多个 Agent 的结果列表
            topic: 主题描述

        Returns:
            综合后的共识答案
        """
        prompt = f"""
        主题: {topic}

        我们收到了来自不同 Agent 的多个回复:

        """
        for i, res in enumerate(results):
            prompt += f"--- Agent {i+1} ---\n{res}\n\n"

        prompt += """
        请分析这些回复并综合得出一个最终的共识答案。
        如果存在冲突，请解释不同的观点，并根据事实选择最合理的观点。
        直接输出最终答案。
        """

        return call_qwen([{"role": "user", "content": prompt}])

    @staticmethod
    def map_reduce(results: Dict[str, str], instruction: str) -> str:
        """Map-Reduce 的 Reduce 步骤.

        Args:
            results: 部分结果字典，键为部分标识，值为内容
            instruction: 合并指令

        Returns:
            合并后的最终结果
        """
        content = "\n".join([f"部分 {k}: {v}" for k, v in results.items()])
        prompt = f"""
        根据以下指令将各部分合并成一个连贯的整体: "{instruction}"

        {content}
        """
        return call_qwen([{"role": "user", "content": prompt}])
