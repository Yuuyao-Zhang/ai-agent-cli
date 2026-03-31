"""Map-Reduce 规划器模块.

该模块实现了 MapReducePlanner 类，用于将复杂任务分解为子任务 (Map)
并聚合结果 (Reduce)。使用 LLM 进行智能任务分解。
"""

from typing import List
from llm.llm import call_qwen
from swarm.types import SwarmTask
from swarm.factory import SubagentFactory
from engine.agent import run
import json


class MapReducePlanner:
    """将复杂任务分解为子任务 (Map) 并聚合结果 (Reduce)."""

    @staticmethod
    def reduce(task_desc: str, results: List[str]) -> str:
        """使用 Critic Agent 聚合和审查结果.

        Args:
            task_desc: 原始任务描述
            results: 子任务执行结果列表

        Returns:
            最终汇总结果
        """
        # 创建 Critic Agent
        critic_config = SubagentFactory.create_critic("Critic-Reducer")
        
        # 构造输入
        results_str = "\n\n".join([f"Part {i+1}:\n{res}" for i, res in enumerate(results)])
        prompt = f"""
        任务: {task_desc}
        
        以下是子任务的执行结果:
        {results_str}
        
        请审查这些结果，指出潜在的错误或不一致之处，并整合成一份最终的解答。
        """
        
        # 创建 Session 并运行
        session = SubagentFactory.create_session(critic_config)
        return run(prompt, session)

    @staticmethod
    def decompose(task_desc: str, num_parts: int = 3) -> List[SwarmTask]:
        """使用 LLM 将任务分解为可并行执行的子任务.

        Args:
            task_desc: 任务描述
            num_parts: 分解的子任务数量，默认为 3

        Returns:
            SwarmTask 列表
        """
        prompt = f"""
        将以下任务分解为 {num_parts} 个可并行执行的独立子任务。
        任务: {task_desc}

        仅输出有效的 JSON 格式:
        [
            {{ "id": "part1", "description": "..." }},
            {{ "id": "part2", "description": "..." }}
        ]
        """
        response = call_qwen([{"role": "user", "content": prompt}])
        try:
            # 简单的清理以去除可能的 markdown 代码块
            clean_resp = response.replace("```json", "").replace("```", "").strip()
            parts = json.loads(clean_resp)

            tasks = []
            for p in parts:
                config = SubagentFactory.create_worker(
                    f"Worker-{p['id']}", p['description']
                )
                tasks.append(SwarmTask(
                    id=p['id'],
                    description=p['description'],
                    agent_config=config
                ))
            return tasks
        except Exception as e:
            print(f"Error decomposing task: {e}")
            # 回退：创建一个单一任务
            return [SwarmTask(
                id="single",
                description=task_desc,
                agent_config=SubagentFactory.create_worker("SoloWorker", task_desc)
            )]
