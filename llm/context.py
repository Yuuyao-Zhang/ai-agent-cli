"""上下文组装器模块.

该模块实现了上下文组装器和动态 Token 预算管理，按优先级拼接多源信息，
避免超出 Token 限制。支持文件引用解析、终端输出捕获、文件树生成等功能。
"""

import platform
import re
from dataclasses import dataclass
from typing import Dict, List

from common.constant import (
    DYNAMIC_RATIO,
    FILE_TREE_MAX_DEPTH,
    FILE_TREE_MAX_LINES,
    HISTORY_RATIO,
    MAX_TOTAL_TOKENS_PER_AGENT,
    RECENT_FILE_OPS_LIMIT,
    SYSTEM_RATIO,
    TERMINAL_OUTPUT_LINES,
    FILE_TREE_RATIO,
    TERMINAL_RATIO
)
from common.file_index import get_file_tree
from knowledge import knowledge_manager
from mcp.registry import registry
from state.session import Session
from llm.terminal import get_recent_output


@dataclass
class ContextConfig:
    """上下文配置类，定义了上下文组装器的参数.

    Attributes:
        max_total_tokens: 最大总 Token 数
        system_ratio: System Prompt 占比
        history_ratio: 历史记录占比
        file_tree_ratio: 文件树占比
        terminal_ratio: 终端输出占比
        dynamic_ratio: 动态内容占比，留给 @file 引用等动态内容
    """

    max_total_tokens: int = MAX_TOTAL_TOKENS_PER_AGENT
    system_ratio: float = SYSTEM_RATIO
    history_ratio: float = HISTORY_RATIO
    file_tree_ratio: float = FILE_TREE_RATIO
    terminal_ratio: float = TERMINAL_RATIO
    dynamic_ratio: float = DYNAMIC_RATIO

    def __post_init__(self):
        """初始化后验证配置有效性."""
        total_ratio = (
            self.system_ratio
            + self.history_ratio
            + self.file_tree_ratio
            + self.terminal_ratio
            + self.dynamic_ratio
        )
        if total_ratio > 1.0 + 1e-9:
            # 仅打印警告，不强制报错，允许弹性调整
            print(f"Warning: Context ratios sum to {total_ratio} > 1.0")


def estimate_tokens(text: str) -> int:
    """粗略估算 Token 数 (按字符/4).

    Note: 对于中文环境，len(text)/4 可能会低估 token 数量
    （通常中文 1 char ~ 0.5-1 token）。
    但为了保持零依赖（不引入 tiktoken），这里暂时维持此简易算法。
    建议在 budget 设置时留出 buffer。

    TODO: Replace with tokenizer-aware estimation (e.g., tiktoken)
        if dependency allowed.

    Args:
        text: 要估算 Token 数的文本

    Returns:
        估算的 Token 数
    """

    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    non_chinese_tokens = len(text) - chinese_chars

    return int(chinese_chars / 1.5 + non_chinese_tokens / 4)


def get_recent_file_ops(session: Session, limit: int = RECENT_FILE_OPS_LIMIT) -> str:
    """提取最近成功的文件操作记录.

    通过扫描历史消息中的工具反馈来获取。

    Args:
        session: 当前会话对象
        limit: 返回的最大记录数，默认为 RECENT_FILE_OPS_LIMIT

    Returns:
        格式化的文件操作记录字符串，如果没有记录则返回空字符串
    """
    ops = []
    count = 0
    for msg in reversed(session.history):
        if msg["role"] == "user" and "Tool Results" in msg["content"]:
            content = msg["content"]
            writes = re.findall(r"Successfully wrote to (.+)", content)
            edits = re.findall(r"Successfully edited (.+)", content)

            for path in writes:
                if count < limit:
                    ops.append(f"- Created/Overwrote: {path.strip()}")
                    count += 1

            for path in edits:
                if count < limit:
                    ops.append(f"- Edited: {path.strip()}")
                    count += 1

            if count >= limit:
                break

    if not ops:
        return ""

    return "\n[Recent File Operations]:\n" + "\n".join(ops) + "\n"


