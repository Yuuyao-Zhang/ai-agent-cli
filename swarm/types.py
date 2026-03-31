"""Swarm 类型定义模块.

该模块定义了 Swarm 智能系统中使用的数据类型，包括 Agent 角色、
Agent 配置和 Swarm 任务等。
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List


class AgentRole(Enum):
    """Agent 角色枚举.

    Attributes:
        WORKER: 工作 Agent，负责执行具体任务
        MANAGER: 管理 Agent，负责协调和分配任务
        CRITIC: 批评 Agent，负责审查和改进输出
    """

    WORKER = auto()
    MANAGER = auto()
    CRITIC = auto()


@dataclass
class AgentConfig:
    """子 Agent 配置类.

    定义 Agent 的名称、角色、系统提示词、可用工具和温度参数。

    Attributes:
        name: Agent 名称
        role: Agent 角色
        system_prompt: 系统提示词
        tools: 可用工具列表
        temperature: 温度参数，控制输出的随机性
    """

    name: str
    role: AgentRole
    system_prompt: str
    tools: List[str] = field(default_factory=list)
    temperature: float = 0.7


@dataclass
class SwarmTask:
    """分配给 Swarm Agent 的任务类.

    Attributes:
        id: 任务唯一标识符
        description: 任务描述
        agent_config: Agent 配置
        dependencies: 依赖的其他任务 ID 列表
    """

    id: str
    description: str
    agent_config: AgentConfig
    dependencies: List[str] = field(default_factory=list)
