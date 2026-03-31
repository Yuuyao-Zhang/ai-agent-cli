"""Skill 类型定义模块.

定义 Skill 的数据结构，支持渐进式披露 (Progressive Disclosure)。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class DisclosureLevel(Enum):
    """渐进式披露级别枚举.

    定义 Skill 信息展示的详细程度，从简到繁逐层递进。

    Attributes:
        BRIEF: 简要信息，仅展示名称和简短描述
        SUMMARY: 摘要信息，展示摘要和关键特性
        DETAILED: 详细信息，展示完整内容和使用示例
        FULL: 完整信息，展示所有可用信息包括高级配置
    """

    BRIEF = "brief"
    SUMMARY = "summary"
    DETAILED = "detailed"
    FULL = "full"


@dataclass
class SkillExample:
    """Skill 使用示例.

    Attributes:
        description: 示例描述
        input: 输入示例
        output: 输出示例
        explanation: 示例解释
    """

    description: str = ""
    input: str = ""
    output: str = ""
    explanation: str = ""


@dataclass
class SkillHint:
    """Skill 使用提示.

    Attributes:
        condition: 触发条件描述
        suggestion: 建议内容
        priority: 优先级 (1-10, 越高越重要)
    """

    condition: str = ""
    suggestion: str = ""
    priority: int = 5


@dataclass
class SkillParameter:
    """Skill 参数定义.

    Attributes:
        name: 参数名称
        type: 参数类型
        description: 参数描述
        required: 是否必需
        default: 默认值
        choices: 可选值列表
    """

    name: str = ""
    type: str = "str"
    description: str = ""
    required: bool = True
    default: Any = None
    choices: List[str] = field(default_factory=list)


@dataclass
class Skill:
    """Skill 数据结构.

    支持渐进式披露的 Skill 定义，包含多层信息展示。

    Attributes:
        name: Skill 名称 (唯一标识)
        description: 简短描述 (用于 BRIEF 级别)
        summary: 功能摘要 (用于 SUMMARY 级别)
        content: 完整内容/Prompt 模板 (用于 DETAILED 级别)
        parameters: 参数定义列表
        examples: 使用示例列表
        hints: 使用提示列表
        dependencies: 依赖的其他 Skill 名称
        tags: 标签列表
        version: 版本号
        author: 作者
        category: 分类
        advanced_config: 高级配置 (用于 FULL 级别)
        embedding: 向量嵌入
        path: 文件路径
        disclosure_level: 当前披露级别
    """

    name: str
    description: str
    summary: str = ""
    content: str = ""
    parameters: List[SkillParameter] = field(default_factory=list)
    examples: List[SkillExample] = field(default_factory=list)
    hints: List[SkillHint] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    advanced_config: Dict[str, Any] = field(default_factory=dict)
    embedding: List[float] = field(default_factory=list)
    path: str = ""
    disclosure_level: DisclosureLevel = DisclosureLevel.BRIEF

    @staticmethod
    def get_brief_info(skill) -> Dict[str, str]:
        """获取简要信息 (BRIEF 级别).

        Args:
            skill: Skill 实例

        Returns:
            包含名称和描述的字典
        """
        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
        }

    @staticmethod
    def get_summary_info(skill) -> Dict[str, Any]:
        """获取摘要信息 (SUMMARY 级别).

        Args:
            skill: Skill 实例

        Returns:
            包含摘要和关键特性的字典
        """
        return {
            "name": skill.name,
            "description": skill.description,
            "summary": skill.summary,
            "category": skill.category,
            "tags": skill.tags,
            "parameters_count": len(skill.parameters),
            "examples_count": len(skill.examples),
        }

    @staticmethod
    def get_detailed_info(skill) -> Dict[str, Any]:
        """获取详细信息 (DETAILED 级别).

        Args:
            skill: Skill 实例

        Returns:
            包含完整内容和使用示例的字典
        """
        return {
            "name": skill.name,
            "description": skill.description,
            "summary": skill.summary,
            "content": skill.content,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in skill.parameters
            ],
            "examples": [
                {
                    "description": e.description,
                    "input": e.input,
                    "output": e.output,
                }
                for e in skill.examples
            ],
            "hints": [
                {"condition": h.condition, "suggestion": h.suggestion}
                for h in sorted(skill.hints, key=lambda x: x.priority, reverse=True)
            ],
            "dependencies": skill.dependencies,
            "tags": skill.tags,
            "version": skill.version,
        }

    @staticmethod
    def get_full_info(skill) -> Dict[str, Any]:
        """获取完整信息 (FULL 级别).

        Args:
            skill: Skill 实例

        Returns:
            包含所有可用信息的字典
        """
        detailed = Skill.get_detailed_info(skill)
        detailed.update(
            {
                "author": skill.author,
                "advanced_config": skill.advanced_config,
                "path": skill.path,
                "embedding_dim": len(skill.embedding) if skill.embedding else 0,
            }
        )
        return detailed

    def disclose(self, level: DisclosureLevel) -> Dict[str, Any]:
        """按指定级别披露信息.

        Args:
            level: 披露级别

        Returns:
            对应级别的信息字典
        """
        level_handlers = {
            DisclosureLevel.BRIEF: Skill.get_brief_info,
            DisclosureLevel.SUMMARY: Skill.get_summary_info,
            DisclosureLevel.DETAILED: Skill.get_detailed_info,
            DisclosureLevel.FULL: Skill.get_full_info,
        }
        handler = level_handlers.get(level, Skill.get_brief_info)
        return handler(self)

    def get_relevant_hints(self, context: str) -> List[SkillHint]:
        """根据上下文获取相关提示.

        Args:
            context: 当前上下文描述

        Returns:
            相关提示列表，按优先级排序
        """
        relevant = []
        context_lower = context.lower()
        for hint in self.hints:
            if hint.condition.lower() in context_lower:
                relevant.append(hint)
        return sorted(relevant, key=lambda x: x.priority, reverse=True)

    def to_prompt(self, level: DisclosureLevel = DisclosureLevel.DETAILED) -> str:
        """将 Skill 转换为 Prompt 格式.

        Args:
            level: 披露级别

        Returns:
            格式化的 Prompt 字符串
        """
        info = self.disclose(level)
        lines = [f"# Skill: {self.name}", ""]

        if level == DisclosureLevel.BRIEF:
            lines.append(f"Description: {info['description']}")
            lines.append(f"Category: {info['category']}")
        elif level == DisclosureLevel.SUMMARY:
            lines.append(f"Description: {info['description']}")
            lines.append(f"Summary: {info['summary']}")
            lines.append(f"Tags: {', '.join(info['tags']) if info['tags'] else 'None'}")
        else:
            lines.append(f"Version: {self.version}")
            lines.append(f"Description: {self.description}")
            lines.append("")
            lines.append("## Summary")
            lines.append(self.summary if self.summary else self.description)
            lines.append("")

            if self.parameters:
                lines.append("## Parameters")
                for p in self.parameters:
                    req = "required" if p.required else "optional"
                    lines.append(f"- {p.name} ({p.type}, {req}): {p.description}")
                    if p.default is not None:
                        lines.append(f"  Default: {p.default}")
                lines.append("")

            if level in (DisclosureLevel.DETAILED, DisclosureLevel.FULL):
                lines.append("## Content")
                lines.append(self.content)
                lines.append("")

                if self.examples:
                    lines.append("## Examples")
                    for i, e in enumerate(self.examples, 1):
                        lines.append(f"### Example {i}: {e.description}")
                        if e.input:
                            lines.append(f"Input: {e.input}")
                        if e.output:
                            lines.append(f"Output: {e.output}")
                        if e.explanation:
                            lines.append(f"Explanation: {e.explanation}")
                        lines.append("")

                if self.hints:
                    lines.append("## Hints")
                    for h in sorted(self.hints, key=lambda x: x.priority, reverse=True):
                        lines.append(f"- [{h.condition}] {h.suggestion}")
                    lines.append("")

            if level == DisclosureLevel.FULL and self.advanced_config:
                lines.append("## Advanced Configuration")
                for key, value in self.advanced_config.items():
                    lines.append(f"- {key}: {value}")

        return "\n".join(lines)