def get_available_mcp_tools_text(limit: int = 20) -> str:
    tool_specs = registry.list_tool_specs()
    if not tool_specs:
        return ""

    lines = ["\n[MCP Tools]:"]
    for tool in tool_specs[:limit]:
        name = tool.get("name", "")
        description = str(tool.get("description", "")).strip().replace("\n", " ")
        props = tool.get("inputSchema", {}).get("properties", {})
        required = set(tool.get("inputSchema", {}).get("required", []))
        arg_parts = []
        for arg_name, arg_meta in list(props.items())[:6]:
            marker = "*" if arg_name in required else ""
            arg_desc = str(arg_meta.get("description", "")).strip().replace("\n", " ")
            if len(arg_desc) > 40:
                arg_desc = arg_desc[:40] + "..."
            arg_parts.append(f"{arg_name}{marker}: {arg_desc}")
        arg_text = "; ".join(arg_parts) if arg_parts else "无参数"
        lines.append(f"- {name}: {description[:80]} | 参数: {arg_text}")

    lines.append("调用远程 MCP 工具时，直接输出 JSON 指令，如 [{\"tool\":\"tool_name\",\"args\":{\"key\":\"value\"}}]。")
    lines.append("优先根据工具描述和参数 schema 选择最匹配的 MCP 工具；若任务需要多步推理，可串联多个工具完成。")
    return "\n".join(lines) + "\n"


def get_cached_knowledge_context(task: str, session: Session) -> str:
    cache = session.get("_knowledge_context_cache")
    if isinstance(cache, dict) and cache.get("task") == task:
        return str(cache.get("context", ""))

    results = knowledge_manager.search_hierarchical(task, top_k=3, min_score=0.35)
    context = knowledge_manager.get_context_for_prompt(task, top_k=3, min_score=0.35)
    references = knowledge_manager.format_source_references(results, limit=3)
    session.set("_knowledge_context_cache", {
        "task": task,
        "context": context,
        "results": results,
        "references": references,
    })
    return context


def get_system_prompt(task: str, session: Session) -> str:
    """动态生成系统提示词.

    Args:
        task: 任务描述
        session: 当前会话对象

    Returns:
        完整的系统提示词字符串
    """
    if session.get('system_prompt'):
        return session.get('system_prompt')

    os_info = platform.system()
    shell_hint = "PowerShell/CMD" if os_info == "Windows" else "Bash"

    context_info = (
        f"\n当前上下文:\n"
        f"- 工作目录: {session.get('cwd', '.')}\n"
        f"- 调用栈: {session.get_trace()}"
    )
    mcp_tools_text = get_available_mcp_tools_text()

    todo_example = '[{{ "id": "1", "status": "completed" }},\n'
    todo_example += '        {{ "id": "new", "content": "新任务" }}]'

    return f"""你是一个智能代理，运行在 {os_info} 环境下。
    任务：{task}{context_info}{mcp_tools_text}

    请使用适用于 {os_info} 的 {shell_hint} 命令解决问题。
    可用指令：
    1. 执行命令: ```bash\n命令\n``` (注意：Windows下默认使用CMD)
    2. 读取文件: ```read\n路径\n```
    3. 写入文件: ```write 路径\n内容\n```
    4. 编辑文件: ```edit 路径\n<<OLD\n旧内容\nOLD\n<<NEW\n新内容\nNEW\n```
    5. 管理任务: ```todo\n{todo_example}\n```
    6. 分解任务: SUBTASK: <子任务描述> (将创建子Agent进行递归求解)
    7. 调用远程 MCP 工具: 直接输出 JSON 列表，如 [{{"tool": "tool_name", "args": {{"key": "value"}}}}]

    规则：
    - 优先使用专用工具(read/write/edit)进行文件操作。
    - 必须主动维护 Todo List。
    - 若已提供 MCP 工具，优先根据工具描述和参数 schema 选择最合适的 MCP 工具获取实时信息，不要臆测结果。
    - 当用户表达“我这里”“当前位置”“附近”等相对位置语义时，先寻找定位类工具，再调用后续领域工具。
    - 如果任务可通过 Shell 命令直接完成，请直接输出 ```bash ... ```。
    - 只有遇到极复杂任务时，才使用 SUBTASK: ... 分解。
    - 优先尝试直接解决问题，不要过度规划。
    - 递归深度限制：当前为第 {session.depth} 层。
    - 任务完成后，请明确回复"任务完成"或"DONE"。
    - 请用中文回复。
    """


