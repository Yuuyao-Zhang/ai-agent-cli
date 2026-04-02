"""Agent 执行中的面向切面编程 (AOP) 钩子系统.

支持前置/后置钩子、优先级链和异常处理。
"""

import ast
import json
import os
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from common.io_utils import debug, error
from engine.tools import validate_path


class HookType(Enum):
    """钩子点枚举.

    Attributes:
        PRE_RUN: Agent 运行开始前
        POST_RUN: Agent 运行结束后
        PRE_LLM: LLM API 调用前
        POST_LLM: LLM API 调用返回后
        PRE_TOOL: 工具执行前
        POST_TOOL: 工具执行后
        ON_ERROR: 发生错误时
    """

    PRE_RUN = auto()
    POST_RUN = auto()
    PRE_LLM = auto()
    POST_LLM = auto()
    PRE_TOOL = auto()
    POST_TOOL = auto()
    ON_ERROR = auto()

@dataclass
class HookContext:
    """传递给钩子的上下文对象.

    Attributes:
        hook_type: 钩子类型
        agent_id: Agent ID
        task_desc: 任务描述
        session: 会话对象
        llm_input: LLM 输入
        llm_output: LLM 输出
        tool_name: 工具名称
        tool_args: 工具参数
        tool_result: 工具执行结果
        error: 异常对象
        metadata: 元数据字典
    """

    hook_type: HookType
    agent_id: str = "main"
    task_desc: str = ""
    session: Any = None
    llm_input: Optional[List[Dict]] = None
    llm_output: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def stop_propagation(
        self,
        reason: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> None:
        """停止钩子链传播.

        Args:
            reason: 拒绝原因
            feedback: 反馈信息
        """
        self.metadata["_stop_propagation"] = True
        if reason is not None:
            self.metadata["reject_reason"] = reason
        if feedback is not None:
            self.metadata["feedback"] = feedback

    def reject(
        self,
        reason: str,
        feedback: Optional[str] = None
    ) -> None:
        """拒绝操作.

        Args:
            reason: 拒绝原因
            feedback: 反馈信息
        """
        self.metadata["_decision"] = "reject"
        self.stop_propagation(reason=reason, feedback=feedback)

    def set_feedback(self, feedback: str) -> None:
        """设置反馈信息.

        Args:
            feedback: 反馈内容
        """
        self.metadata["feedback"] = feedback

    @property
    def is_propagation_stopped(self) -> bool:
        """检查是否已停止传播."""
        return self.metadata.get("_stop_propagation", False)

    @property
    def decision(self) -> Optional[str]:
        """获取决策结果."""
        return self.metadata.get("_decision")

    @property
    def reject_reason(self) -> Optional[str]:
        """获取拒绝原因."""
        return self.metadata.get("reject_reason")

    @property
    def feedback(self) -> Optional[str]:
        """获取反馈信息."""
        return self.metadata.get("feedback")


@dataclass
class HookEntry:
    """钩子注册项.

    Attributes:
        callback: 回调函数
        priority: 优先级
        condition: 触发条件
    """

    callback: Callable[[HookContext], None]
    priority: int = 0
    condition: Optional[Callable[[HookContext], bool]] = None


class HookRegistry:
    """管理全局和局部钩子的注册中心."""

    _instance = None

    def __new__(cls):
        """单例模式实现."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.hooks: Dict[HookType, List[HookEntry]] = {
                t: [] for t in HookType
            }
        return cls._instance

    @classmethod
    def get_instance(cls):
        """获取单例实例."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        hook_type: HookType,
        callback: Callable[[HookContext], None],
        priority: int = 0,
        condition: Optional[Callable[[HookContext], bool]] = None
    ) -> None:
        """注册一个钩子.

        Args:
            hook_type: 钩子类型
            callback: 回调函数
            priority: 优先级
            condition: 触发条件
        """
        entry = HookEntry(callback, priority, condition)
        self.hooks[hook_type].append(entry)
        self.hooks[hook_type].sort(key=lambda x: x.priority, reverse=True)
        debug(
            f"Registered hook {callback.__name__} for "
            f"{hook_type.name} with priority {priority}"
        )

    def clear(self) -> None:
        """清空所有钩子."""
        self.hooks = {t: [] for t in HookType}


class HookChain:
    """执行钩子链."""

    def __init__(self):
        """初始化钩子链."""
        self.registry = HookRegistry.get_instance()

    def execute(self, hook_type: HookType, context: HookContext) -> None:
        """执行指定类型的所有钩子.

        Args:
            hook_type: 钩子类型
            context: 钩子上下文
        """
        hooks = self.registry.hooks.get(hook_type, [])
        if not hooks:
            return

        debug(f"Executing {len(hooks)} hooks for {hook_type.name}")

        for entry in hooks:
            if context.is_propagation_stopped:
                break

            try:
                if entry.condition and not entry.condition(context):
                    continue

                entry.callback(context)
            except Exception as e:
                error(f"Error in hook {entry.callback.__name__}: {e}")
                if hook_type != HookType.ON_ERROR:
                    traceback.print_exc()


