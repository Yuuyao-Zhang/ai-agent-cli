"""提示词模板管理模块.

统一管理各种提示词模板，提供模板的注册、渲染和管理功能。
"""

from typing import Dict, List, Optional
from .types import PromptTemplate


class PromptManager:
    """提示词管理器."""

    def __init__(self):
        """初始化提示词管理器."""
        self.templates: Dict[str, PromptTemplate] = {}
        self._init_default_templates()

    def _init_default_templates(self):
        """初始化默认提示词模板."""
        # 摘要生成模板
        self.register_template(PromptTemplate(
            name="conversation_summary",
            template=(
                "你是一个摘要助手。请用中文简洁地总结以下对话。"
                "保留关键事实、决策和代码变更。\n\n"
                "已有摘要: {existing_summary}\n\n"
                "新对话:\n{conversation}"
            ),
            description="对话摘要生成",
            variables=["existing_summary", "conversation"],
            category="memory"
        ))

        # 查询重写模板
        self.register_template(PromptTemplate(
            name="query_rewrite",
            template=(
                "将以下查询重写为3个不同的变体，"
                "用于更好地捕获潜在意图：\n\n"
                "原始查询: {query}\n\n"
                "请以JSON数组格式返回3个重写的查询。"
            ),
            description="查询重写",
            variables=["query"],
            category="retrieval"
        ))

        # 代码解释模板
        self.register_template(PromptTemplate(
            name="code_explanation",
            template=(
                "请用简单易懂的方式解释以下代码：\n\n"
                "代码:\n{code}\n\n"
                "请包括：\n"
                "1. 代码的主要功能\n"
                "2. 关键实现细节\n"
                "3. 使用示例"
            ),
            description="代码解释",
            variables=["code"],
            category="general"
        ))

    def register_template(self, template: PromptTemplate) -> bool:
        """注册提示词模板.

        Args:
            template: 提示词模板对象

        Returns:
            是否注册成功
        """
        if template.name in self.templates:
            return False
        self.templates[template.name] = template
        return True

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取提示词模板.

        Args:
            name: 模板名称

        Returns:
            提示词模板对象，未找到返回None
        """
        return self.templates.get(name)

    def render(self, name: str, **kwargs) -> Optional[str]:
        """渲染提示词模板.

        Args:
            name: 模板名称
            **kwargs: 模板变量值

        Returns:
            渲染后的提示词，未找到模板返回None
        """
        template = self.get_template(name)
        if not template:
            return None
        return self._render_string(template.template, **kwargs)

    def _render_string(self, template_str: str, **kwargs) -> str:
        """渲染模板字符串.

        Args:
            template_str: 模板字符串
            **kwargs: 变量值

        Returns:
            渲染后的字符串
        """
        # 简单的变量替换
        result = template_str
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def list_templates(self, category: Optional[str] = None) -> List[PromptTemplate]:
        """列出所有模板.

        Args:
            category: 按类别筛选

        Returns:
            模板列表
        """
        templates = list(self.templates.values())
        if category:
            return [t for t in templates if t.category == category]
        return templates

    def delete_template(self, name: str) -> bool:
        """删除模板.

        Args:
            name: 模板名称

        Returns:
            是否删除成功
        """
        if name not in self.templates:
            return False
        self.templates.pop(name)
        return True


# 全局单例
prompt_manager = PromptManager()