def build_dynamic_context(
    task: str, session: Session, remaining_budget: int
) -> str:
    """构建动态上下文文本（文件引用、终端、文件树）.

    优先级: Dynamic(@file) > Terminal > FileTree

    Args:
        task: 任务描述
        session: 当前会话对象
        remaining_budget: 剩余可用 Token 预算

    Returns:
        组装后的上下文文本
    """
    if remaining_budget <= 0:
        return ""

    context_parts = ["\n[Additional Context]:"]
    used_tokens = estimate_tokens(context_parts[0])

    # 知识库上下文
    if used_tokens < remaining_budget:
        knowledge_text = get_cached_knowledge_context(task, session)
        if knowledge_text:
            knowledge_block = f"\n{knowledge_text}\n"
            knowledge_tokens = estimate_tokens(knowledge_block)
            if used_tokens + knowledge_tokens < remaining_budget:
                context_parts.append(knowledge_block)
                used_tokens += knowledge_tokens

    # 最近文件操作
    if used_tokens < remaining_budget:
        file_ops_text = get_recent_file_ops(session)
        if file_ops_text:
            ops_tokens = estimate_tokens(file_ops_text)
            if used_tokens + ops_tokens < remaining_budget:
                context_parts.append(file_ops_text)
                used_tokens += ops_tokens

    # 终端输出
    if used_tokens < remaining_budget:
        raw_output = get_recent_output()
        term_lines = raw_output.splitlines()[-TERMINAL_OUTPUT_LINES:]
        if term_lines:
            term_text = (
                "\n[Terminal Output (Last "
                f"{TERMINAL_OUTPUT_LINES} lines)]:\n"
                + "\n".join(term_lines)
                + "\n"
            )
            term_tokens = estimate_tokens(term_text)

            if used_tokens + term_tokens < remaining_budget:
                context_parts.append(term_text)
                used_tokens += term_tokens

    # 文件树
    if used_tokens < remaining_budget:
        file_tree = get_file_tree(
            root_dir=session.get("cwd", "."),
            max_depth=FILE_TREE_MAX_DEPTH,
            max_lines=FILE_TREE_MAX_LINES
        )
        tree_text = f"\n[Project File Tree]:\n{file_tree}\n"
        tree_tokens = estimate_tokens(tree_text)

        if used_tokens + tree_tokens <= remaining_budget:
            context_parts.append(tree_text)
            used_tokens += tree_tokens

    if len(context_parts) == 1:
        return ""

    return "\n".join(context_parts)


class ContextAssembler:
    """上下文组装器类.

    负责按优先级组装各种上下文信息，管理 Token 预算分配。
    """

    def __init__(self, config: ContextConfig = None):
        """初始化上下文组装器.

        Args:
            config: 上下文配置对象，默认使用 ContextConfig()
        """
        self.config = config or ContextConfig()

    def assemble_messages(
        self, task: str, session: Session, memory_manager=None
    ) -> List[Dict[str, str]]:
        """组装最终发送给 LLM 的消息列表.

        包含: System Prompt + Additional Context + Task(User) + Pruned History

        Args:
            task: 任务描述
            session: 当前会话对象
            memory_manager: (可选) 分层记忆管理器

        Returns:
            组装后的消息列表，每条消息为包含 role 和 content 的字典
        """
        total_budget = self.config.max_total_tokens

        # 构建 System Message
        system_prompt = get_system_prompt(task, session)
        system_tokens = estimate_tokens(system_prompt)

        # 计算剩余预算
        net_budget = total_budget - system_tokens

        if net_budget <= 0:
            return [{"role": "system", "content": system_prompt}]

        # 分配预算
        history_budget_target = int(net_budget * self.config.history_ratio)
        context_budget = net_budget - history_budget_target

        # 构建 Dynamic Context
        dynamic_context = build_dynamic_context(task, session, context_budget)
        context_tokens = estimate_tokens(dynamic_context)

        # 重新计算给 History 的最终剩余预算
        remaining_for_history = net_budget - context_tokens
        if remaining_for_history < 0:
            remaining_for_history = 0

        # 裁剪历史记录
        pruned_history = []
        current_tokens = 0

        if memory_manager:
            # 使用记忆管理器获取上下文 (包含摘要 + 活跃窗口)
            mem_msgs = memory_manager.get_context()
            # 倒序遍历以优先保留最近消息
            for msg in reversed(mem_msgs):
                msg_tokens = estimate_tokens(msg["content"])
                if current_tokens + msg_tokens > remaining_for_history:
                    break
                pruned_history.insert(0, msg)
                current_tokens += msg_tokens
        else:
            # 原始逻辑：直接从 Session 读取
            for msg in reversed(session.history):
                msg_tokens = estimate_tokens(msg["content"])
                if current_tokens + msg_tokens > remaining_for_history:
                    break
                pruned_history.insert(0, msg)
                current_tokens += msg_tokens

        # 组装最终消息列表 (顺序：[System] -> [History] -> [User(Task)])
        # 这样 Agent 最后看到的是任务指令，能有效利用近因效应
        user_content_parts = []
        if dynamic_context:
            user_content_parts.append(dynamic_context)

        user_content_parts.append(f"User Task: {task}")

        final_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 插入历史记录
        final_messages.extend(pruned_history)
        
        # 插入当前任务
        final_messages.append({"role": "user", "content": "\n\n".join(user_content_parts)})

        return final_messages


# 全局实例
assembler = ContextAssembler()