def _extract_tool_args(context: HookContext) -> Any:
    """从上下文提取工具参数.

    Args:
        context: 钩子上下文

    Returns:
        工具参数
    """
    if not isinstance(context.tool_args, dict):
        return None
    return context.tool_args.get("args")


def _extract_tool_path(
    tool_name: Optional[str],
    tool_args: Any
) -> Optional[str]:
    """从上下文提取工具路径.

    Args:
        tool_name: 工具名称
        tool_args: 工具参数

    Returns:
        文件路径
    """
    if tool_name == "read" and isinstance(tool_args, str):
        return tool_args
    if tool_name == "write" and isinstance(tool_args, dict):
        return tool_args.get("path") if isinstance(tool_args.get("path"), str) else None
    if tool_name == "write" and isinstance(tool_args, (tuple, list)) and tool_args:
        return tool_args[0] if isinstance(tool_args[0], str) else None
    if tool_name == "edit" and isinstance(tool_args, dict):
        return tool_args.get("path") if isinstance(tool_args.get("path"), str) else None
    if tool_name == "edit" and isinstance(tool_args, (tuple, list)) and tool_args:
        return tool_args[0] if isinstance(tool_args[0], str) else None
    return None


def builtin_security_filter_hook(context: HookContext) -> None:
    """内置安全过滤器钩子.

    检查文件路径是否在工作目录内。

    Args:
        context: 钩子上下文
    """
    tool_args = _extract_tool_args(context)
    target_path = _extract_tool_path(context.tool_name, tool_args)
    if not target_path:
        return
    cwd = "."
    if context.session is not None:
        cwd = context.session.get("cwd", ".")
    try:
        validate_path(target_path, cwd)
    except ValueError:
        context.reject(
            "文件路径越界",
            (
                f"{context.tool_name} 只能访问当前工作目录内的文件。"
                "请改用工作目录内的相对路径，不要使用 .. 或工作区外绝对路径。"
            ),
        )


def _lint_file_content(path: str, content: str) -> Optional[str]:
    """检查文件语法错误.

    Args:
        path: 文件路径
        content: 文件内容

    Returns:
        错误信息，无错误返回 None
    """
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".py":
        try:
            ast.parse(content, filename=path)
        except SyntaxError as exc:
            line = exc.lineno or "?"
            column = exc.offset or "?"
            detail = exc.msg or "Python 语法错误"
            return f"Python 语法错误: {detail} (line {line}, column {column})"
    elif suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            return f"JSON 语法错误: {exc.msg} (line {exc.lineno}, column {exc.colno})"
    return None


def builtin_lint_check_hook(context: HookContext) -> None:
    """内置语法检查钩子.

    在文件写入或编辑后检查语法错误。

    Args:
        context: 钩子上下文
    """
    if context.tool_name not in {"write", "edit"}:
        return
    if not isinstance(context.tool_result, str):
        return
    if not (
        context.tool_result.startswith("Successfully wrote to ")
        or context.tool_result.startswith("Successfully edited ")
    ):
        return
    tool_args = _extract_tool_args(context)
    target_path = _extract_tool_path(context.tool_name, tool_args)
    if not target_path:
        return
    cwd = "."
    if context.session is not None:
        cwd = context.session.get("cwd", ".")
    try:
        safe_path = validate_path(target_path, cwd)
        with open(safe_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except Exception:
        return
    lint_error = _lint_file_content(target_path, content)
    if not lint_error:
        return
    context.tool_result = (
        f"{context.tool_result}\n"
        f"[LINT] {lint_error}\n"
        "请修复该文件后重新执行相关写入。"
    )
    context.set_feedback(
        f"{target_path} 未通过语法校验。\n"
        f"{lint_error}\n"
        "请基于当前文件内容修复后重新提交。"
    )


def _is_registered(
    hook_type: HookType,
    callback: Callable[[HookContext], None]
) -> bool:
    """检查钩子是否已注册.

    Args:
        hook_type: 钩子类型
        callback: 回调函数

    Returns:
        是否已注册
    """
    return any(
        entry.callback is callback
        for entry in registry.hooks.get(hook_type, [])
    )


def register_builtin_hooks() -> None:
    """注册内置钩子."""
    if not _is_registered(HookType.PRE_TOOL, builtin_security_filter_hook):
        registry.register(HookType.PRE_TOOL, builtin_security_filter_hook, priority=100)
    if not _is_registered(HookType.POST_TOOL, builtin_lint_check_hook):
        registry.register(HookType.POST_TOOL, builtin_lint_check_hook, priority=100)


registry = HookRegistry.get_instance()
