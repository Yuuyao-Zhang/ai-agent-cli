"""Skill 加载器模块.

支持传统 JSON/YAML Skill 与 Anthropic 风格目录型 SKILL.md。
"""

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from skill.types import (
    DisclosureLevel,
    Skill,
    SkillExample,
    SkillHint,
    SkillParameter,
    SkillSupportingFile,
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

    def __init__(self, skill_dir: Union[str, List[str]]):
        """初始化加载器.

        Args:
            skill_dir: Skill 文件所在目录
        """
        if isinstance(skill_dir, str):
            skill_dirs = [skill_dir]
        else:
            skill_dirs = skill_dir
        self.skill_dirs = [os.path.abspath(path) for path in skill_dirs]
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
        for skill_dir in self.skill_dirs:
            if not os.path.exists(skill_dir):
                os.makedirs(skill_dir, exist_ok=True)
                continue

            for path in self._iter_skill_files(skill_dir):
                skill = self._load_file(path)
                if skill and skill.name:
                    skills[skill.name] = skill
        return skills

    def _iter_skill_files(self, skill_dir: str) -> Iterable[str]:
        """遍历所有 skill 入口文件."""
        for root, _, files in os.walk(skill_dir):
            for file in files:
                full_path = os.path.join(root, file)
                if file.endswith(self.SUPPORTED_EXTENSIONS):
                    yield full_path
                elif file == "SKILL.md":
                    yield full_path

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

            if os.path.basename(path) == "SKILL.md":
                return self._load_markdown_skill(path)

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

    def _load_markdown_skill(self, path: str) -> Optional[Skill]:
        """加载 Anthropic 风格目录型 SKILL.md."""
        try:
            raw_text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"读取 {path} 失败: {e}")
            return None

        frontmatter, body = self._split_frontmatter(raw_text)
        meta = self._parse_frontmatter(frontmatter)
        skill_dir = str(Path(path).resolve().parent)
        description = str(meta.get("description", "")).strip()

        if not description:
            description = self._extract_first_paragraph(body)

        name = str(meta.get("name", "")).strip() or Path(skill_dir).name
        tags = self._coerce_string_list(meta.get("tags", []))
        allowed_tools = self._coerce_string_list(meta.get("allowed-tools", []))
        paths = self._coerce_string_list(meta.get("paths", []))
        supporting_files = self._collect_supporting_files(skill_dir, body)
        summary = self._extract_summary(body, description)

        known_keys = {
            "name",
            "description",
            "argument-hint",
            "disable-model-invocation",
            "user-invocable",
            "allowed-tools",
            "model",
            "effort",
            "context",
            "agent",
            "hooks",
            "paths",
            "shell",
            "tags",
            "category",
            "summary",
            "version",
            "author",
            "dependencies",
        }
        advanced_config = {
            key: value for key, value in meta.items() if key not in known_keys
        }

        return Skill(
            name=name,
            description=description,
            summary=str(meta.get("summary", "")).strip() or summary,
            content=body.strip(),
            parameters=[],
            examples=[],
            hints=[],
            dependencies=self._coerce_string_list(meta.get("dependencies", [])),
            tags=tags,
            version=str(meta.get("version", "1.0.0")),
            author=str(meta.get("author", "")),
            category=str(meta.get("category", "claude-skill")),
            advanced_config=advanced_config,
            embedding=[],
            path=path,
            skill_dir=skill_dir,
            source_format="claude",
            argument_hint=str(meta.get("argument-hint", "")).strip(),
            disable_model_invocation=self._coerce_bool(
                meta.get("disable-model-invocation", False)
            ),
            user_invocable=self._coerce_bool(meta.get("user-invocable", True)),
            allowed_tools=allowed_tools,
            model=str(meta.get("model", "")).strip(),
            effort=str(meta.get("effort", "")).strip(),
            context=str(meta.get("context", "")).strip(),
            agent=str(meta.get("agent", "")).strip(),
            hooks=meta.get("hooks", {}) if isinstance(meta.get("hooks", {}), dict) else {},
            paths=paths,
            shell=str(meta.get("shell", "")).strip(),
            supporting_files=supporting_files,
            disclosure_level=DisclosureLevel.DETAILED,
        )

    @staticmethod
    def _split_frontmatter(text: str) -> Tuple[str, str]:
        """拆分 frontmatter 与正文."""
        if not text.startswith("---"):
            return "", text

        parts = text.split("\n")
        if not parts:
            return "", text

        for idx in range(1, len(parts)):
            if parts[idx].strip() == "---":
                frontmatter = "\n".join(parts[1:idx])
                body = "\n".join(parts[idx + 1:])
                return frontmatter, body
        return "", text

    def _parse_frontmatter(self, text: str) -> Dict[str, Any]:
        """解析 YAML frontmatter."""
        if not text.strip():
            return {}

        if self._yaml_available:
            try:
                import yaml

                loaded = yaml.safe_load(text)
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                pass

        result: Dict[str, Any] = {}
        current_list_key: Optional[str] = None
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue

            stripped = line.strip()
            if stripped.startswith("- ") and current_list_key:
                result.setdefault(current_list_key, [])
                result[current_list_key].append(self._strip_quotes(stripped[2:].strip()))
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if not value:
                result[key] = []
                current_list_key = key
                continue

            current_list_key = None
            if "," in value and key in {"allowed-tools", "paths", "tags", "dependencies"}:
                result[key] = [
                    self._strip_quotes(item.strip())
                    for item in value.split(",")
                    if item.strip()
                ]
            else:
                result[key] = self._coerce_scalar(self._strip_quotes(value))

        return result

    @staticmethod
    def _strip_quotes(text: str) -> str:
        """移除首尾引号."""
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
            return text[1:-1]
        return text

    @staticmethod
    def _coerce_scalar(value: str) -> Any:
        """将文本值转为简单标量."""
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        return value

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        """转换布尔值."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _coerce_string_list(value: Any) -> List[str]:
        """转换字符串列表."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _extract_first_paragraph(text: str) -> str:
        """提取第一个自然段."""
        for paragraph in re.split(r"\n\s*\n", text):
            cleaned = paragraph.strip()
            if cleaned and not cleaned.startswith("#"):
                return cleaned.replace("\n", " ")
        return ""

    @staticmethod
    def _extract_summary(text: str, fallback: str) -> str:
        """提取 skill 摘要."""
        for paragraph in re.split(r"\n\s*\n", text):
            cleaned = paragraph.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            compact = re.sub(r"\s+", " ", cleaned)
            return compact[:240]
        return fallback

    def _collect_supporting_files(
        self,
        skill_dir: str,
        body: str,
    ) -> List[SkillSupportingFile]:
        """收集配套文件."""
        skill_root = Path(skill_dir)
        referenced_paths = []
        for match in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
            if "://" in match or match.startswith("#"):
                continue
            referenced_paths.append(match)

        referenced_set = set()
        supporting_files: List[SkillSupportingFile] = []

        for rel_path in referenced_paths:
            candidate = (skill_root / rel_path).resolve()
            try:
                candidate.relative_to(skill_root.resolve())
            except ValueError:
                continue
            if not candidate.exists() or not candidate.is_file():
                continue
            relative = candidate.relative_to(skill_root).as_posix()
            if relative in referenced_set:
                continue
            referenced_set.add(relative)
            content = self._read_supporting_file(candidate)
            supporting_files.append(
                SkillSupportingFile(path=relative, content=content)
            )

        for candidate in sorted(skill_root.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.name == "SKILL.md":
                continue
            relative = candidate.relative_to(skill_root).as_posix()
            if relative in referenced_set:
                continue
            supporting_files.append(SkillSupportingFile(path=relative, content=""))

        return supporting_files[:20]

    @staticmethod
    def _read_supporting_file(path: Path) -> str:
        """读取小型文本配套文件."""
        text_like_exts = {
            ".md", ".txt", ".json", ".yaml", ".yml",
            ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".ps1",
        }
        if path.suffix.lower() not in text_like_exts:
            return ""

        try:
            if path.stat().st_size > 12_000:
                return ""
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ""
        return content[:8_000].strip()

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
            skill_dir=str(Path(path).resolve().parent),
            source_format="legacy",
            argument_hint=data.get("argument_hint", ""),
            disable_model_invocation=bool(data.get("disable_model_invocation", False)),
            user_invocable=bool(data.get("user_invocable", True)),
            allowed_tools=self._coerce_string_list(data.get("allowed_tools", [])),
            model=str(data.get("model", "")).strip(),
            effort=str(data.get("effort", "")).strip(),
            context=str(data.get("context", "")).strip(),
            agent=str(data.get("agent", "")).strip(),
            hooks=data.get("hooks", {}) if isinstance(data.get("hooks", {}), dict) else {},
            paths=self._coerce_string_list(data.get("paths", [])),
            shell=str(data.get("shell", "")).strip(),
            supporting_files=[],
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
        for skill_dir in self.skill_dirs:
            if not os.path.exists(skill_dir):
                continue

            for path in self._iter_skill_files(skill_dir):
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
