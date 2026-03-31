"""记忆系统类型定义.

定义记忆系统的核心类型和数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class MemoryType(Enum):
    """记忆类型枚举."""
    SHORT_TERM = "short_term"  # 短期记忆 (活跃窗口)
    MID_TERM = "mid_term"      # 中期记忆 (摘要/结构化存储)
    LONG_TERM = "long_term"    # 长期记忆 (摘要/向量)


@dataclass
class MemoryEntry:
    """记忆条目."""
    role: str
    content: str
    timestamp: float
    importance: float = 1.0  # 重要性权重 (0.0-1.0)
    tokens: int = 0


@dataclass
class MemoryStats:
    """记忆统计信息."""
    total_tokens: int = 0
    short_term_count: int = 0
    mid_term_count: int = 0
    long_term_summary_len: int = 0
    compression_ratio: float = 0.0


@dataclass
class SummaryEntry:
    """中期记忆摘要条目."""
    id: int
    session_id: str
    round_start: int
    round_end: int
    summary: str
    created_at: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class PromptTemplate:
    """提示词模板."""
    name: str
    template: str
    description: str = ""
    variables: List[str] = field(default_factory=list)
    category: str = "general"
