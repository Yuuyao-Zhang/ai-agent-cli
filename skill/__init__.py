"""Skill 模块.

提供 Skill 的定义、加载、管理和渐进式披露功能。
"""

from skill.loader import SkillLoader, SkillWriter
from skill.manager import ProgressiveDisclosureEngine, SkillManager, manager
from skill.types import (
    DisclosureLevel,
    Skill,
    SkillExample,
    SkillHint,
    SkillParameter,
)
from skill.vector_index import VectorIndex

__all__ = [
    "DisclosureLevel",
    "Skill",
    "SkillExample",
    "SkillHint",
    "SkillParameter",
    "SkillLoader",
    "SkillWriter",
    "SkillManager",
    "ProgressiveDisclosureEngine",
    "VectorIndex",
    "manager",
]
