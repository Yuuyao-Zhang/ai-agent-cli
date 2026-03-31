"""任务模块.

该模块实现了 Task 类和 TaskStatus 枚举，用于任务的生命周期管理。
支持任务状态转换、父任务追踪和子任务管理。
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any


class TaskStatus(Enum):
    """任务状态枚举.

    Attributes:
        PENDING: 待处理
        IN_PROGRESS: 进行中
        PAUSED: 已暂停
        COMPLETED: 已完成
        FAILED: 失败
        TERMINATED: 已终止
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class Task:
    """任务类.

    表示一个可执行的任务单元，支持状态管理和生命周期追踪。

    Attributes:
        id: 任务唯一标识符
        name: 任务名称
        status: 当前状态
        session: 关联的会话对象
        parent_id: 父任务 ID
        children_ids: 子任务 ID 列表
        created_at: 创建时间戳
        started_at: 开始时间戳
        completed_at: 完成时间戳
        result: 执行结果
        error: 错误信息
    """

    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    session: Any = None
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None

    def start(self) -> None:
        """开始任务.

        将状态从 PENDING 转换为 IN_PROGRESS。
        """
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.IN_PROGRESS
            self.started_at = time.time()

    def pause(self) -> None:
        """暂停任务.

        将状态从 IN_PROGRESS 转换为 PAUSED。
        """
        if self.status == TaskStatus.IN_PROGRESS:
            self.status = TaskStatus.PAUSED

    def resume(self) -> None:
        """恢复任务.

        将状态从 PAUSED 转换为 IN_PROGRESS。
        """
        if self.status == TaskStatus.PAUSED:
            self.status = TaskStatus.IN_PROGRESS

    def complete(self, result: str = "") -> None:
        """完成任务.

        将状态设置为 COMPLETED 并记录结果。

        Args:
            result: 执行结果
        """
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = time.time()

    def fail(self, error: str) -> None:
        """标记任务失败.

        将状态设置为 FAILED 并记录错误信息。

        Args:
            error: 错误信息
        """
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = time.time()

    def terminate(self) -> None:
        """终止任务.

        将状态设置为 TERMINATED。
        """
        self.status = TaskStatus.TERMINATED
        self.completed_at = time.time()

    def add_child(self, child_id: str) -> None:
        """添加子任务.

        Args:
            child_id: 子任务 ID
        """
        if child_id not in self.children_ids:
            self.children_ids.append(child_id)

    def get_duration(self) -> Optional[float]:
        """获取任务持续时间.

        Returns:
            持续时间（秒），如果任务未开始则返回 None
        """
        if not self.started_at:
            return None
        end_time = self.completed_at or time.time()
        return end_time - self.started_at
