"""To-do 存储管理模块.

该模块实现了 To-do 列表的持久化存储与版本控制，支持增删改查、
批量更新、历史回溯等功能。
"""

import json
import os
import time
import copy
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from enum import Enum

from common.config import config
from common.io_utils import error, warning


class ToDoStatus(Enum):
    """待办状态枚举.

    Attributes:
        PENDING: 待处理
        IN_PROGRESS: 进行中
        COMPLETED: 已完成
        FAILED: 失败
        SKIPPED: 已跳过
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToDoItem:
    """To-do 项目类.

    Attributes:
        id: 任务唯一标识符
        content: 任务内容描述
        status: 任务状态
        priority: 优先级 (high, medium, low)
        created_at: 创建时间戳
        updated_at: 更新时间戳
    """

    id: str
    content: str
    status: ToDoStatus = ToDoStatus.PENDING
    priority: str = "medium"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式.

        Returns:
            包含所有字段的字典，status 字段转换为字符串值
        """
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ToDoItem":
        """从字典创建 ToDoItem 实例.

        Args:
            d: 包含任务数据的字典

        Returns:
            ToDoItem 实例
        """
        d["status"] = ToDoStatus(d["status"])
        return ToDoItem(**d)


@dataclass
class ToDoList:
    """To-do 列表类.

    Attributes:
        todos: To-do 项目列表
        version: 版本号
        timestamp: 时间戳
    """

    todos: List[ToDoItem] = field(default_factory=list)
    version: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式.

        Returns:
            包含所有字段的字典
        """
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "todos": [t.to_dict() for t in self.todos]
        }


class ToDoStore:
    """To-do 存储类.

    实现持久化存储与版本控制，支持历史回溯。

    Attributes:
        storage_path: 存储文件路径
        history: 版本历史列表
        current_list: 当前 To-do 列表
        _next_id: ID 计数器
    """

    def __init__(self, storage_path: str = None):
        """初始化 To-do 存储.

        Args:
            storage_path: 存储文件路径，默认从配置获取
        """
        self.storage_path = storage_path or config.app.todo_storage_path
        self.history: List[ToDoList] = []
        self.current_list: ToDoList = ToDoList()
        self._next_id: int = 1
        self._load()

    def _load(self) -> None:
        """从文件加载 To-do 列表."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.current_list = ToDoList(
                    version=data.get("version", 0),
                    timestamp=data.get("timestamp", time.time()),
                    todos=[
                        ToDoItem.from_dict(t)
                        for t in data.get("todos", [])
                    ]
                )

                max_id = 0
                for t in self.current_list.todos:
                    if str(t.id).isdigit():
                        max_id = max(max_id, int(t.id))
                self._next_id = max_id + 1

            except Exception as e:
                error(f"[ToDoStore] Load error: {e}")
                self.current_list = ToDoList()
                self._next_id = 1
        else:
            self._next_id = 1

    def _save(self) -> None:
        """保存 To-do 列表到文件."""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.current_list.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            error(f"[ToDoStore] Save error: {e}")

    def _generate_id(self) -> str:
        """生成唯一 ID.

        Returns:
            新的唯一标识符字符串
        """
        new_id = str(self._next_id)
        self._next_id += 1
        return new_id

    def snapshot(self) -> None:
        """创建当前状态的快照并保存到历史.

        限制快照历史长度为 10，避免无限增长。
        """
        snapshot = copy.deepcopy(self.current_list)
        self.history.append(snapshot)
        if len(self.history) > 10:
            self.history.pop(0)

    def add_todo(self, content: str, priority: str = "medium") -> ToDoItem:
        """添加新的 To-do 项目.

        Args:
            content: 任务内容描述
            priority: 优先级 (high, medium, low)，默认为 medium

        Returns:
            新创建的 ToDoItem 实例
        """
        self.snapshot()

        new_id = self._generate_id()
        item = ToDoItem(id=new_id, content=content, priority=priority)
        self.current_list.todos.append(item)
        self.current_list.version += 1
        self.current_list.timestamp = time.time()
        self._save()
        return item

    def update_todo(
        self, todo_id: str, status: str = None, content: str = None
    ) -> bool:
        """更新指定 To-do 项目.

        Args:
            todo_id: 任务 ID
            status: 新状态（可选）
            content: 新内容（可选）

        Returns:
            如果找到并更新了任务，返回 True；否则返回 False

        Raises:
            ValueError: 如果提供了无效的状态值
        """
        self.snapshot()

        found = False
        for todo in self.current_list.todos:
            if todo.id == todo_id:
                if status:
                    try:
                        todo.status = ToDoStatus(status)
                    except ValueError as e:
                        raise ValueError(f"Invalid status: {status}") from e
                if content:
                    todo.content = content
                todo.updated_at = time.time()
                found = True
                break

        if found:
            self.current_list.version += 1
            self._save()

        return found

    def bulk_update(self, todos_data: List[Dict[str, Any]]) -> None:
        """批量更新或添加 To-do 项目.

        Args:
            todos_data: To-do 数据列表
        """
        self.snapshot()

        updated_any = False

        for item_data in todos_data:
            tid = item_data.get("id")
            if tid:
                found = False
                for todo in self.current_list.todos:
                    if todo.id == tid:
                        if "status" in item_data:
                            try:
                                todo.status = ToDoStatus(item_data["status"])
                            except ValueError:
                                warning(
                                    f"[ToDoStore] Invalid status "
                                    f"{item_data['status']} for {tid}"
                                )
                        if "content" in item_data:
                            todo.content = item_data["content"]
                        todo.updated_at = time.time()
                        found = True
                        updated_any = True
                        break

                if not found:
                    content = item_data.get("content", "Untitled Task")
                    priority = item_data.get("priority", "medium")

                    if str(tid).isdigit():
                        self._next_id = max(self._next_id, int(tid) + 1)

                    new_item = ToDoItem(
                        id=str(tid), content=content, priority=priority
                    )

                    if "status" in item_data:
                        try:
                            new_item.status = ToDoStatus(item_data["status"])
                        except ValueError:
                            warning(
                                f"[ToDoStore] Invalid status "
                                f"{item_data['status']} for new task {tid}"
                            )

                    self.current_list.todos.append(new_item)
                    updated_any = True
            else:
                content = item_data.get("content", "Untitled Task")
                priority = item_data.get("priority", "medium")
                new_id = self._generate_id()
                new_item = ToDoItem(id=new_id, content=content, priority=priority)
                self.current_list.todos.append(new_item)
                updated_any = True

        if updated_any:
            self.current_list.version += 1
            self.current_list.timestamp = time.time()
            self._save()

    def get_all(self) -> List[ToDoItem]:
        """获取所有 To-do 项目.

        Returns:
            所有 To-do 项目的列表
        """
        return self.current_list.todos

    def get_pending(self) -> List[ToDoItem]:
        """获取状态为 pending 的任务.

        Returns:
            所有待处理任务的列表
        """
        return [
            t for t in self.current_list.todos
            if t.status == ToDoStatus.PENDING
        ]

    def clear(self) -> None:
        """清空当前 To-do 列表并保存."""
        self.snapshot()
        self.current_list = ToDoList()
        self.current_list.version += 1
        self.current_list.timestamp = time.time()
        self._next_id = 1
        self._save()

    def rollback(self, steps: int = 1) -> bool:
        """回溯到之前的版本.

        Args:
            steps: 回溯的步数，默认为 1

        Returns:
            如果回溯成功，返回 True；否则返回 False
        """
        if not self.history or steps < 1:
            return False

        target_idx = len(self.history) - steps
        if target_idx < 0:
            target_idx = 0

        self.current_list = copy.deepcopy(self.history[target_idx])
        self.history = self.history[:target_idx]
        self._save()
        return True


# 全局存储实例
to_do_store = ToDoStore()
