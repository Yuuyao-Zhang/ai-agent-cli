"""Swarm 调度器模块.

该模块实现了 SwarmScheduler 类，用于并行调度和执行 Swarm 任务。
使用线程池实现任务的并发执行，支持简单的依赖关系调度 (DAG)。
"""

import concurrent.futures
import time
from typing import Dict, List, Optional, Set

from common.io_utils import error, info
from engine.agent import run
from swarm.factory import SubagentFactory
from swarm.types import SwarmTask
from state.session import Session


class SwarmScheduler:
    """并行调度和执行 Swarm 任务，支持依赖管理."""

    def __init__(self, max_workers: int = 3):
        """初始化调度器.

        Args:
            max_workers: 最大工作线程数，默认为 3
        """
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def execute_task(
        self,
        task: SwarmTask,
        parent_session: Session,
        context: Optional[Dict[str, str]] = None
    ) -> str:
        """使用配置好的子 Agent 执行单个任务.

        Args:
            task: Swarm 任务
            parent_session: 父会话
            context: 上游任务的结果上下文 (可选)

        Returns:
            任务执行结果
        """
        final_description = task.description
        if context:
            context_str = "\n".join(
                f"前置任务 {tid} 结果:\n{res}"
                for tid, res in context.items()
            )
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
        self,
        tasks: List[SwarmTask],
        parent_session: Session
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

        while pending_tasks or running_futures:
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
                        completed_ids.add(task_id)
                    done_futures.append(future)

            for f in done_futures:
                del running_futures[f]

            if len(running_futures) < self.max_workers:
                ready_task_ids = []
                for tid, task in pending_tasks.items():
                    if all(dep_id in completed_ids for dep_id in task.dependencies):
                        ready_task_ids.append(tid)

                for tid in ready_task_ids:
                    if len(running_futures) >= self.max_workers:
                        break

                    task = pending_tasks.pop(tid)
                    dependency_context = {
                        dep_id: results[dep_id]
                        for dep_id in task.dependencies
                        if dep_id in results
                    }

                    future = self.executor.submit(
                        self.execute_task, task, parent_session, dependency_context
                    )
                    running_futures[future] = tid

            if pending_tasks or running_futures:
                if not running_futures and pending_tasks:
                    deadlock_msg = (
                        f"Scheduler Deadlock detected! "
                        f"Pending tasks {list(pending_tasks.keys())} "
                        f"cannot be scheduled."
                    )
                    error(deadlock_msg)
                    for tid in list(pending_tasks.keys()):
                        results[tid] = f"Error: {deadlock_msg}"
                        completed_ids.add(tid)
                    break

                time.sleep(0.1)

        return results

    def shutdown(self) -> None:
        """关闭线程池."""
        self.executor.shutdown(wait=True)
