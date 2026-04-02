"""意图识别模块.

用于在上下文组装前，判断用户任务是否需要触发 RAG (Knowledge) 或 Skill 检索，
以节省 Token 预算和检索时间。
"""

import json
import re
from typing import Optional

from common.config import config
from llm.llm import call_qwen


def recognize_intent(task: str) -> tuple[bool, bool]:
    """识别任务意图，决定是否需要检索 RAG (Knowledge) 和 Skill。

    Args:
        task: 用户任务描述

    Returns:
        (need_rag, need_skill): 两个布尔值，分别表示是否需要 RAG 和 Skill
    """
    if not config.intent.enabled:
        return True, True

    default_prompt = (
        f"请分析以下用户任务，判断是否需要查询本地项目知识库(RAG)"
        f"或特定的开发技能(Skill)。\n"
        f"- RAG (本地项目知识库): 当用户询问项目架构、代码实现、"
        f"业务逻辑、API文档等特定于当前项目的问题时需要。\n"
        f"- Skill (开发技能): 当用户需要特定的工具使用方法、部署步骤、"
        f"框架最佳实践等指导时需要。\n"
        f"- 只有极简单的命令或纯闲聊，或者意图非常明确不需要任何额外上下文的"
        f'（比如"删除某个文件"），才不需要检索。\n\n'
        f'任务描述: "{task}"\n\n'
        f"请严格且仅输出 JSON 格式，不要包含任何其他内容：\n"
        f'{{"need_rag": true/false, "need_skill": true/false}}'
    )
    prompt = config.intent.prompt
    if prompt:
        prompt = prompt.replace("{task}", task)
    else:
        prompt = default_prompt

    model = config.intent.model

    try:
        res = call_qwen(
            [{"role": "user", "content": prompt}],
            model=model,
            use_cache=True,
            stream=False
        )
        match = re.search(r"\{.*\}", res, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            need_rag = bool(data.get("need_rag", True))
            need_skill = bool(data.get("need_skill", True))
            return need_rag, need_skill
    except Exception as e:
        print(f"[Intent] 意图识别解析失败，降级为全量检索: {e}")

    return True, True
