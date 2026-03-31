"""Skill 管理器模块.

提供 Skill 的加载、检索、依赖解析等功能。
支持渐进式披露的智能检索。
"""

import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from skill.loader import SkillLoader, SkillWriter
from skill.types import DisclosureLevel, Skill, SkillHint
from skill.vector_index import VectorIndex


class SkillManager:
    """Skill 管理器.

    提供 Skill 的完整生命周期管理，包括加载、检索、依赖解析等。
    支持渐进式披露的智能检索。

    Attributes:
        loader: Skill 加载器
        writer: Skill 写入器
        index: 向量索引
        skills: Skill 字典
        skill_dir: Skill 目录
    """

    def __init__(self, skill_dir: str):
        """初始化管理器.

        Args:
            skill_dir: Skill 文件所在目录
        """
        self.loader = SkillLoader(skill_dir)
        self.writer = SkillWriter(skill_dir)
        self.index = VectorIndex()
        self.skills: Dict[str, Skill] = {}
        self.skill_dir = skill_dir
        self._watching = False
        self._lock = threading.RLock()

    def initialize(self) -> None:
        """初始化加载."""
        self.reload()

    def reload(self) -> None:
        """重新加载所有 Skills."""
        with self._lock:
            new_skills = self.loader.load_all()
            self.skills = new_skills
            self.index.rebuild(list(self.skills.values()))
            print(f"已加载 {len(self.skills)} 个技能。")

    def reload_skill(self, name: str) -> bool:
        """重新加载指定的 Skill.

        Args:
            name: Skill 名称

        Returns:
            加载成功返回 True，否则返回 False
        """
        with self._lock:
            skill = self.loader.load_skill_by_name(name)
            if skill:
                self.skills[name] = skill
                # 这里只重建索引可能会比较慢，但为了保持一致性
                self.index.rebuild(list(self.skills.values()))
                print(f"已重新加载技能: {name}")
                return True
            else:
                print(f"未能找到或重新加载技能: {name}")
                return False

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill.

        Args:
            name: Skill 名称

        Returns:
            Skill 对象，未找到返回 None
        """
        return self.skills.get(name)

    def get_skill_disclosed(
        self, name: str, level: DisclosureLevel
    ) -> Optional[Dict[str, Any]]:
        """按指定披露级别获取 Skill 信息.

        Args:
            name: Skill 名称
            level: 披露级别

        Returns:
            披露信息字典，未找到返回 None
        """
        skill = self.skills.get(name)
        if skill:
            return skill.disclose(level)
        return None

    def resolve_dependencies(self, skill_name: str) -> List[Skill]:
        """解析依赖链 (拓扑排序).

        Args:
            skill_name: Skill 名称

        Returns:
            按依赖顺序排列的 Skill 列表
        """
        result: List[Skill] = []
        visited: set = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name not in self.skills:
                print(f"警告: 缺失依赖 {name}")
                return

            visited.add(name)
            skill = self.skills[name]
            for dep in skill.dependencies:
                visit(dep)
            result.append(skill)

        visit(skill_name)
        return result

    def resolve_dependencies_disclosed(
        self, skill_name: str, level: DisclosureLevel
    ) -> List[Dict[str, Any]]:
        """解析依赖链并按披露级别返回.

        Args:
            skill_name: Skill 名称
            level: 披露级别

        Returns:
            按依赖顺序排列的披露信息字典列表
        """
        skills = self.resolve_dependencies(skill_name)
        return [s.disclose(level) for s in skills]

    def search_skills(self, query: str, top_k: int = 3) -> List[Skill]:
        """语义检索 Skills.

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            匹配的 Skill 列表
        """
        results = self.index.search(query, top_k)
        return [r[0] for r in results]

    def search_skills_disclosed(
        self, query: str, level: DisclosureLevel, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """语义检索并按披露级别返回.

        Args:
            query: 查询文本
            level: 披露级别
            top_k: 返回结果数量

        Returns:
            匹配的披露信息字典列表
        """
        skills = self.search_skills(query, top_k)
        return [s.disclose(level) for s in skills]

    def search_with_hints(
        self, query: str, context: str, top_k: int = 3
    ) -> List[Tuple[Skill, List[SkillHint]]]:
        """语义检索并返回相关提示.

        根据查询和上下文检索 Skills，同时返回与上下文相关的提示。

        Args:
            query: 查询文本
            context: 当前上下文
            top_k: 返回结果数量

        Returns:
            (Skill, hints) 元组列表
        """
        skills = self.search_skills(query, top_k)
        results = []
        for skill in skills:
            hints = skill.get_relevant_hints(context)
            results.append((skill, hints))
        return results

    def get_all_brief(self) -> List[Dict[str, str]]:
        """获取所有 Skill 的简要信息.

        Returns:
            简要信息字典列表
        """
        return [s.get_brief_info() for s in self.skills.values()]

    def get_all_summary(self) -> List[Dict[str, Any]]:
        """获取所有 Skill 的摘要信息.

        Returns:
            摘要信息字典列表
        """
        return [s.get_summary_info() for s in self.skills.values()]

    def get_skills_by_category(self, category: str) -> List[Skill]:
        """按分类获取 Skills.

        Args:
            category: 分类名称

        Returns:
            该分类下的 Skill 列表
        """
        return [s for s in self.skills.values() if s.category == category]

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        """按标签获取 Skills.

        Args:
            tag: 标签名称

        Returns:
            包含该标签的 Skill 列表
        """
        return [s for s in self.skills.values() if tag in s.tags]

    def build_context_prompt(
        self,
        skill_names: List[str],
        level: DisclosureLevel = DisclosureLevel.DETAILED,
        include_dependencies: bool = True,
    ) -> str:
        """构建上下文 Prompt.

        将多个 Skills 组合成一个完整的上下文 Prompt。

        Args:
            skill_names: Skill 名称列表
            level: 披露级别
            include_dependencies: 是否包含依赖

        Returns:
            格式化的 Prompt 字符串
        """
        lines = ["# Skills Context\n"]

        processed = set()

        for name in skill_names:
            if name in processed:
                continue

            if include_dependencies:
                skills = self.resolve_dependencies(name)
            else:
                skill = self.get_skill(name)
                skills = [skill] if skill else []

            for skill in skills:
                if skill.name in processed:
                    continue
                processed.add(skill.name)
                lines.append(skill.to_prompt(level))
                lines.append("---\n")

        return "\n".join(lines)

    def create_skill(self, skill: Skill) -> str:
        """创建新 Skill.

        Args:
            skill: Skill 对象

        Returns:
            保存的文件路径
        """
        path = self.writer.save_skill(skill)
        with self._lock:
            self.skills[skill.name] = skill
            self.index.rebuild(list(self.skills.values()))
        return path

    def create_skill_template(self, name: str, fmt: str = "json") -> str:
        """创建 Skill 模板文件.

        Args:
            name: Skill 名称
            fmt: 文件格式

        Returns:
            创建的文件路径
        """
        return self.writer.create_skill_template(name, fmt)

    def start_hot_reload(self, interval: int = 5) -> None:
        """开启热重载监控.

        Args:
            interval: 检查间隔 (秒)
        """
        if self._watching:
            return
        self._watching = True

        def watcher() -> None:
            last_mtime = 0.0
            while self._watching:
                current_mtime = self._get_max_mtime()
                if current_mtime > last_mtime:
                    if last_mtime > 0:
                        print("检测到技能变更，正在重新加载...")
                        self.reload()
                    last_mtime = current_mtime
                time.sleep(interval)

        t = threading.Thread(target=watcher, daemon=True)
        t.start()

    def stop_hot_reload(self) -> None:
        """停止热重载监控."""
        self._watching = False

    def _get_max_mtime(self) -> float:
        """获取目录下最新文件修改时间.

        Returns:
            最新修改时间戳
        """
        max_mtime = 0.0
        if not os.path.exists(self.skill_dir):
            return 0.0

        for root, _, files in os.walk(self.skill_dir):
            for file in files:
                if file.endswith((".json", ".yaml", ".yml")):
                    path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(path)
                        max_mtime = max(max_mtime, mtime)
                    except OSError:
                        pass
        return max_mtime


class ProgressiveDisclosureEngine:
    """渐进式披露引擎.

    根据用户交互上下文智能调整 Skill 信息披露级别。

    Attributes:
        manager: Skill 管理器
        context_history: 上下文历史
        disclosure_thresholds: 披露级别阈值配置
    """

    def __init__(self, manager: SkillManager):
        """初始化引擎.

        Args:
            manager: Skill 管理器
        """
        self.manager = manager
        self.context_history: List[str] = []
        self.disclosure_thresholds = {
            "mention_count": {1: DisclosureLevel.BRIEF, 3: DisclosureLevel.SUMMARY},
            "query_depth": {"simple": DisclosureLevel.BRIEF, "detailed": DisclosureLevel.DETAILED},
        }
        self._mention_counts: Dict[str, int] = {}

    def process_query(
        self, query: str, context: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """处理查询并返回适当披露级别的结果.

        Args:
            query: 用户查询
            context: 当前上下文

        Returns:
            (披露结果列表, 构建的 Prompt)
        """
        if context:
            self.context_history.append(context)

        skills = self.manager.search_skills(query)

        for skill in skills:
            self._mention_counts[skill.name] = self._mention_counts.get(skill.name, 0) + 1

        level = self._determine_disclosure_level(query, skills)
        results = [s.disclose(level) for s in skills]

        prompt = self.manager.build_context_prompt(
            [s.name for s in skills], level=level
        )

        return results, prompt

    def _determine_disclosure_level(
        self, query: str, skills: List[Skill]
    ) -> DisclosureLevel:
        """确定披露级别.

        Args:
            query: 用户查询
            skills: 匹配的 Skills

        Returns:
            确定的披露级别
        """
        query_lower = query.lower()

        if any(
            kw in query_lower
            for kw in ["详细", "完整", "所有", "full", "complete", "detailed"]
        ):
            return DisclosureLevel.DETAILED

        if any(kw in query_lower for kw in ["摘要", "概要", "summary", "overview"]):
            return DisclosureLevel.SUMMARY

        if any(kw in query_lower for kw in ["简要", "简单", "brief", "simple"]):
            return DisclosureLevel.BRIEF

        if skills:
            max_mentions = max(
                self._mention_counts.get(s.name, 0) for s in skills
            )
            if max_mentions >= 3:
                return DisclosureLevel.SUMMARY
            elif max_mentions >= 5:
                return DisclosureLevel.DETAILED

        if len(self.context_history) > 5:
            return DisclosureLevel.SUMMARY

        return DisclosureLevel.BRIEF

    def get_relevant_hints(self, context: str) -> Dict[str, List[SkillHint]]:
        """获取与上下文相关的所有提示.

        Args:
            context: 当前上下文

        Returns:
            {skill_name: hints} 字典
        """
        result = {}
        for skill in self.manager.skills.values():
            hints = skill.get_relevant_hints(context)
            if hints:
                result[skill.name] = hints
        return result

    def reset_context(self) -> None:
        """重置上下文历史."""
        self.context_history.clear()
        self._mention_counts.clear()


manager = SkillManager(os.path.join(os.getcwd(), "skills"))
