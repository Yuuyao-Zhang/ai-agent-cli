"""Agent 模块 - 核心任务执行循环.

该模块实现了 Agent 的核心循环逻辑，集成了 Context Assembler、File Index、
Terminal Buffer 和 Security Policy 等组件，支持递归深度控制、调用栈追踪、
上下文隔离与继承以及 Todo 任务规划等功能。

Attributes:
    task_desc: 任务描述
    session: 会话对象
    parent_task_id: 父任务 ID
"""

import time
import traceback
from common.constant import (
    MAX_RECURSION_DEPTH,
    MAX_TURNS_PER_AGENT,
    UNCERTAINTY_KEYWORDS,
    END_KEYWORDS,
    INCOMPLETE_MARKERS,
    MIN_RESPONSE_LENGTH
)
from llm.context import assembler
from llm.llm import call_qwen
from llm.parser import parse_commands
from common.security import security_manager
from common.io_utils import info, debug, error, output, Colors
from llm.terminal import log_output
from engine.tools import execute_instruction
from engine.hooks import HookChain, HookContext, HookType

from state.session import Session
from state.manager import task_manager
from state.task import TaskStatus
from state.checkpoint import checkpoint_manager
from memory import MemoryManager


def append_knowledge_references(response: str, session: Session) -> str:
    """为最终回答追加知识来源引用."""
    if not response or "知识来源引用" in response:
        return response

    cache = session.get("_knowledge_context_cache", {})
    if not isinstance(cache, dict):
        return response

    references = cache.get("references") or []
    if not references:
        return response

    reference_lines = ["知识来源引用:"]
    for ref in references[:3]:
        reference_lines.append(f"- {ref}")
    return response.rstrip() + "\n\n" + "\n".join(reference_lines)


def append_skill_references(response: str, session: Session) -> str:
    """为最终回答追加已激活的 skill 引用."""
    if not response or "技能上下文引用" in response:
        return response

    cache = session.get("_skill_context_cache", {})
    if not isinstance(cache, dict):
        return response

    references = cache.get("references") or []
    if not references:
        return response

    reference_lines = ["技能上下文引用:"]
    for ref in references[:3]:
        reference_lines.append(f"- {ref}")
    return response.rstrip() + "\n\n" + "\n".join(reference_lines)


