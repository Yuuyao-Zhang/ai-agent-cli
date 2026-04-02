"""Agent 执行中的面向切面编程 (AOP) 钩子系统.

支持前置/后置钩子、优先级链和异常处理。
"""

import ast
import json
import os
import threading
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from common.config import YAML_AVAILABLE
from common.file_lock import FileLock
from common.io_utils import debug, error
from engine.tools import validate_path

if YAML_AVAILABLE:
    import yaml
else:
    yaml = None


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
    _instance_lock = threading.Lock()

    def __new__(cls):
        """单例模式实现."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.hooks: Dict[HookType, List[HookEntry]] = {
                        t: [] for t in HookType
                    }
        return cls._instance

    @classmethod
    def get_instance(cls):
        """获取单例实例."""
        return cls()

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
        self.reset()

    def reset(self) -> None:
        """重置所有钩子."""
        self.hooks = {t: [] for t in HookType}


registry = HookRegistry.get_instance()

LLM_FINISH_REASON_METADATA_KEY = "llm_finish_reason"
CONTINUATION_REQUIRED_METADATA_KEY = "continuation_required"
CONTINUATION_PROMPT_METADATA_KEY = "continuation_prompt"
HOOK_FILE_SNAPSHOT_METADATA_KEY = "hook_file_snapshot"


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

            original_error = context.error
            try:
                if entry.condition and not entry.condition(context):
                    continue

                entry.callback(context)
            except Exception as e:
                if hook_type == HookType.ON_ERROR and original_error is not None:
                    context.metadata.setdefault("original_error", repr(original_error))
                error(f"Error in hook {entry.callback.__name__}: {e}")
                traceback.print_exc()
                if hook_type == HookType.ON_ERROR:
                    error("ON_ERROR hook 执行失败，继续传播原始错误")


class RollbackStatus(Enum):
    """回滚状态枚举.

    Attributes:
        MISSING_SNAPSHOT: 缺少快照
        SKIPPED_SIGNATURE_MISMATCH: 签名不匹配跳过
        RESTORED: 已恢复
        DELETED_NEW_FILE: 已删除新建文件
        FAILED: 失败
    """

    MISSING_SNAPSHOT = "missing_snapshot"
    SKIPPED_SIGNATURE_MISMATCH = "skipped_signature_mismatch"
    RESTORED = "restored"
    DELETED_NEW_FILE = "deleted_new_file"
    FAILED = "failed"


@dataclass
class RollbackResult:
    """回滚结果数据类.

    Attributes:
        status: 回滚状态
        message: 结果消息
    """

    status: RollbackStatus
    message: Optional[str] = None


def _session_get(session: Any, key: str, default: Any = None) -> Any:
    """从会话中安全获取值.

    Args:
        session: 会话对象
        key: 键名
        default: 默认值

    Returns:
        获取到的值或默认值
    """
    if session is None:
        return default
    getter = getattr(session, "get", None)
    if not callable(getter):
        return default
    try:
        return getter(key, default)
    except TypeError:
        return default


def _session_set(session: Any, key: str, value: Any) -> bool:
    """安全设置会话中的值.

    Args:
        session: 会话对象
        key: 键名
        value: 值

    Returns:
        是否设置成功
    """
    if session is None:
        return False
    setter = getattr(session, "set", None)
    if not callable(setter):
        return False
    try:
        setter(key, value)
        return True
    except TypeError:
        return False


def _read_file_with_lock(path: str) -> str:
    """带锁读取文件内容.

    Args:
        path: 文件路径

    Returns:
        文件内容
    """
    with open(path, "r", encoding="utf-8") as handle:
        with FileLock(handle, exclusive=False):
            return handle.read()


def _write_file_with_lock(path: str, content: str) -> None:
    """带锁写入文件内容.

    Args:
        path: 文件路径
        content: 文件内容
    """
    with open(path, "w", encoding="utf-8") as handle:
        with FileLock(handle, exclusive=True):
            handle.write(content)


def _get_file_signature(path: str) -> Optional[tuple[int, int]]:
    """获取文件签名.

    Args:
        path: 文件路径

    Returns:
        由修改时间和大小组成的签名，不存在则返回 None
    """
    try:
        stat_result = os.stat(path)
    except FileNotFoundError:
        return None
    return (stat_result.st_mtime_ns, stat_result.st_size)


def _read_file_with_lock_and_signature(path: str) -> tuple[str, Optional[tuple[int, int]]]:
    """带锁读取文件内容和签名.

    Args:
        path: 文件路径

    Returns:
        文件内容和签名
    """
    with open(path, "r", encoding="utf-8") as handle:
        with FileLock(handle, exclusive=False):
            content = handle.read()
            stat_result = os.fstat(handle.fileno())
            signature = (stat_result.st_mtime_ns, stat_result.st_size)
            return content, signature


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
        path = tool_args.get("path")
        return path if isinstance(path, str) else None
    if tool_name == "write" and isinstance(tool_args, (tuple, list)) and tool_args:
        return tool_args[0] if isinstance(tool_args[0], str) else None
    if tool_name == "edit" and isinstance(tool_args, dict):
        path = tool_args.get("path")
        return path if isinstance(path, str) else None
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
    cwd = _session_get(context.session, "cwd", ".")
    try:
        validate_path(target_path, cwd)
    except (OSError, PermissionError, ValueError) as exc:
        context.reject(
            "文件路径越界",
            (
                f"{context.tool_name} 只能访问当前工作目录内的文件。"
                "请改用工作目录内的相对路径，不要使用 .. 或工作区外绝对路径。"
                f"\n校验失败原因: {exc}"
            ),
        )


def _get_snapshot_store(session: Any) -> Dict[str, Dict[str, Any]]:
    """获取会话中的快照存储.

    Args:
        session: 会话对象

    Returns:
        快照存储字典
    """
    if session is None:
        return {}
    snapshots = _session_get(session, "_hook_file_snapshots", {})
    if not isinstance(snapshots, dict):
        snapshots = {}
        _session_set(session, "_hook_file_snapshots", snapshots)
    return snapshots


def _save_file_snapshot(
    session: Any,
    safe_path: str,
    snapshot: Dict[str, Any]
) -> None:
    """保存文件快照到会话.

    Args:
        session: 会话对象
        safe_path: 安全路径
        snapshot: 快照数据
    """
    if session is None:
        return
    snapshots = _get_snapshot_store(session)
    snapshots[safe_path] = snapshot
    _session_set(session, "_hook_file_snapshots", snapshots)


def _pop_file_snapshot(
    session: Any,
    safe_path: str
) -> Optional[Dict[str, Any]]:
    """从会话中弹出文件快照.

    Args:
        session: 会话对象
        safe_path: 安全路径

    Returns:
        快照数据或 None
    """
    if session is None:
        return None
    snapshots = _get_snapshot_store(session)
    snapshot = snapshots.pop(safe_path, None)
    _session_set(session, "_hook_file_snapshots", snapshots)
    return snapshot


def _consume_file_snapshot(
    context: HookContext,
    safe_path: str
) -> Optional[Dict[str, Any]]:
    """消费文件快照并存储到上下文元数据.

    Args:
        context: 钩子上下文
        safe_path: 安全路径

    Returns:
        快照数据或 None
    """
    snapshot = _pop_file_snapshot(context.session, safe_path)
    if snapshot is not None:
        context.metadata[HOOK_FILE_SNAPSHOT_METADATA_KEY] = snapshot
    return snapshot


def builtin_lint_snapshot_hook(context: HookContext) -> None:
    """内置语法检查快照钩子.

    在文件写入或编辑前保存文件快照。

    Args:
        context: 钩子上下文
    """
    if context.tool_name not in {"write", "edit"}:
        return
    tool_args = _extract_tool_args(context)
    target_path = _extract_tool_path(context.tool_name, tool_args)
    if not target_path:
        return
    cwd = _session_get(context.session, "cwd", ".")
    try:
        safe_path = validate_path(target_path, cwd)
    except (OSError, PermissionError, ValueError):
        return
    exists_before = os.path.exists(safe_path)
    content_before = None
    if exists_before:
        try:
            content_before = _read_file_with_lock(safe_path)
        except Exception:
            return
    _save_file_snapshot(
        context.session,
        safe_path,
        {
            "display_path": target_path,
            "exists_before": exists_before,
            "content_before": content_before,
        },
    )


def _resolve_safe_tool_path(context: HookContext) -> Optional[str]:
    """解析工具的安全路径.

    Args:
        context: 钩子上下文

    Returns:
        安全路径或 None
    """
    tool_args = _extract_tool_args(context)
    target_path = _extract_tool_path(context.tool_name, tool_args)
    if not target_path:
        return None
    cwd = _session_get(context.session, "cwd", ".")
    try:
        return validate_path(target_path, cwd)
    except (OSError, PermissionError, ValueError):
        return None


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
    elif suffix in {".yaml", ".yml"} and YAML_AVAILABLE and yaml is not None:
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            return f"YAML 语法错误: {str(exc).strip()}"
    return None


def _rollback_file_snapshot(
    session: Any,
    safe_path: str,
    snapshot: Optional[Dict[str, Any]],
    expected_signature: Optional[tuple[int, int]] = None
) -> RollbackResult:
    """回滚文件快照.

    Args:
        session: 会话对象
        safe_path: 安全路径
        snapshot: 快照数据
        expected_signature: 回滚前预期的当前文件签名

    Returns:
        回滚结果
    """
    if not snapshot:
        return RollbackResult(status=RollbackStatus.MISSING_SNAPSHOT)
    try:
        if expected_signature is not None:
            current_signature = _get_file_signature(safe_path)
            if current_signature != expected_signature:
                return RollbackResult(
                    status=RollbackStatus.SKIPPED_SIGNATURE_MISMATCH,
                    message="检测到文件在回滚前已被其他进程修改，已跳过自动回滚。",
                )
        if snapshot.get("exists_before"):
            _write_file_with_lock(safe_path, snapshot.get("content_before") or "")
            return RollbackResult(
                status=RollbackStatus.RESTORED,
                message="已自动回滚到写入前内容。",
            )
        try:
            os.remove(safe_path)
        except FileNotFoundError:
            pass
        return RollbackResult(
            status=RollbackStatus.DELETED_NEW_FILE,
            message="已删除本次新建的无效文件。",
        )
    except PermissionError as exc:
        return RollbackResult(
            status=RollbackStatus.FAILED,
            message=f"自动回滚失败（权限不足）: {exc}",
        )
    except OSError as exc:
        return RollbackResult(
            status=RollbackStatus.FAILED,
            message=f"自动回滚失败（系统错误）: {exc}",
        )
    except Exception as exc:
        return RollbackResult(
            status=RollbackStatus.FAILED,
            message=f"自动回滚失败: {exc}",
        )


def _read_current_file_state(
    safe_path: str,
    snapshot: Optional[Dict[str, Any]]
) -> str:
    """读取当前文件状态.

    Args:
        safe_path: 安全路径
        snapshot: 快照数据

    Returns:
        文件状态描述
    """
    if snapshot is not None:
        if snapshot.get("exists_before"):
            content = snapshot.get("content_before") or ""
            return (
                "当前文件已恢复到写前内容。\n"
                "当前文件内容:\n"
                f"{content[:2000]}"
            )
        return "当前文件不存在，请重新生成完整文件内容。"
    if not os.path.exists(safe_path):
        return "当前文件不存在，请重新生成完整文件内容。"
    try:
        content = _read_file_with_lock(safe_path)
        return (
            "当前文件内容:\n"
            f"{content[:2000]}"
        )
    except Exception as exc:
        return f"无法读取当前文件状态: {exc}"


def _build_lint_feedback(
    target_path: str,
    lint_error: str,
    rollback_result: RollbackResult,
    safe_path: str,
    snapshot: Optional[Dict[str, Any]]
) -> str:
    """构建语法检查反馈信息.

    Args:
        target_path: 目标路径
        lint_error: 语法错误信息
        rollback_message: 回滚消息
        safe_path: 安全路径
        snapshot: 快照数据

    Returns:
        反馈信息
    """
    if rollback_result.status in {
        RollbackStatus.RESTORED,
        RollbackStatus.DELETED_NEW_FILE,
    }:
        state_snapshot = snapshot
    else:
        state_snapshot = None
    parts = [
        f"{target_path} 未通过语法校验。",
        lint_error,
        rollback_result.message or "未执行自动回滚。",
        _read_current_file_state(safe_path, state_snapshot),
        "请基于当前文件状态重新提交正确的 write 或 edit 指令。"
    ]
    return "\n".join(part for part in parts if part)


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
    safe_path = _resolve_safe_tool_path(context)
    if not safe_path:
        return
    if not (
        context.tool_result.startswith("Successfully wrote to ")
        or context.tool_result.startswith("Successfully edited ")
    ):
        _consume_file_snapshot(context, safe_path)
        return
    tool_args = _extract_tool_args(context)
    target_path = _extract_tool_path(context.tool_name, tool_args)
    if not target_path:
        _consume_file_snapshot(context, safe_path)
        return
    try:
        content, current_signature = _read_file_with_lock_and_signature(safe_path)
    except Exception:
        _consume_file_snapshot(context, safe_path)
        return
    snapshot = _consume_file_snapshot(context, safe_path)
    lint_error = _lint_file_content(target_path, content)
    if not lint_error:
        return
    rollback_result = _rollback_file_snapshot(
        context.session,
        safe_path,
        snapshot,
        expected_signature=current_signature,
    )
    feedback = _build_lint_feedback(
        target_path,
        lint_error,
        rollback_result,
        safe_path,
        snapshot,
    )
    context.tool_result = (
        f"{context.tool_result}\n"
        f"[LINT] {lint_error}\n"
        f"{rollback_result.message or '未执行自动回滚。'}\n"
        "请修复该文件后重新执行相关写入。"
    )
    context.set_feedback(feedback)


def builtin_llm_continuation_hook(context: HookContext) -> None:
    """内置 LLM 续写钩子.

    当 LLM 输出因 token 限制被截断时，设置续写提示。

    Args:
        context: 钩子上下文
    """
    finish_reason = context.metadata.get(LLM_FINISH_REASON_METADATA_KEY)
    if finish_reason != "length":
        return
    if not isinstance(context.llm_output, str):
        return
    if not context.llm_output.strip():
        return
    context.metadata[CONTINUATION_REQUIRED_METADATA_KEY] = True
    context.metadata[CONTINUATION_PROMPT_METADATA_KEY] = (
        "你上一轮的输出因 token 限制被截断。"
        "请从刚才中断的位置继续，仅输出剩余内容，不要重复已输出部分；"
        "如果任务已经完成，请直接回复 DONE。"
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
    if not _is_registered(HookType.POST_LLM, builtin_llm_continuation_hook):
        registry.register(HookType.POST_LLM, builtin_llm_continuation_hook, priority=100)
    if not _is_registered(HookType.PRE_TOOL, builtin_security_filter_hook):
        registry.register(HookType.PRE_TOOL, builtin_security_filter_hook, priority=100)
    if not _is_registered(HookType.PRE_TOOL, builtin_lint_snapshot_hook):
        registry.register(HookType.PRE_TOOL, builtin_lint_snapshot_hook, priority=90)
    if not _is_registered(HookType.POST_TOOL, builtin_lint_check_hook):
        registry.register(HookType.POST_TOOL, builtin_lint_check_hook, priority=100)
