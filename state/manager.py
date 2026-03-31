"""任务管理器模块.

该模块实现了 TaskManager 类，负责任务的生命周期管理，包括创建、
启动、暂停、恢复、终止等操作。
"""

from typing import Dict, List, Optional

from state.task import Task, TaskStatus


class TaskManager:
    """任务管理器类.

    统一管理所有任务的生命周期，提供任务的创建、查询、状态转换等功能。

    Attributes:
        tasks: 任务字典，键为任务 ID，值为 Task 对象
        _task_counter: 任务 ID 计数器
    """

    def __init__(self):
        """初始化任务管理器."""
        self.tasks: Dict[str, Task] = {}
        self._task_counter: int = 0

    def _generate_id(self) -> str:
        """生成唯一任务 ID.

        Returns:
            新的任务 ID 字符串
        """
        self._task_counter += 1
        return f"task_{self._task_counter}"

    def create_task(
        self,
        name: str,
        session=None,
        parent_id: Optional[str] = None
    ) -> Task:
        """创建新任务.

        Args:
            name: 任务名称
            session: 关联的会话对象
            parent_id: 父任务 ID（可选）

        Returns:
            新创建的 Task 对象
        """
        task_id = self._generate_id()
        task = Task(
            id=task_id,
            name=name,
            session=session,
            parent_id=parent_id
        )
        self.tasks[task_id] = task

        # 如果存在父任务，则建立关联
        if parent_id:
            parent_task = self.tasks.get(parent_id)
            if parent_task:
                parent_task.add_child(task_id)

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取指定任务.

        Args:
            task_id: 任务 ID

        Returns:
            Task 对象，如果不存在则返回 None
        """
        return self.tasks.get(task_id)

    def get_active_tasks(self) -> List[Task]:
        """获取所有活跃任务.

        Returns:
            状态为 PENDING 或 IN_PROGRESS 的任务列表
        """
        return [
            task for task in self.tasks.values()
            if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        ]

    def pause_task(self, task_id: str) -> bool:
        """暂停指定任务.

        Args:
            task_id: 任务 ID

        Returns:
            暂停成功返回 True，失败返回 False
        """
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.IN_PROGRESS:
            task.pause()
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """恢复指定任务.

        Args:
            task_id: 任务 ID

        Returns:
            恢复成功返回 True，失败返回 False
        """
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PAUSED:
            task.resume()
            return True
        return False

    def terminate_task(self, task_id: str) -> bool:
        """终止指定任务.

        Args:
            task_id: 任务 ID

        Returns:
            终止成功返回 True，失败返回 False
        """
        task = self.tasks.get(task_id)
        if task:
            task.terminate()
            return True
        return False

    def get_task_tree(self, task_id: str) -> List[Task]:
        """获取任务及其所有子任务.

        Args:
            task_id: 任务 ID

        Returns:
            任务及其子任务的列表
        """
        result = []
        task = self.tasks.get(task_id)
        if not task:
            return result

        result.append(task)
        for child_id in task.children_ids:
            result.extend(self.get_task_tree(child_id))

        return result


# 全局任务管理器实例
task_manager = TaskManager()
