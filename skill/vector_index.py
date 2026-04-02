"""向量索引模块.

基于 Qwen Embedding 的向量索引实现，支持多级别披露的向量检索。
用于 Skill 的语义搜索和匹配。
"""

import math
from typing import Dict, List, Tuple

from common.vector.tokenizer import tokenize
from llm.llm import call_qwen_embedding
from skill.types import DisclosureLevel, Skill


class VectorIndex:
    """基于 Qwen Embedding 的向量索引.

    支持多级别披露的向量索引，用于 Skill 的语义检索。
    """

    def __init__(self):
        """初始化向量索引."""
        self.skills: List[Skill] = []
        self.vectors: List[List[float]] = []
        self.brief_index: Dict[str, List[float]] = {}
        self.summary_index: Dict[str, List[float]] = {}
        self.detailed_index: Dict[str, List[float]] = {}
        self.lexical_index: Dict[str, List[str]] = {}

    def rebuild(self, skills: List[Skill]) -> None:
        """重建向量索引.

        Args:
            skills: Skill 列表
        """
        self.skills = skills
        self.vectors = []
        self.brief_index = {}
        self.summary_index = {}
        self.detailed_index = {}
        self.lexical_index = {}

        if not skills:
            return

        for skill in skills:
            detailed_text = self._build_index_text(skill, DisclosureLevel.DETAILED)
            brief_text = self._build_index_text(skill, DisclosureLevel.BRIEF)
            summary_text = self._build_index_text(skill, DisclosureLevel.SUMMARY)
            self.vectors.append(
                call_qwen_embedding(detailed_text)
            )
            self.brief_index[skill.name] = call_qwen_embedding(brief_text)
            self.summary_index[skill.name] = call_qwen_embedding(summary_text)
            self.detailed_index[skill.name] = call_qwen_embedding(detailed_text)
            self.lexical_index[skill.name] = tokenize(detailed_text)

    def _build_index_text(self, skill: Skill, level: DisclosureLevel) -> str:
        """构建用于索引的文本.

        根据不同的披露级别构建索引文本。

        Args:
            skill: Skill 对象
            level: 披露级别

        Returns:
            索引文本
        """
        if level == DisclosureLevel.BRIEF:
            return (
                f"{skill.name} {skill.description} {skill.category} "
                f"{skill.argument_hint}"
            )
        if level == DisclosureLevel.SUMMARY:
            tags_str = " ".join(skill.tags)
            tools_str = " ".join(skill.allowed_tools)
            return (
                f"{skill.name} {skill.description} {skill.summary} "
                f"{skill.category} {tags_str} {tools_str}"
            )
        tags_str = " ".join(skill.tags)
        tools_str = " ".join(skill.allowed_tools)
        params_str = " ".join(
            f"{p.name} {p.description}" for p in skill.parameters
        )
        examples_str = " ".join(
            f"{e.description} {e.input} {e.output}"
            for e in skill.examples
        )
        hints_str = " ".join(h.suggestion for h in skill.hints)
        paths_str = " ".join(skill.paths)
        supporting_str = " ".join(
            item.path for item in skill.supporting_files
        )
        return (
            (f"{skill.name} " * 3) +
            (f"{skill.description} " * 2) +
            f"{skill.summary} " +
            f"{skill.content} " +
            f"{skill.category} " +
            f"{tags_str} " +
            f"{tools_str} " +
            f"{params_str} " +
            f"{examples_str} " +
            f"{hints_str} " +
            f"{paths_str} " +
            f"{supporting_str}"
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
        level: DisclosureLevel = DisclosureLevel.DETAILED
    ) -> List[Tuple[Skill, float]]:
        """搜索 Skills.

        Args:
            query: 查询文本
            top_k: 返回结果数量
            level: 披露级别

        Returns:
            (Skill, 相似度) 元组列表
        """
        if not self.skills:
            return []

        query_vec = call_qwen_embedding(query)
        query_tokens = tokenize(query)

        results = []
        for i, skill in enumerate(self.skills):
            base_vec = self.vectors[i] if i < len(self.vectors) else []
            level_vec = self._get_level_vector(skill.name, level)

            embedding_score = 0.0
            if query_vec:
                base_score = self._cosine_similarity(query_vec, base_vec)
                level_score = self._cosine_similarity(query_vec, level_vec)
                embedding_score = base_score * 0.6 + level_score * 0.4

            lexical_score = self._lexical_similarity(
                query_tokens,
                self.lexical_index.get(skill.name, []),
            )

            combined_score = embedding_score
            if lexical_score > 0:
                combined_score = max(combined_score, lexical_score * 0.85)

            if combined_score > 0:
                results.append((skill, combined_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _get_level_vector(
        self,
        skill_name: str,
        level: DisclosureLevel
    ) -> List[float]:
        """获取指定级别的向量.

        Args:
            skill_name: Skill 名称
            level: 披露级别

        Returns:
            向量列表
        """
        if level == DisclosureLevel.BRIEF:
            return self.brief_index.get(skill_name, [])
        if level == DisclosureLevel.SUMMARY:
            return self.summary_index.get(skill_name, [])
        return self.detailed_index.get(skill_name, [])

    def search_by_level(
        self,
        query: str,
        level: DisclosureLevel,
        top_k: int = 3
    ) -> List[Tuple[Skill, float]]:
        """按指定披露级别搜索 Skills.

        Args:
            query: 查询文本
            level: 披露级别
            top_k: 返回结果数量

        Returns:
            (Skill, 相似度) 元组列表
        """
        return self.search(query, top_k, level)

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算两个向量的余弦相似度.

        Args:
            v1: 第一个向量
            v2: 第二个向量

        Returns:
            余弦相似度值，范围 [0, 1]
        """
        if not v1 or not v2:
            return 0.0

        if len(v1) != len(v2):
            min_len = min(len(v1), len(v2))
            if min_len == 0:
                return 0.0
            v1 = v1[:min_len]
            v2 = v2[:min_len]

        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_v1 = math.sqrt(sum(a * a for a in v1))
        norm_v2 = math.sqrt(sum(a * a for a in v2))

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return dot_product / (norm_v1 * norm_v2)

    @staticmethod
    def _lexical_similarity(
        query_tokens: List[str],
        doc_tokens: List[str]
    ) -> float:
        """基于词项重合的兜底相似度.

        Args:
            query_tokens: 查询词列表
            doc_tokens: 文档词列表

        Returns:
            相似度分数
        """
        if not query_tokens or not doc_tokens:
            return 0.0

        query_set = set(query_tokens)
        doc_set = set(doc_tokens)
        overlap = query_set & doc_set
        if not overlap:
            return 0.0

        coverage = len(overlap) / len(query_set)
        precision = len(overlap) / len(doc_set)
        return coverage * 0.8 + precision * 0.2

    def get_skill_keywords(
        self,
        skill_name: str,
        top_n: int = 10
    ) -> List[Tuple[str, float]]:
        """获取 Skill 的关键词（预留功能）.

        Args:
            skill_name: Skill 名称
            top_n: 返回关键词数量

        Returns:
            (关键词, 权重) 元组列表
        """
        return []
