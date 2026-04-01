"""MCP 客户端模块.

实现 Model Context Protocol (MCP) 的客户端功能，
目前支持通过 HTTP 协议连接外部 Tool Server。
"""

import json
import time
import urllib.request
import urllib.error
import uuid
from typing import Any, Dict, Optional


class MCPClient:
    """MCP 客户端.
    
    负责与 MCP Server 进行通信，发送 JSON-RPC 2.0 请求。
    """

    def __init__(self, server_url: str, timeout: int = 30):
        """初始化 MCP 客户端.

        Args:
            server_url: MCP Server 的 URL 地址
            timeout: 请求超时时间（秒），默认为 30
        """
        self.server_url = server_url
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.initialized = False
        self.server_info: Dict[str, Any] = {}
        self.server_capabilities: Dict[str, Any] = {}

    def initialize(self) -> Dict[str, Any]:
        """初始化与 MCP Server 的会话.

        发送初始化请求，建立会话连接，获取服务器信息和能力。

        Returns:
            包含服务器信息和能力的字典
        """
        if self.initialized:
            return {
                "serverInfo": self.server_info,
                "capabilities": self.server_capabilities,
            }

        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "AI-agent-CLI",
                    "version": "1.0.0",
                },
            },
            "id": str(uuid.uuid4()),
        }
        result = self._send_request(payload)
        self.server_info = result.get("serverInfo", {}) if isinstance(result, dict) else {}
        self.server_capabilities = result.get("capabilities", {}) if isinstance(result, dict) else {}
        self._send_notification("notifications/initialized", {})
        self.initialized = True
        return result if isinstance(result, dict) else {}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用远程工具.

        Args:
            tool_name: 工具名称
            arguments: 工具参数字典

        Returns:
            工具执行结果
        """
        self.initialize()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": str(uuid.uuid4())
        }

        return self._send_request(payload)

    def list_tools(self) -> list:
        """获取服务器提供的工具列表.

        Returns:
            工具规范字典列表
        """
        self.initialize()
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": str(uuid.uuid4())
        }
        result = self._send_request(payload)
        if isinstance(result, dict):
            return result.get("tools", [])
        return []

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """发送 JSON-RPC 通知请求.

        通知请求不期待响应，用于发送事件通知。

        Args:
            method: JSON-RPC 方法名
            params: 请求参数字典
        """
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        self._send_request(payload, expect_response=False)

    def _build_headers(self) -> Dict[str, str]:
        """构建 HTTP 请求头.

        Returns:
            包含必要请求头的字典
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _parse_sse_response(self, response_text: str) -> Dict[str, Any]:
        """解析 Server-Sent Events (SSE) 响应.

        从 SSE 格式的响应中提取 JSON 数据。

        Args:
            response_text: SSE 响应文本

        Returns:
            解析后的 JSON 对象

        Raises:
            RuntimeError: 无法解析有效数据时抛出
        """
        events: list[str] = []
        current_data: list[str] = []
        for line in response_text.splitlines():
            if line.startswith("data:"):
                current_data.append(line[5:].lstrip())
                continue
            if not line.strip() and current_data:
                events.append("\n".join(current_data))
                current_data = []
        if current_data:
            events.append("\n".join(current_data))

        for event_data in reversed(events):
            if not event_data:
                continue
            try:
                parsed = json.loads(event_data)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        raise RuntimeError("Invalid SSE response payload")

    def _send_request(
        self,
        payload: Dict[str, Any],
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        expect_response: bool = True,
    ) -> Any:
        """发送 JSON-RPC 请求并处理响应（带重试机制）.

        Args:
            payload: JSON-RPC 请求体
            max_retries: 最大重试次数，默认为 3
            backoff_factor: 退避系数（秒），默认为 1.0

        Returns:
            响应结果

        Raises:
            RuntimeError: 所有重试失败后抛出
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self.server_url,
                    data=data,
                    headers=self._build_headers(),
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    session_id = response.headers.get("Mcp-Session-Id")
                    if session_id:
                        self.session_id = session_id

                    resp_data = response.read().decode("utf-8")
                    if not resp_data.strip():
                        return {}

                    content_type = response.headers.get("Content-Type", "")
                    if "text/event-stream" in content_type or resp_data.lstrip().startswith("event:") or resp_data.lstrip().startswith("data:"):
                        resp_json = self._parse_sse_response(resp_data)
                    else:
                        resp_json = json.loads(resp_data)

                    if "error" in resp_json:
                        error_obj = resp_json["error"]
                        # 某些错误不需要重试（如认证错误）
                        if isinstance(error_obj, dict):
                            code = error_obj.get("code", 0)
                            # JSON-RPC 标准错误码：-32602 参数错误，-32601 方法未找到
                            if code in (-32602, -32601):
                                raise RuntimeError(f"MCP Error: {error_obj}")
                        raise RuntimeError(f"MCP Error: {error_obj}")

                    if not expect_response:
                        return {}

                    return resp_json.get("result", {})

            except urllib.error.HTTPError as e:
                last_error = e
                # 429 (Rate Limit) 和 503 (Service Unavailable) 可重试
                if e.code in (429, 503) and attempt < max_retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    error_body = ""
                error_detail = f"HTTP Error {e.code}: {e.reason}"
                if error_body:
                    error_detail = f"{error_detail} | {error_body[:500]}"
                raise RuntimeError(error_detail)

            except urllib.error.URLError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(
                    f"Connection failed to {self.server_url} "
                    f"after {max_retries} retries: {last_error}"
                )

            except Exception as e:
                # 其他异常不重试，直接抛出
                raise RuntimeError(f"MCP Request failed: {e}")

        raise RuntimeError(f"Max retries exceeded: {last_error}")
