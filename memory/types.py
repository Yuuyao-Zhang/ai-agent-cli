"""记忆系统类型定义.

定义记忆系统的核心类型和数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class MemoryType(Enum):
    """记忆类型枚举.

    Attributes:
        SHORT_TERM: 短期记忆 (活跃窗口)
        MID_TERM: 中期记忆 (摘要/结构化存储)
        LONG_TERM: 长期记忆 (摘要/向量)
    """

    SHORT_TERM = "short_term"
    MID_TERM = "mid_term"
    LONG_TERM = "long_term"


@dataclass
class MemoryEntry:
    """记忆条目.

    Attributes:
        role: 角色
        content: 内容
        timestamp: 时间戳
        importance: 重要性权重 (0.0-1.0)
        tokens: Token 数量
    """

    role: str
    content: str
    timestamp: float
    importance: float = 1.0
    tokens: int = 0


@dataclass
class MemoryStats:
    """记忆统计信息.

    Attributes:
        total_tokens: 总 Token 数
        short_term_count: 短期记忆数量
        mid_term_count: 中期记忆数量
        long_term_summary_len: 长期记忆摘要长度
        compression_ratio: 压缩比率
    """

    total_tokens: int = 0
    short_term_count: int = 0
    mid_term_count: int = 0
    long_term_summary_len: int = 0
    compression_ratio: float = 0.0


@dataclass
class SummaryEntry:
    """中期记忆摘要条目.

    Attributes:
        id: 摘要ID
        session_id: 会话ID
        round_start: 起始轮次
        round_end: 结束轮次
        summary: 摘要内容
        created_at: 创建时间
        keywords: 关键词列表
    """

    id: int
    session_id: str
    round_start: int
    round_end: int
    summary: str
    created_at: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class PromptTemplate:
    """提示词模板.

    Attributes:
        name: 模板名称
        template: 模板内容
        description: 模板描述
        variables: 变量列表
        category: 分类
    """

    name: str
    template: str
    description: str = ""
    variables: List[str] = field(default_factory=list)
    category: str = "general"
