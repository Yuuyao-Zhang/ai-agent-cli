"""日志系统模块.

提供统一的日志接口，支持不同级别的日志输出和文件记录。
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

from common.config import config


class Logger:
    """日志管理器.

    提供统一的日志接口，支持控制台输出和文件记录。
    """

    _instance: Optional['Logger'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """单例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str = "ai_agent", log_dir: str = "logs"):
        """初始化日志管理器.

        Args:
            name: 日志记录器名称
            log_dir: 日志文件目录
        """
        if Logger._initialized:
            return

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        log_level = getattr(logging, config.app.log_level, logging.INFO)

        # 控制台输出格式
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S"
        )

        # 文件输出格式
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # 文件处理器
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"agent_{datetime.now().strftime('%Y%m%d')}.log")

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)

        Logger._initialized = True

    def debug(self, message: str):
        """输出调试日志.

        Args:
            message: 日志消息
        """
        self.logger.debug(message)

    def info(self, message: str):
        """输出信息日志.

        Args:
            message: 日志消息
        """
        self.logger.info(message)

    def warning(self, message: str):
        """输出警告日志.

        Args:
            message: 日志消息
        """
        self.logger.warning(message)

    def error(self, message: str, exc_info: bool = False):
        """输出错误日志.

        Args:
            message: 日志消息
            exc_info: 是否包含异常堆栈信息
        """
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False):
        """输出严重错误日志.

        Args:
            message: 日志消息
            exc_info: 是否包含异常堆栈信息
        """
        self.logger.critical(message, exc_info=exc_info)


# 全局日志器实例
logger = Logger()
