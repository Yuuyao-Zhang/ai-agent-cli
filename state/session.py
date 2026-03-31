"""会话状态管理模块.

该模块实现了会话状态机，维护对话历史与变量上下文，
支持调用栈追踪和上下文继承。

Attributes:
    Session: 会话状态类
    Snapshot: 上下文快照类
"""

import copy
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from state.channel import Channel
from state.namespace import Namespace


@dataclass
class Snapshot:
    """上下文快照类.

    保存会话的完整状态，用于调试和错误恢复。

    Attributes:
        timestamp: 快照创建时间
        history: 对话历史副本
        namespace_vars: 命名空间变量副本
        task_stack: 任务调用栈副本
        depth: 递归深度
    """

    timestamp: float
    history: List[Dict[str, str]] = field(default_factory=list)
    namespace_vars: Dict[str, Any] = field(default_factory=dict)
    task_stack: List[str] = field(default_factory=list)
    depth: int = 0

    # 补充 v5 Memory Fields 以避免漂移
    global_summary: str = ""
    summarized_index: int = 0

    @classmethod
    def from_session(cls, session: "Session") -> "Snapshot":
        """从会话创建快照.

        Args:
            session: 要保存的会话对象

        Returns:
            新的 Snapshot 实例
        """
        return cls(
            timestamp=time.time(),
            history=copy.deepcopy(session.history),
            namespace_vars=copy.deepcopy(session.namespace.get_all()),
            task_stack=copy.deepcopy(session.task_stack),
            depth=session.depth,
            # 保存记忆状态
            global_summary=session.global_summary,
            summarized_index=session.summarized_index
        )

    def restore_to(self, session: "Session") -> None:
        """将快照状态恢复到会话.

        Args:
            session: 目标会话对象
        """
        session.history = copy.deepcopy(self.history)
        session.namespace.clear()
        for key, value in self.namespace_vars.items():
            session.namespace.set(key, value)
        session.task_stack = copy.deepcopy(self.task_stack)
        session.depth = self.depth
        # 恢复记忆状态
        session.global_summary = self.global_summary
        session.summarized_index = self.summarized_index


@dataclass
class Session:
    """会话状态容器 - 支持调用栈和上下文继承.

    Attributes:
        history: 当前会话的对话历史，每条消息为包含 role 和 content 的字典
        namespace: 命名空间，用于变量隔离
        channel: 通信通道，用于任务间通信
        parent: 父会话引用 (用于调用栈追踪)
        depth: 当前递归深度
        task_stack: 任务调用栈 (记录每一层级的任务描述)
    """

    history: List[Dict[str, str]] = field(default_factory=list)
    namespace: Namespace = field(default_factory=lambda: Namespace("root"))
    channel: Optional[Channel] = field(default=None)
    parent: Optional["Session"] = None
    depth: int = 0
    task_stack: List[str] = field(default_factory=list)

    # v5 Memory Fields
    global_summary: str = ""
    summarized_index: int = 0

    def __post_init__(self):
        """初始化后创建默认通道."""
        if self.channel is None:
            self.channel = Channel(name=f"session_{self.depth}")

    def __getstate__(self):
        """自定义序列化状态，排除不可序列化的 Channel 对象."""
        state = self.__dict__.copy()
        if 'channel' in state:
            del state['channel']
        return state

    def __setstate__(self, state):
        """自定义反序列化状态，重新初始化 Channel."""
        self.__dict__.update(state)
        # 恢复 channel
        self.channel = Channel(name=f"session_{self.depth}")

    def fork(self, new_task: str) -> "Session":
        """创建子会话：继承上下文，但隔离历史.

        为了实现"上下文继承与隔离的平衡"，子会话能读取父会话环境，
        但子会话的临时变量不应污染父会话。

        Args:
            new_task: 子任务描述

        Returns:
            新的子 Session 实例
        """
        # 创建子命名空间
        child_namespace = self.namespace.fork(f"task_{self.depth + 1}")

        return Session(
            history=[],
            namespace=child_namespace,
            channel=self.channel,  # 共享通道
            parent=self,
            depth=self.depth + 1,
            task_stack=self.task_stack + [new_task],
        )

    def add_message(self, role: str, content: str) -> None:
        """添加一条消息到对话历史.

        Args:
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容
        """
        self.history.append({"role": role, "content": content})

    def get(self, key: str, default=None) -> Any:
        """获取命名空间变量值.

        Args:
            key: 变量名
            default: 默认值（可选）

        Returns:
            变量值或默认值
        """
        return self.namespace.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置命名空间变量值.

        Args:
            key: 变量名
            value: 新值
        """
        self.namespace.set(key, value)

    def get_trace(self) -> str:
        """获取当前任务调用栈的字符串表示.

        Returns:
            任务调用栈的字符串表示，格式为 "task1 -> task2 -> task3"
        """
        return " -> ".join(self.task_stack)

    def create_snapshot(self) -> Snapshot:
        """创建当前状态的快照.

        Returns:
            当前会话状态的快照
        """
        return Snapshot.from_session(self)
