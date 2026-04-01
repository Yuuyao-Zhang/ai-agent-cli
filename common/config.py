"""配置文件管理模块.

该模块支持从 YAML 配置文件加载配置，同时保留环境变量支持。
配置加载优先级：环境变量 > 配置文件 > 默认值
"""

import os
import json
import re
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class LLMConfig:
    """LLM 配置."""
    api_key: Optional[str] = None
    model: str = "qwen-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    embedding_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 60


@dataclass
class ContextConfig:
    """上下文占比配置."""
    system_ratio: float = 0.2
    history_ratio: float = 0.6
    file_tree_ratio: float = 0.05
    terminal_ratio: float = 0.05
    dynamic_ratio: float = 0.1


@dataclass
class SecurityConfig:
    """安全配置."""
    trusted_domains: Optional[str] = None
    acl_config: Optional[str] = None


@dataclass
class AppConfig:
    """应用配置."""
    todo_storage_path: str = ".todos.json"
    debug_mode: bool = False
    log_level: str = "INFO"
    checkpoint_dir: str = "checkpoints"
    vector_db_dir: str = "vectordb"
    mcp_data_dir: str = "mcp/mcp_data"
    max_recursion_depth: int = 10
    max_turns_per_agent: int = 20
    max_buffer_lines: int = 50
    max_total_tokens_per_agent: int = 8000
    file_tree_max_depth: int = 3
    file_tree_max_lines: int = 50
    file_ref_truncate_length: int = 500
    recent_file_ops_limit: int = 5
    terminal_output_lines: int = 20


@dataclass
class MCPConfig:
    """MCP 服务器配置."""
    servers: list[str] = field(default_factory=list)


@dataclass
class IntentConfig:
    """意图识别配置."""
    enabled: bool = True
    model: Optional[str] = None
    prompt: Optional[str] = None


