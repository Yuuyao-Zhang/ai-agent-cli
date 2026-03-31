"""配置管理模块.

该模块统一管理所有环境变量配置和配置文件，提供统一的配置访问接口。
配置优先级：环境变量 > 配置文件 > 默认值
"""

import os
from typing import Optional

try:
    from common.config_file import config_file_manager
    CONFIG_FILE_AVAILABLE = True
except ImportError:
    CONFIG_FILE_AVAILABLE = False


class Config:
    """配置类.

    统一管理所有环境变量配置和配置文件，提供类型安全的访问方法。
    所有配置项都有默认值，确保在没有设置环境变量时也能正常工作。

    配置优先级：
        1. 环境变量
        2. 配置文件 (YAML)
        3. 默认值

    Attributes:
        无实例属性，所有方法均为静态方法
    """

    # ==================== LLM 配置 ====================
    @staticmethod
    def get_llm_api_key() -> Optional[str]:
        """获取 LLM API 密钥.

        优先级：环境变量 DASHSCOPE_API_KEY > 配置文件 > None

        Returns:
            API 密钥字符串，如果未设置则返回 None
        """
        env_key = os.environ.get("DASHSCOPE_API_KEY")
        if env_key:
            return env_key
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.llm.api_key
        return None

    @staticmethod
    def get_llm_model() -> str:
        """获取 LLM 模型名称.

        优先级：环境变量 LLM_MODEL > 配置文件 > "qwen-plus"

        Returns:
            模型名称
        """
        env_model = os.environ.get("LLM_MODEL")
        if env_model:
            return env_model
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.llm.model
        return "qwen-plus"

    @staticmethod
    def get_llm_base_url() -> str:
        """获取 LLM API 基础 URL.

        优先级：环境变量 LLM_BASE_URL > 配置文件 > 默认值

        Returns:
            API 基础 URL
        """
        env_url = os.environ.get("LLM_BASE_URL")
        if env_url:
            return env_url
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.llm.base_url
        return "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    @staticmethod
    def get_llm_embedding_url() -> str:
        """获取 LLM Embedding API URL.

        优先级：环境变量 LLM_EMBEDDING_URL > 配置文件 > 默认值

        Returns:
            Embedding API URL
        """
        env_url = os.environ.get("LLM_EMBEDDING_URL")
        if env_url:
            return env_url
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.llm.embedding_url
        return "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"

    # ==================== 安全策略配置 ====================
    @staticmethod
    def get_trusted_domains() -> Optional[str]:
        """获取可信域名列表.

        优先级：环境变量 TRAE_TRUSTED_DOMAINS > 配置文件 > None

        Returns:
            逗号分隔的域名列表，如果未设置则返回 None
        """
        env_domains = os.environ.get("TRAE_TRUSTED_DOMAINS")
        if env_domains:
            return env_domains
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.security.trusted_domains
        return None

    @staticmethod
    def get_acl_config() -> Optional[str]:
        """获取 ACL 配置 JSON 字符串.

        优先级：环境变量 TRAE_ACL > 配置文件 > None

        Returns:
            ACL 配置的 JSON 字符串，如果未设置则返回 None
        """
        env_acl = os.environ.get("TRAE_ACL")
        if env_acl:
            return env_acl
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.security.acl_config
        return None

    # ==================== 应用配置 ====================
    @staticmethod
    def get_todo_storage_path() -> str:
        """获取 To-do 存储文件路径.

        优先级：环境变量 TRAE_TODO_PATH > 配置文件 > ".todos.json"

        Returns:
            存储文件路径
        """
        env_path = os.environ.get("TRAE_TODO_PATH")
        if env_path:
            return env_path
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.app.todo_storage_path
        return ".todos.json"

    @staticmethod
    def is_debug_mode() -> bool:
        """检查是否处于调试模式.

        优先级：环境变量 DEBUG > 配置文件 > False

        Returns:
            如果 DEBUG 设置为 "1", "true" 或 "yes" 则返回 True
        """
        env_debug = os.environ.get("DEBUG", "").lower()
        if env_debug in ("1", "true", "yes"):
            return True
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.app.debug_mode
        return False

    @staticmethod
    def get_log_level() -> str:
        """获取日志级别.

        优先级：环境变量 LOG_LEVEL > 配置文件 > "INFO"

        Returns:
            日志级别
        """
        env_level = os.environ.get("LOG_LEVEL")
        if env_level:
            return env_level.upper()
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.app.log_level.upper()
        return "INFO"

    @staticmethod
    def get_checkpoint_dir() -> str:
        """获取快照存储目录.

        优先级：环境变量 > 配置文件 > "checkpoints"

        Returns:
            快照存储目录
        """
        env_dir = os.environ.get("CHECKPOINT_DIR")
        if env_dir:
            return env_dir
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.app.checkpoint_dir
        return "checkpoints"

    @staticmethod
    def get_vector_db_dir() -> str:
        """获取向量数据库存储目录.

        优先级：环境变量 > 配置文件 > "vectordb"

        Returns:
            向量数据库存储目录
        """
        env_dir = os.environ.get("VECTOR_DB_DIR")
        if env_dir:
            return env_dir
        if CONFIG_FILE_AVAILABLE:
            return config_file_manager.config.app.vector_db_dir
        return "vectordb"


# 全局配置实例
config = Config()
