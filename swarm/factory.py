"""子 Agent 工厂模块.

该模块实现了 SubagentFactory 类，用于创建和配置子 Agent。
支持为不同角色（Worker、Critic 等）创建预配置的 Session。
"""

from state.session import Session
from swarm.types import AgentConfig, AgentRole


class SubagentFactory:
    """创建和配置子 Agent 的工厂类.

    提供静态方法用于创建不同角色的 Agent 配置和 Session。
    """

    @staticmethod
    def create_session(
        config: AgentConfig, parent_session: Session = None
    ) -> Session:
        """为特定角色创建配置好的 Session.

        Args:
            config: Agent 配置
            parent_session: 父会话（可选）

        Returns:
            配置好的 Session 实例
        """
        if parent_session:
            session = parent_session.fork(f"Agent-{config.name}")
        else:
            session = Session()

        # 将 system prompt 注入 session (由修改后的 assembler 支持)
        session.set('system_prompt', config.system_prompt)
        session.set('agent_config', config)

        return session

    @staticmethod
    def create_worker(name: str, task: str) -> AgentConfig:
        """创建工作 Agent 配置.

        Args:
            name: Agent 名称
            task: 任务描述

        Returns:
            Worker 角色的 AgentConfig
        """
        return AgentConfig(
            name=name,
            role=AgentRole.WORKER,
            system_prompt=f"你是一个名为 {name} 的工作 Agent。任务: {task}。请高效地解决它。"
        )

    @staticmethod
    def create_critic(name: str) -> AgentConfig:
        """创建批评 Agent 配置.

        Args:
            name: Agent 名称

        Returns:
            Critic 角色的 AgentConfig
        """
        return AgentConfig(
            name=name,
            role=AgentRole.CRITIC,
            system_prompt=f"你是一个名为 {name} 的批评 Agent。请审查提供的输出是否存在错误并提出改进建议。"
        )