def run(task_desc: str, session: Session = None, parent_task_id: str = None) -> str:
    """执行 Agent 任务循环.

    v3 Agent 循环:
    集成 TaskManager, Namespace Isolation
    
    v4 Agent 循环:
    集成 Hook System

    v5 Agent 循环:
    集成 MemoryManager, CheckpointManager
    
    Args:
        task_desc: 要执行的任务描述
        session: 会话状态对象 (可选)
        parent_task_id: 父任务 ID (可选)

    Returns:
        任务执行结果或错误信息
    """
    hooks = HookChain()
    
    # 1. 初始化会话
    if session is None:
        session = Session()
        session.task_stack.append(task_desc)

    # v5: 初始化记忆管理器
    memory_manager = MemoryManager(session)

    # Hook: PRE_RUN
    hook_ctx = HookContext(
        hook_type=HookType.PRE_RUN,
        task_desc=task_desc,
        session=session
    )
    hooks.execute(HookType.PRE_RUN, hook_ctx)
    if hook_ctx.is_propagation_stopped:
        return "任务被 PRE_RUN 钩子终止。"

    # 2. 创建并注册任务
    current_task = task_manager.create_task(
        name=task_desc,
        session=session,
        parent_id=parent_task_id
    )
    current_task.start()

    # 3. 递归深度检测
    if session.depth > MAX_RECURSION_DEPTH:
        error_msg = (
            f"达到递归深度限制 (深度 {session.depth})。 "
            f"任务 '{task_desc}' 已中止。"
        )
        error(error_msg)
        current_task.fail(error_msg)
        return f"错误: {error_msg}"

    info(f"[{session.depth}] 开始任务: {task_desc} (ID: {current_task.id})")
    memory_manager.add_message("user", f"User Task:\n{task_desc}")

    turn_count = 0
    
    try:
        # 4. Agent 循环
        while True:
            # 检查任务状态 (例如是否被暂停或终止)
            if current_task.status == TaskStatus.PAUSED:
                info(f"任务 {current_task.id} 已暂停。等待中...")
                time.sleep(1)
                continue

            if current_task.status == TaskStatus.TERMINATED:
                info(f"任务 {current_task.id} 已终止。")
                return "任务已被管理器终止。"

            # 动态 Token 预算与 Context 更新 (v5: 传入 memory_manager)
            final_messages = assembler.assemble_messages(
                task_desc, session, memory_manager=memory_manager
            )

            # Hook: PRE_LLM
            hook_ctx = HookContext(
                hook_type=HookType.PRE_LLM,
                task_desc=task_desc,
                session=session,
                llm_input=final_messages
            )
            hooks.execute(HookType.PRE_LLM, hook_ctx)

            response = call_qwen(final_messages, stream=True)
            
            # Hook: POST_LLM
            hook_ctx = HookContext(
                hook_type=HookType.POST_LLM,
                task_desc=task_desc,
                session=session,
                llm_input=final_messages,
                llm_output=response
            )
            hooks.execute(HookType.POST_LLM, hook_ctx)
            
            if not response:
                error_msg = "LLM API 调用失败。"
                error(error_msg)
                current_task.fail(error_msg)
                return f"错误: {error_msg}"

            turn_count += 1
            if turn_count > MAX_TURNS_PER_AGENT:
                current_task.fail("达到最大对话轮数")
                return "错误: 达到最大对话轮数。任务未完成。"

            output(f"[{session.depth}] AI: {response[:100]}...", color=Colors.DIM)
            # v5: 使用 memory_manager 添加消息
            memory_manager.add_message("assistant", response)

            instructions = parse_commands(response)

            if not instructions:
                if any(kw in response for kw in END_KEYWORDS):
                    current_task.complete()
                    final_response = append_knowledge_references(response, session)
                    final_response = append_skill_references(final_response, session)
                    
                    # Hook: POST_RUN
                    hook_ctx = HookContext(
                        hook_type=HookType.POST_RUN,
                        task_desc=task_desc,
                        session=session,
                        metadata={"result": final_response}
                    )
                    hooks.execute(HookType.POST_RUN, hook_ctx)
                    return final_response

                if len(response.strip()) > MIN_RESPONSE_LENGTH and not any(
                    marker in response for marker in INCOMPLETE_MARKERS
                ):
                    current_task.complete()
                    final_response = append_knowledge_references(response, session)
                    final_response = append_skill_references(final_response, session)
                    
                    # Hook: POST_RUN
                    hook_ctx = HookContext(
                        hook_type=HookType.POST_RUN,
                        task_desc=task_desc,
                        session=session,
                        metadata={"result": final_response}
                    )
                    hooks.execute(HookType.POST_RUN, hook_ctx)
                    return final_response

                # v5: 使用 memory_manager 添加消息
                memory_manager.add_message(
                    "user",
                    "请继续执行任务，或者如果已完成请回复 DONE。"
                )
                continue

            results = []
            user_cancelled = False
            uncertainty_detected = any(k in response.lower() for k in UNCERTAINTY_KEYWORDS)

            for inst_type, inst_args in instructions:
                is_allowed, reason_or_clarification = security_manager.check_authorization(
                    inst_type, inst_args, uncertainty_detected
                )

                if not is_allowed:
                    msg = f"[安全] 用户拒绝执行 {inst_type}。"
                    if reason_or_clarification:
                        msg += f" 说明: {reason_or_clarification}"
                    results.append(msg)
                    user_cancelled = True
                    break

                # Hook: PRE_TOOL
                hook_ctx = HookContext(
                    hook_type=HookType.PRE_TOOL,
                    task_desc=task_desc,
                    session=session,
                    tool_name=inst_type,
                    tool_args={"args": inst_args}
                )
                hooks.execute(HookType.PRE_TOOL, hook_ctx)
                if hook_ctx.is_propagation_stopped:
                    results.append(f"工具 {inst_type} 被钩子拦截。")
                    continue

                if inst_type == 'subtask':
                    sub_task_desc = inst_args
                    info(f"[{session.depth}] -> 分叉子任务: {sub_task_desc}")
                    # 使用 session.fork 创建子会话 (包含 namespace 隔离)
                    sub_session = session.fork(sub_task_desc)
                    # 递归调用，传入当前任务 ID 作为父 ID
                    sub_result = run(sub_task_desc, sub_session, parent_task_id=current_task.id)
                    results.append(f"子任务结果:\n{sub_result}")
                    output_res = sub_result
                else:
                    output_res = execute_instruction(inst_type, inst_args, cwd=session.get('cwd', '.'))
                    log_output(
                        f"指令 ({inst_type}): {inst_args}\n输出:\n{output_res}"
                    )
                    results.append(f"[{inst_type}] 结果:\n{output_res}")

                # Hook: POST_TOOL
                hook_ctx = HookContext(
                    hook_type=HookType.POST_TOOL,
                    task_desc=task_desc,
                    session=session,
                    tool_name=inst_type,
                    tool_args={"args": inst_args},
                    tool_result=str(output_res)
                )
                hooks.execute(HookType.POST_TOOL, hook_ctx)

            if user_cancelled:
                current_task.fail("用户取消")
                return "任务已取消：用户中止了操作。"

            feedback = "\n".join(results)
            debug(f"[{session.depth}] 反馈: {feedback[:200]}...")
            # v5: 使用 memory_manager 添加消息
            memory_manager.add_message("user", f"Tool Results:\n{feedback}")

        current_task.complete()
        return "错误: 无响应"
    
    except KeyboardInterrupt:
        # v5: 中断处理与状态保存
        info("\n[Interrupt] 检测到中断信号 (SIGINT)。正在保存状态...")
        checkpoint_id = checkpoint_manager.create_checkpoint(
            session, 
            description=f"Interrupt during {task_desc}"
        )
        info(f"[Interrupt] 状态已保存至 Checkpoint: {checkpoint_id}")
        current_task.fail("Interrupted by user")
        return f"任务已中断。状态已保存 (ID: {checkpoint_id})。"
        
    except Exception as e:
        # Hook: ON_ERROR
        hook_ctx = HookContext(
            hook_type=HookType.ON_ERROR,
            task_desc=task_desc,
            session=session,
            error=e
        )
        hooks.execute(HookType.ON_ERROR, hook_ctx)
        
        error(f"Agent 循环异常: {e}")
        traceback.print_exc()
        current_task.fail(str(e))
        return f"错误: {e}"
