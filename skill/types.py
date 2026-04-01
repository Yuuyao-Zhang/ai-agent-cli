"""Skill 类型定义模块.

定义更贴近 Anthropic/Claude 风格的 Skill 数据结构，
同时保持对现有渐进式披露能力的兼容。
"""

from dataclasses import dataclass, field
from enum import Enum
import fnmatch
import os
import re
from typing import Any, Dict, List, Optional


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
class SkillSupportingFile:
    """Skill 配套文件."""

    path: str = ""
    content: str = ""


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
        skill_dir: Skill 所在目录
        source_format: 技能来源格式 (legacy / claude)
        argument_hint: 手动调用时的参数提示
        disable_model_invocation: 是否禁止模型自动触发
        user_invocable: 是否允许用户直接触发
        allowed_tools: 激活该 skill 时默认允许的工具
        model: skill 建议模型
        effort: skill 建议推理强度
        context: skill 上下文模式
        agent: skill 建议 agent
        hooks: skill hooks 配置
        paths: skill 生效路径限制
        shell: skill 建议 shell
        supporting_files: 配套文件
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
    skill_dir: str = ""
    source_format: str = "legacy"
    argument_hint: str = ""
    disable_model_invocation: bool = False
    user_invocable: bool = True
    allowed_tools: List[str] = field(default_factory=list)
    model: str = ""
    effort: str = ""
    context: str = ""
    agent: str = ""
    hooks: Dict[str, Any] = field(default_factory=dict)
    paths: List[str] = field(default_factory=list)
    shell: str = ""
    supporting_files: List[SkillSupportingFile] = field(default_factory=list)
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
            "source_format": skill.source_format,
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
            "allowed_tools": skill.allowed_tools,
            "user_invocable": skill.user_invocable,
            "disable_model_invocation": skill.disable_model_invocation,
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
            "argument_hint": skill.argument_hint,
            "allowed_tools": skill.allowed_tools,
            "user_invocable": skill.user_invocable,
            "disable_model_invocation": skill.disable_model_invocation,
            "paths": skill.paths,
            "supporting_files": [f.path for f in skill.supporting_files],
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
                "skill_dir": skill.skill_dir,
                "embedding_dim": len(skill.embedding) if skill.embedding else 0,
                "source_format": skill.source_format,
                "model": skill.model,
                "effort": skill.effort,
                "context": skill.context,
                "agent": skill.agent,
                "hooks": skill.hooks,
                "shell": skill.shell,
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

    def supports_auto_invocation(self) -> bool:
        """是否允许模型自动触发该 skill."""
        return not self.disable_model_invocation

    def supports_user_invocation(self) -> bool:
        """是否允许用户显式触发该 skill."""
        return self.user_invocable

    def applies_to_path(self, candidate_path: str) -> bool:
        """判断 skill 是否适用于指定路径."""
        if not self.paths:
            return True

        normalized = candidate_path.replace("\\", "/")
        for pattern in self.paths:
            if fnmatch.fnmatch(normalized, pattern.replace("\\", "/")):
                return True
        return False

    def applies_to_any_path(self, candidate_paths: List[str]) -> bool:
        """判断 skill 是否适用于一组路径."""
        if not self.paths:
            return True
        return any(self.applies_to_path(path) for path in candidate_paths)

    @staticmethod
    def _replace_argument_tokens(text: str, arguments: str) -> str:
        """替换 Claude 风格参数占位符."""
        if not text:
            return text

        args = arguments.strip()
        parts = args.split() if args else []

        def replace_index(match: re.Match) -> str:
            try:
                idx = int(match.group(1))
            except ValueError:
                return ""
            return parts[idx] if 0 <= idx < len(parts) else ""

        rendered = text.replace("$ARGUMENTS", args)
        rendered = re.sub(r"\$ARGUMENTS\[(\d+)\]", replace_index, rendered)
        rendered = re.sub(r"\$(\d+)", replace_index, rendered)
        return rendered

    def render_instruction(self, arguments: str = "") -> str:
        """渲染 skill 指令正文."""
        rendered = self._replace_argument_tokens(self.content, arguments)
        rendered = rendered.replace(
            "${CLAUDE_SKILL_DIR}",
            self.skill_dir.replace("\\", "/") if self.skill_dir else "",
        )

        if arguments.strip() and "$ARGUMENTS" not in self.content:
            rendered = rendered.rstrip() + f"\n\nARGUMENTS: {arguments.strip()}"
        return rendered.strip()

    def to_prompt(
        self,
        level: DisclosureLevel = DisclosureLevel.DETAILED,
        arguments: str = "",
    ) -> str:
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
            if self.argument_hint:
                lines.append(f"Arguments: {self.argument_hint}")
        elif level == DisclosureLevel.SUMMARY:
            lines.append(f"Description: {info['description']}")
            lines.append(f"Summary: {info['summary']}")
            lines.append(f"Tags: {', '.join(info['tags']) if info['tags'] else 'None'}")
            if self.allowed_tools:
                lines.append(f"Allowed Tools: {', '.join(self.allowed_tools)}")
        else:
            lines.append(f"Version: {self.version}")
            lines.append(f"Description: {self.description}")
            lines.append("")
            lines.append("## Summary")
            lines.append(self.summary if self.summary else self.description)
            lines.append("")

            if self.argument_hint:
                lines.append("## Argument Hint")
                lines.append(self.argument_hint)
                lines.append("")

            if self.allowed_tools:
                lines.append("## Allowed Tools")
                lines.append(", ".join(self.allowed_tools))
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
                lines.append(self.render_instruction(arguments))
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

                if self.supporting_files:
                    lines.append("## Supporting Files")
                    for supporting_file in self.supporting_files:
                        lines.append(f"- {supporting_file.path}")
                    lines.append("")

                    for supporting_file in self.supporting_files:
                        if not supporting_file.content.strip():
                            continue
                        lines.append(f"### File: {supporting_file.path}")
                        lines.append(supporting_file.content)
                        lines.append("")

            if level == DisclosureLevel.FULL and self.advanced_config:
                lines.append("## Advanced Configuration")
                for key, value in self.advanced_config.items():
                    lines.append(f"- {key}: {value}")

            if level == DisclosureLevel.FULL:
                lines.append("")
                lines.append("## Invocation Control")
                lines.append(f"- Auto Invocation: {self.supports_auto_invocation()}")
                lines.append(f"- User Invocable: {self.supports_user_invocation()}")
                if self.paths:
                    lines.append(f"- Paths: {', '.join(self.paths)}")
                if self.model:
                    lines.append(f"- Model: {self.model}")
                if self.effort:
                    lines.append(f"- Effort: {self.effort}")
                if self.context:
                    lines.append(f"- Context: {self.context}")
                if self.agent:
                    lines.append(f"- Agent: {self.agent}")
                if self.shell:
                    lines.append(f"- Shell: {self.shell}")

        return "\n".join(lines)