@dataclass
class ConfigFile:
    """完整配置文件结构."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    app: AppConfig = field(default_factory=AppConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    intent: IntentConfig = field(default_factory=IntentConfig)


class ConfigFileManager:
    """配置文件管理器."""

    DEFAULT_CONFIG_PATHS = [
        "agent_config.yaml",
        "agent_config.yml",
        ".agent_config.yaml",
        "config/agent_config.yaml",
    ]

    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器.

        Args:
            config_path: 配置文件路径，如果为 None 则自动查找
        """
        self.config_path = self._find_config_file(config_path, self.DEFAULT_CONFIG_PATHS)
        self._config: Optional[ConfigFile] = None
        self._load_config()

    @staticmethod
    def _find_config_file(config_path: Optional[str], default_paths: list) -> Optional[Path]:
        """查找配置文件.

        Args:
            config_path: 指定的配置文件路径
            default_paths: 默认配置文件路径列表

        Returns:
            找到的配置文件路径，如果没找到则返回 None
        """
        if config_path:
            path = Path(config_path)
            if path.exists():
                return path
            return None

        for path_str in default_paths:
            path = Path(path_str)
            if path.exists():
                return path

        return None

    def _load_config(self):
        """加载配置文件."""
        if not self.config_path:
            self._config = ConfigFile()
            return

        if not YAML_AVAILABLE:
            print("[Warning] PyYAML not available, using default config")
            self._config = ConfigFile()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            llm_data = data.get("llm", {})
            context_data = data.get("context", {})
            security_data = data.get("security", {})
            app_data = data.get("app", {})
            mcp_servers_data = data.get("mcpServers", {})
            
            # Ensure mcp_data_dir is set properly if missing from config file
            if "mcp_data_dir" not in app_data:
                app_data["mcp_data_dir"] = "mcp/mcp_data"

            intent_data = data.get("intent", {})

            alias_servers: list[str] = []
            if isinstance(mcp_servers_data, dict):
                for server_value in mcp_servers_data.values():
                    if isinstance(server_value, dict):
                        server_url = server_value.get("url")
                    else:
                        server_url = server_value
                    if isinstance(server_url, str):
                        server_url = server_url.strip().strip("`").strip()
                        server_url = re.sub(
                            r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
                            lambda match: os.getenv(match.group(1), ""),
                            server_url,
                        ).strip()
                        if server_url:
                            alias_servers.append(server_url)

            mcp_data = {"servers": list(dict.fromkeys(alias_servers))}

            self._config = ConfigFile(
                llm=LLMConfig(**llm_data),
                context=ContextConfig(**context_data),
                security=SecurityConfig(**security_data),
                app=AppConfig(**app_data),
                mcp=MCPConfig(**mcp_data),
                intent=IntentConfig(**intent_data),
            )
            self._apply_env_overrides()
        except Exception as e:
            print(f"[Warning] Failed to load config file: {e}, using default config")
            self._config = ConfigFile()
            self._apply_env_overrides()

    def _apply_env_overrides(self):
        """应用环境变量覆盖配置."""
        if not self._config:
            return

        # LLM
        if "DASHSCOPE_API_KEY" in os.environ:
            self._config.llm.api_key = os.environ["DASHSCOPE_API_KEY"]
        if "LLM_MODEL" in os.environ:
            self._config.llm.model = os.environ["LLM_MODEL"]
        if "LLM_BASE_URL" in os.environ:
            self._config.llm.base_url = os.environ["LLM_BASE_URL"]
        if "LLM_EMBEDDING_URL" in os.environ:
            self._config.llm.embedding_url = os.environ["LLM_EMBEDDING_URL"]

        # Security
        if "TRAE_TRUSTED_DOMAINS" in os.environ:
            self._config.security.trusted_domains = os.environ["TRAE_TRUSTED_DOMAINS"]
        if "TRAE_ACL" in os.environ:
            self._config.security.acl_config = os.environ["TRAE_ACL"]

        # App
        if "TRAE_TODO_PATH" in os.environ:
            self._config.app.todo_storage_path = os.environ["TRAE_TODO_PATH"]
        if "DEBUG" in os.environ:
            self._config.app.debug_mode = os.environ["DEBUG"].lower() in ("1", "true", "yes")
        if "LOG_LEVEL" in os.environ:
            self._config.app.log_level = os.environ["LOG_LEVEL"].upper()
        if "CHECKPOINT_DIR" in os.environ:
            self._config.app.checkpoint_dir = os.environ["CHECKPOINT_DIR"]
        if "VECTOR_DB_DIR" in os.environ:
            self._config.app.vector_db_dir = os.environ["VECTOR_DB_DIR"]
        if "MCP_DATA_DIR" in os.environ:
            self._config.app.mcp_data_dir = os.environ["MCP_DATA_DIR"]

    def reload(self):
        """重新加载配置文件（热重载）."""
        self._load_config()

    @property
    def config(self) -> ConfigFile:
        """获取配置对象."""
        return self._config

    def create_default_config(self, path: str = "agent_config.yaml"):
        """创建默认配置文件.

        Args:
            path: 配置文件路径
        """
        if not YAML_AVAILABLE:
            print("[Error] PyYAML not available, cannot create config file")
            return

        default_config = ConfigFile()
        data = {
            "llm": {
                "api_key": None,
                "model": default_config.llm.model,
                "base_url": default_config.llm.base_url,
                "embedding_url": default_config.llm.embedding_url,
                "temperature": default_config.llm.temperature,
                "max_tokens": None,
            },
            "security": {
                "trusted_domains": None,
                "acl_config": None,
            },
            "app": {
                "todo_storage_path": default_config.app.todo_storage_path,
                "debug_mode": default_config.app.debug_mode,
                "log_level": default_config.app.log_level,
                "checkpoint_dir": default_config.app.checkpoint_dir,
                "vector_db_dir": default_config.app.vector_db_dir,
                "mcp_data_dir": default_config.app.mcp_data_dir,
            },
            "mcpServers": {
                "example-server": {
                    "url": "http://localhost:8000/mcp"
                }
            },
            "intent": {
                "enabled": True,
                "model": None,
                "prompt": None,
            }
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print(f"Default config file created at: {path}")


# 全局配置文件管理器和配置实例
config_file_manager = ConfigFileManager()
config = config_file_manager.config
