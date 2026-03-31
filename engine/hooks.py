"""Agent 执行中的面向切面编程 (AOP) 钩子系统.

支持前置/后置钩子、优先级链和异常处理。
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional
import traceback
from common.io_utils import error, debug

class HookType(Enum):
    """钩子点枚举."""
    PRE_RUN = auto()         # Agent 运行开始前
    POST_RUN = auto()        # Agent 运行结束后
    PRE_LLM = auto()         # LLM API 调用前
    POST_LLM = auto()        # LLM API 调用返回后
    PRE_TOOL = auto()        # 工具执行前
    POST_TOOL = auto()       # 工具执行后
    ON_ERROR = auto()        # 发生错误时

@dataclass
class HookContext:
    """传递给钩子的上下文对象."""
    hook_type: HookType
    agent_id: str = "main"
    task_desc: str = ""
    session: Any = None  # v4.state.session.Session
    llm_input: Optional[List[Dict]] = None
    llm_output: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    tool_result: Optional[str] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def stop_propagation(self):
        """发出停止执行钩子链的信号."""
        self.metadata["_stop_propagation"] = True

    @property
    def is_propagation_stopped(self):
        return self.metadata.get("_stop_propagation", False)

@dataclass
class HookEntry:
    """钩子注册项."""
    callback: Callable[[HookContext], None]
    priority: int = 0  # 值越高越先执行
    condition: Optional[Callable[[HookContext], bool]] = None

class HookRegistry:
    """管理全局和局部钩子."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HookRegistry, cls).__new__(cls)
            cls._instance.hooks: Dict[HookType, List[HookEntry]] = {
                t: [] for t in HookType
            }
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, 
                 hook_type: HookType, 
                 callback: Callable[[HookContext], None], 
                 priority: int = 0,
                 condition: Callable[[HookContext], bool] = None):
        """注册一个钩子."""
        entry = HookEntry(callback, priority, condition)
        self.hooks[hook_type].append(entry)
        # 按优先级降序排序
        self.hooks[hook_type].sort(key=lambda x: x.priority, reverse=True)
        debug(f"Registered hook {callback.__name__} for {hook_type.name} with priority {priority}")

    def clear(self):
        """清空所有钩子."""
        self.hooks = {t: [] for t in HookType}

class HookChain:
    """执行钩子链."""
    
    def __init__(self):
        self.registry = HookRegistry.get_instance()

    def execute(self, hook_type: HookType, context: HookContext):
        """执行指定类型的所有钩子."""
        hooks = self.registry.hooks.get(hook_type, [])
        if not hooks:
            return

        debug(f"Executing {len(hooks)} hooks for {hook_type.name}")
        
        for entry in hooks:
            if context.is_propagation_stopped:
                break
                
            try:
                # 检查条件
                if entry.condition and not entry.condition(context):
                    continue
                    
                entry.callback(context)
            except Exception as e:
                error(f"Error in hook {entry.callback.__name__}: {e}")
                # 如果是 ON_ERROR 钩子，为防止无限循环，仅记录日志
                if hook_type != HookType.ON_ERROR:
                    # 是否应该为钩子错误触发 ON_ERROR 钩子？
                    # 暂时保持简单，仅打印堆栈。
                    traceback.print_exc()

# 全局访问器
registry = HookRegistry.get_instance()
