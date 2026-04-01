"""工具注册中心模块.

负责管理和发现所有可用工具，包括本地工具和远程 MCP 工具。
支持多 Server 路由策略。
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from common.logger import logger
from mcp.client import MCPClient


def sanitize_server_url(server_url: str) -> str:
    parts = urlsplit(server_url)
    if not parts.query:
        return server_url

    sensitive_keys = {"ak", "key", "api_key", "token", "access_token"}
    sanitized_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in sensitive_keys:
            sanitized_query.append((key, "***"))
        else:
            sanitized_query.append((key, value))

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(sanitized_query),
        parts.fragment,
    ))


class RoutingStrategy(Enum):
    """路由策略枚举.

    Attributes:
        FIRST_AVAILABLE: 第一个可用（默认）
        ROUND_ROBIN: 轮询
        RANDOM: 随机
    """
    FIRST_AVAILABLE = "first_available"
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"


class ToolRouter:
    """工具请求路由器.

    根据策略从多个 MCP 客户端中选择一个进行调用。

    Attributes:
        strategy: 当前使用的路由策略
        _round_robin_index: 轮询索引
    """

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.FIRST_AVAILABLE):
        """初始化路由器.

        Args:
            strategy: 路由策略，默认为 FIRST_AVAILABLE
        """
        self.strategy = strategy
        self._round_robin_index = 0

    def select_client(self, clients: List[MCPClient]) -> Optional[MCPClient]:
        """根据策略选择客户端.

        Args:
            clients: 可用的客户端列表

        Returns:
            选中的客户端，如果列表为空返回 None
        """
        if not clients:
            return None

        if self.strategy == RoutingStrategy.FIRST_AVAILABLE:
            return clients[0]
        elif self.strategy == RoutingStrategy.ROUND_ROBIN:
            client = clients[self._round_robin_index % len(clients)]
            self._round_robin_index += 1
            return client
        elif self.strategy == RoutingStrategy.RANDOM:
            import random
            return random.choice(clients)

        return clients[0]


class ToolRegistry:
    """工具注册中心.

    动态管理工具的注册与发现，支持多 Server 路由。

    Attributes:
        _local_tools: 本地工具函数字典
        _remote_tools: 远程工具客户端字典（支持多客户端）
        _mcp_clients: MCP Server 客户端实例列表
        _router: 工具路由器
    """

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.FIRST_AVAILABLE):
        """初始化注册中心.

        Args:
            strategy: 多 Server 路由策略
        """
        # 存储本地工具函数: {name: function}
        self._local_tools: Dict[str, Any] = {}
        # 存储远程工具客户端: {tool_name: [MCPClient, ...]}
        self._remote_tools: Dict[str, List[MCPClient]] = {}
        # 存储工具元信息: {tool_name: metadata}
        self._tool_specs: Dict[str, Dict[str, Any]] = {}
        # 存储 MCP Server 客户端实例
        self._mcp_clients: List[MCPClient] = []
        # 路由器
        self._router = ToolRouter(strategy)

    def register_local_tool(self, name: str, func: Any) -> None:
        """注册本地工具.

        Args:
            name: 工具名称
            func: 工具函数
        """
        self._local_tools[name] = func

    def connect_mcp_server(self, server_url: str) -> bool:
        """连接 MCP Server 并注册其提供的工具.

        Args:
            server_url: MCP Server URL
        """
        safe_url = sanitize_server_url(server_url)
        try:
            client = MCPClient(server_url)
            # 动态发现工具
            tools = client.list_tools()
            for tool in tools:
                tool_name = tool.get("name")
                if tool_name:
                    # 支持同一工具多个 Server 提供
                    if tool_name not in self._remote_tools:
                        self._remote_tools[tool_name] = []
                    self._remote_tools[tool_name].append(client)
                    self._tool_specs[tool_name] = tool
                    logger.debug(
                        f"Registered remote tool: {tool_name} from {safe_url}"
                    )
            self._mcp_clients.append(client)
            return True
        except Exception as e:
            logger.debug(f"Failed to connect to MCP server {safe_url}: {e}")
            return False

    def get_tool(self, name: str) -> Optional[Any]:
        """获取工具（支持路由）.

        Args:
            name: 工具名称

        Returns:
            本地函数或远程调用包装器，未找到返回 None
        """
        if name in self._local_tools:
            return self._local_tools[name]

        if name in self._remote_tools:
            clients = self._remote_tools[name]

            # 返回包装器，使用路由策略选择客户端
            def remote_wrapper(args: Dict[str, Any]) -> Any:
                """远程工具调用包装器.

                Args:
                    args: 工具参数

                Returns:
                    工具执行结果

                Raises:
                    RuntimeError: 无可用客户端时抛出
                """
                client = self._router.select_client(clients)
                if not client:
                    raise RuntimeError(f"No available client for tool: {name}")
                return client.call_tool(name, args)

            return remote_wrapper

        return None

    def list_all_tools(self) -> List[str]:
        """列出所有可用工具名称.

        Returns:
            工具名称列表
        """
        return list(self._local_tools.keys()) + list(self._remote_tools.keys())

    def list_tool_specs(self) -> List[Dict[str, Any]]:
        """获取所有远程工具的规范定义.

        Returns:
            工具规范字典列表
        """
        return list(self._tool_specs.values())

    def get_tool_spec(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定工具的规范定义.

        Args:
            name: 工具名称

        Returns:
            工具规范字典，不存在则返回 None
        """
        return self._tool_specs.get(name)

    def set_routing_strategy(self, strategy: RoutingStrategy) -> None:
        """设置路由策略.

        Args:
            strategy: 新的路由策略
        """
        self._router.strategy = strategy


# 全局注册中心实例（使用默认路由策略）
registry = ToolRegistry()
