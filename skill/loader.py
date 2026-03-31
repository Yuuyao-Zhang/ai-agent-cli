"""Skill 加载器模块.

支持从目录加载 Skill 定义文件，支持 JSON 和 YAML 格式。
支持渐进式披露的分层信息加载。
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from skill.types import (
    DisclosureLevel,
    Skill,
    SkillExample,
    SkillHint,
    SkillParameter,
)


class SkillLoader:
    """Skill 加载器.

    从指定目录加载 Skill 定义文件，支持 JSON 和 YAML 格式。
    支持渐进式披露的分层信息加载。

    Attributes:
        skill_dir: Skill 文件所在目录
        SUPPORTED_EXTENSIONS: 支持的文件扩展名
    """

    SUPPORTED_EXTENSIONS: Tuple[str, ...] = (".json", ".yaml", ".yml")

    def __init__(self, skill_dir: str):
        """初始化加载器.

        Args:
            skill_dir: Skill 文件所在目录
        """
        self.skill_dir = skill_dir
        self._yaml_available = self._check_yaml_support()

    @staticmethod
    def _check_yaml_support() -> bool:
        """检查是否支持 YAML.

        Returns:
            支持返回 True，否则返回 False
        """
        try:
            import yaml  # noqa: F401

            return True
        except ImportError:
            return False

    def load_all(self) -> Dict[str, Skill]:
        """加载目录下所有 Skill.

        Returns:
            Skill 字典，键为 Skill 名称
        """
        skills: Dict[str, Skill] = {}
        if not os.path.exists(self.skill_dir):
            os.makedirs(self.skill_dir, exist_ok=True)
            return skills

        for root, _, files in os.walk(self.skill_dir):
            for file in files:
                if file.endswith(self.SUPPORTED_EXTENSIONS):
                    path = os.path.join(root, file)
                    skill = self._load_file(path)
                    if skill:
                        skills[skill.name] = skill
        return skills

    def _load_file(self, path: str) -> Optional[Skill]:
        """加载单个 Skill 文件.

        Args:
            path: 文件路径

        Returns:
            Skill 对象，加载失败返回 None
        """
        try:
            ext = os.path.splitext(path)[1].lower()
            data: Dict[str, Any] = {}

            if ext == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif ext in (".yaml", ".yml"):
                if not self._yaml_available:
                    print("警告: 不支持 YAML，请安装 PyYAML: pip install pyyaml")
                    return None
                import yaml

                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                return None

            return self._parse_skill(data, path)
        except Exception as e:
            print(f"从 {path} 加载技能出错: {e}")
            return None

    def _parse_skill(self, data: Dict[str, Any], path: str) -> Skill:
        """解析 Skill 数据.

        Args:
            data: 原始数据字典
            path: 文件路径

        Returns:
            解析后的 Skill 对象
        """
        parameters = self._parse_parameters(data.get("parameters", []))
        examples = self._parse_examples(data.get("examples", []))
        hints = self._parse_hints(data.get("hints", []))

        disclosure_str = data.get("disclosure_level", "brief")
        try:
            disclosure_level = DisclosureLevel(disclosure_str)
        except ValueError:
            disclosure_level = DisclosureLevel.BRIEF

        return Skill(
            name=data.get("name", ""),
            description=data.get("description", ""),
            summary=data.get("summary", ""),
            content=data.get("content", ""),
            parameters=parameters,
            examples=examples,
            hints=hints,
            dependencies=data.get("dependencies", []),
            tags=data.get("tags", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            category=data.get("category", "general"),
            advanced_config=data.get("advanced_config", {}),
            embedding=data.get("embedding", []),
            path=path,
            disclosure_level=disclosure_level,
        )

    def _parse_parameters(self, data: List[Dict[str, Any]]) -> List[SkillParameter]:
        """解析参数列表.

        Args:
            data: 参数数据列表

        Returns:
            SkillParameter 对象列表
        """
        parameters = []
        for item in data:
            param = SkillParameter(
                name=item.get("name", ""),
                type=item.get("type", "str"),
                description=item.get("description", ""),
                required=item.get("required", True),
                default=item.get("default"),
                choices=item.get("choices", []),
            )
            parameters.append(param)
        return parameters

    def _parse_examples(self, data: List[Dict[str, Any]]) -> List[SkillExample]:
        """解析示例列表.

        Args:
            data: 示例数据列表

        Returns:
            SkillExample 对象列表
        """
        examples = []
        for item in data:
            example = SkillExample(
                description=item.get("description", ""),
                input=item.get("input", ""),
                output=item.get("output", ""),
                explanation=item.get("explanation", ""),
            )
            examples.append(example)
        return examples

    def _parse_hints(self, data: List[Dict[str, Any]]) -> List[SkillHint]:
        """解析提示列表.

        Args:
            data: 提示数据列表

        Returns:
            SkillHint 对象列表
        """
        hints = []
        for item in data:
            hint = SkillHint(
                condition=item.get("condition", ""),
                suggestion=item.get("suggestion", ""),
                priority=item.get("priority", 5),
            )
            hints.append(hint)
        return hints

    def load_skill_by_name(self, name: str) -> Optional[Skill]:
        """按名称加载单个 Skill.

        Args:
            name: Skill 名称

        Returns:
            Skill 对象，未找到返回 None
        """
        if not os.path.exists(self.skill_dir):
            return None

        for root, _, files in os.walk(self.skill_dir):
            for file in files:
                if file.endswith(self.SUPPORTED_EXTENSIONS):
                    path = os.path.join(root, file)
                    skill = self._load_file(path)
                    if skill and skill.name == name:
                        return skill
        return None


class SkillWriter:
    """Skill 写入器.

    支持将 Skill 对象写入文件，支持 JSON 和 YAML 格式。

    Attributes:
        skill_dir: Skill 文件所在目录
    """

    def __init__(self, skill_dir: str):
        """初始化写入器.

        Args:
            skill_dir: Skill 文件所在目录
        """
        self.skill_dir = skill_dir
        self._yaml_available = self._check_yaml_support()
        os.makedirs(skill_dir, exist_ok=True)

    @staticmethod
    def _check_yaml_support() -> bool:
        """检查是否支持 YAML."""
        try:
            import yaml  # noqa: F401

            return True
        except ImportError:
            return False

    def save_skill(self, skill: Skill, fmt: str = "json") -> str:
        """保存 Skill 到文件.

        Args:
            skill: Skill 对象
            fmt: 文件格式 ("json" 或 "yaml")

        Returns:
            保存的文件路径
        """
        data = self._skill_to_dict(skill)

        if fmt == "yaml" and self._yaml_available:
            import yaml

            filename = f"{skill.name}.yaml"
            path = os.path.join(self.skill_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
        else:
            filename = f"{skill.name}.json"
            path = os.path.join(self.skill_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return path

    def _skill_to_dict(self, skill: Skill) -> Dict[str, Any]:
        """将 Skill 转换为字典.

        Args:
            skill: Skill 对象

        Returns:
            字典表示
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
                    "choices": p.choices,
                }
                for p in skill.parameters
            ],
            "examples": [
                {
                    "description": e.description,
                    "input": e.input,
                    "output": e.output,
                    "explanation": e.explanation,
                }
                for e in skill.examples
            ],
            "hints": [
                {
                    "condition": h.condition,
                    "suggestion": h.suggestion,
                    "priority": h.priority,
                }
                for h in skill.hints
            ],
            "dependencies": skill.dependencies,
            "tags": skill.tags,
            "version": skill.version,
            "author": skill.author,
            "category": skill.category,
            "advanced_config": skill.advanced_config,
            "disclosure_level": skill.disclosure_level.value,
        }

    def create_skill_template(self, name: str, fmt: str = "json") -> str:
        """创建 Skill 模板文件.

        Args:
            name: Skill 名称
            fmt: 文件格式

        Returns:
            创建的文件路径
        """
        skill = Skill(
            name=name,
            description=f"{name} skill description",
            summary=f"Summary of {name} skill",
            content=f"Content/Prompt template for {name}",
            parameters=[
                SkillParameter(
                    name="param1",
                    type="str",
                    description="Parameter description",
                    required=True,
                )
            ],
            examples=[
                SkillExample(
                    description="Example description",
                    input="Example input",
                    output="Example output",
                    explanation="Example explanation",
                )
            ],
            hints=[
                SkillHint(
                    condition="condition keyword",
                    suggestion="Suggestion for this condition",
                    priority=5,
                )
            ],
            tags=["tag1", "tag2"],
            category="general",
        )
        return self.save_skill(skill, fmt)
