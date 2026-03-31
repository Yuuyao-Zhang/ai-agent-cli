"""Swarm 调度器模块.

该模块实现了 SwarmScheduler 类，用于并行调度和执行 Swarm 任务。
使用线程池实现任务的并发执行，支持简单的依赖关系调度 (DAG)。
"""

import concurrent.futures
import time
from typing import List, Dict, Set
from engine.agent import run
from swarm.types import SwarmTask
from swarm.factory import SubagentFactory
from state.session import Session
from common.io_utils import info, error


class SwarmScheduler:
    """并行调度和执行 Swarm 任务，支持依赖管理."""

    def __init__(self, max_workers: int = 3):
        """初始化调度器.

        Args:
            max_workers: 最大工作线程数，默认为 3
        """
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def execute_task(self, task: SwarmTask, parent_session: Session, context: Dict[str, str] = None) -> str:
        """使用配置好的子 Agent 执行单个任务.

        Args:
            task: Swarm 任务
            parent_session: 父会话
            context: 上游任务的结果上下文 (可选)

        Returns:
            任务执行结果
        """
        # 如果有上游结果，拼接到任务描述中
        final_description = task.description
        if context:
            context_str = "\n".join([f"前置任务 {tid} 结果:\n{res}" for tid, res in context.items()])
            final_description += f"\n\n【上游依赖信息】:\n{context_str}"

        session = SubagentFactory.create_session(task.agent_config, parent_session)
        info(f"[Swarm] Starting task {task.id} with agent {task.agent_config.name}")

        try:
            result = run(final_description, session)
            info(f"[Swarm] Task {task.id} completed.")
            return result
        except Exception as e:
            error(f"[Swarm] Task {task.id} failed: {e}")
            return f"Error: {e}"

    def run_batch(
        self, tasks: List[SwarmTask], parent_session: Session
    ) -> Dict[str, str]:
        """并行运行一批任务，自动处理依赖关系 (DAG).

        Args:
            tasks: 任务列表
            parent_session: 父会话

        Returns:
            任务 ID 到结果的映射字典
        """
        results: Dict[str, str] = {}
        pending_tasks = {t.id: t for t in tasks}
        completed_ids: Set[str] = set()
        running_futures: Dict[concurrent.futures.Future, str] = {}

        # 简单的拓扑调度循环
        while pending_tasks or running_futures:
            # 1. 检查已完成的任务
            done_futures = []
            for future in running_futures:
                if future.done():
                    task_id = running_futures[future]
                    try:
                        res = future.result()
                        results[task_id] = res
                        completed_ids.add(task_id)
                    except Exception as e:
                        results[task_id] = f"Error: {e}"
                        # 注意：如果前置任务失败，依赖它的任务可能会拿到错误结果，
                        # 这里暂不处理复杂的错误传播逻辑，继续标记为完成
                        completed_ids.add(task_id)
            done_futures.append(future)
            
            # 清理已完成的 future
            for f in done_futures:
                del running_futures[f]

            # 2. 寻找可以启动的新任务 (依赖已全部满足且未运行)
            # 限制并发数
            if len(running_futures) < self.max_workers:
                ready_task_ids = []
                for tid, task in pending_tasks.items():
                    # 检查所有依赖是否都在 completed_ids 中
                    if all(dep_id in completed_ids for dep_id in task.dependencies):
                        ready_task_ids.append(tid)

                # 提交新任务
                for tid in ready_task_ids:
                    if len(running_futures) >= self.max_workers:
                        break

                    task = pending_tasks.pop(tid)

                    # 收集依赖任务的结果作为上下文
                    dependency_context = {
                        dep_id: results[dep_id]
                        for dep_id in task.dependencies
                        if dep_id in results
                    }

                    future = self.executor.submit(
                        self.execute_task, task, parent_session, dependency_context
                    )
                    running_futures[future] = tid

            # 3. 如果还有任务在跑或在等，就稍微睡一下避免死循环占用 CPU
            if pending_tasks or running_futures:
                # 死锁检测 (Issue 4 Fix)
                # 如果没有正在运行的任务，但仍有挂起的任务，说明这些挂起的任务无法满足依赖（或有环）
                if not running_futures and pending_tasks:
                    deadlock_msg = f"Scheduler Deadlock detected! Pending tasks {list(pending_tasks.keys())} cannot be scheduled."
                    error(deadlock_msg)
                    # 将剩余任务标记为失败
                    for tid in list(pending_tasks.keys()):
                        results[tid] = f"Error: {deadlock_msg}"
                        completed_ids.add(tid)
                    break
                
                time.sleep(0.1)

        return results

    def shutdown(self) -> None:
        """关闭线程池."""
        self.executor.shutdown(wait=True)
