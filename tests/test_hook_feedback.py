import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine import agent
from engine.hooks import HookContext, HookType, register_builtin_hooks, registry
from state.session import Session
from state.task import Task


class DummyMemoryManager:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content):
        self.messages.append((role, content))


class HookFeedbackTests(unittest.TestCase):
    def setUp(self):
        registry.clear()

    def tearDown(self):
        registry.clear()

    def test_hook_context_reject_sets_reason_and_feedback(self):
        context = HookContext(hook_type=HookType.PRE_TOOL)

        context.reject("拒绝执行", "请调整参数后重试")

        self.assertTrue(context.is_propagation_stopped)
        self.assertEqual(context.decision, "reject")
        self.assertEqual(context.reject_reason, "拒绝执行")
        self.assertEqual(context.feedback, "请调整参数后重试")

    def test_stop_propagation_preserves_empty_string_reason_and_feedback(self):
        context = HookContext(hook_type=HookType.PRE_TOOL)

        context.stop_propagation(reason="", feedback="")

        self.assertTrue(context.is_propagation_stopped)
        self.assertEqual(context.reject_reason, "")
        self.assertEqual(context.feedback, "")

    def test_resolve_hook_tool_args_returns_default_when_tool_args_is_not_dict(self):
        context = HookContext(hook_type=HookType.PRE_TOOL, tool_args="invalid")

        resolved = agent._resolve_hook_tool_args(context, {"path": "a.txt"})

        self.assertEqual(resolved, {"path": "a.txt"})

    def test_post_llm_reject_feeds_back_into_next_round(self):
        memory_manager = DummyMemoryManager()
        responses = iter(["bad output", "DONE valid output"])

        def post_llm_validator(context):
            if context.llm_output == "bad output":
                context.reject("响应未通过校验", "请按照 DONE 格式重新输出。")

        registry.register(HookType.POST_LLM, post_llm_validator)

        with patch.object(agent.task_manager, "create_task", return_value=Task(id="t1", name="task")), \
             patch.object(agent, "create_memory_manager", return_value=memory_manager), \
             patch.object(agent.assembler, "assemble_messages", return_value=[{"role": "user", "content": "task"}]), \
             patch.object(agent, "call_qwen", side_effect=lambda *args, **kwargs: next(responses)) as call_qwen_mock, \
             patch.object(agent, "parse_commands", side_effect=lambda response: []):
            result = agent.run("task", session=Session())

        self.assertEqual(result, "DONE valid output")
        self.assertEqual(call_qwen_mock.call_count, 2)
        self.assertIn(
            ("user", "响应未通过校验\n请按照 DONE 格式重新输出。"),
            memory_manager.messages,
        )
        self.assertIn(("assistant", "DONE valid output"), memory_manager.messages)

    def test_post_llm_reject_skips_command_execution_from_rejected_response(self):
        memory_manager = DummyMemoryManager()
        responses = iter(['write("a.txt", "bad")', "DONE valid output"])
        execute_instruction_mock = MagicMock()

        def post_llm_validator(context):
            if context.llm_output == 'write("a.txt", "bad")':
                context.reject("响应未通过校验", "请重新生成指令。")

        registry.register(HookType.POST_LLM, post_llm_validator)

        with patch.object(agent.task_manager, "create_task", return_value=Task(id="t1b", name="task")), \
             patch.object(agent, "create_memory_manager", return_value=memory_manager), \
             patch.object(agent.assembler, "assemble_messages", return_value=[{"role": "user", "content": "task"}]), \
             patch.object(agent, "call_qwen", side_effect=lambda *args, **kwargs: next(responses)), \
             patch.object(agent, "parse_commands", side_effect=lambda response: [("write", {"path": "a.txt"})] if response == 'write("a.txt", "bad")' else []), \
             patch.object(agent.security_manager, "check_authorization", return_value=(True, None)), \
             patch.object(agent, "execute_instruction", execute_instruction_mock):
            result = agent.run("task", session=Session())

        self.assertEqual(result, "DONE valid output")
        execute_instruction_mock.assert_not_called()
        self.assertIn(
            ("user", "响应未通过校验\n请重新生成指令。"),
            memory_manager.messages,
        )

    def test_pre_tool_reject_uses_hook_feedback_and_skips_execution(self):
        memory_manager = DummyMemoryManager()
        responses = iter(["tool round", "DONE finished"])

        def pre_tool_validator(context):
            if context.tool_name == "write":
                context.reject("写入前校验未通过", "请先修复格式问题后再重试。")

        registry.register(HookType.PRE_TOOL, pre_tool_validator)

        execute_instruction_mock = MagicMock(return_value="should not run")

        with patch.object(agent.task_manager, "create_task", return_value=Task(id="t2", name="task")), \
             patch.object(agent, "create_memory_manager", return_value=memory_manager), \
             patch.object(agent.assembler, "assemble_messages", return_value=[{"role": "user", "content": "task"}]), \
             patch.object(agent, "call_qwen", side_effect=lambda *args, **kwargs: next(responses)), \
             patch.object(agent, "parse_commands", side_effect=lambda response: [("write", {"path": "a.txt"})] if response == "tool round" else []), \
             patch.object(agent.security_manager, "check_authorization", return_value=(True, None)), \
             patch.object(agent, "execute_instruction", execute_instruction_mock):
            result = agent.run("task", session=Session())

        self.assertEqual(result, "DONE finished")
        execute_instruction_mock.assert_not_called()
        tool_feedback_messages = [
            content for role, content in memory_manager.messages
            if role == "user" and content.startswith("Tool Results:\n")
        ]
        self.assertTrue(tool_feedback_messages)
        self.assertIn("写入前校验未通过", tool_feedback_messages[0])
        self.assertIn("请先修复格式问题后再重试。", tool_feedback_messages[0])

    def test_register_builtin_hooks_is_idempotent(self):
        register_builtin_hooks()
        register_builtin_hooks()

        pre_tool_hooks = registry.hooks[HookType.PRE_TOOL]
        security_hooks = [
            entry for entry in pre_tool_hooks
            if entry.callback.__name__ == "builtin_security_filter_hook"
        ]
        post_tool_hooks = registry.hooks[HookType.POST_TOOL]
        lint_hooks = [
            entry for entry in post_tool_hooks
            if entry.callback.__name__ == "builtin_lint_check_hook"
        ]
        self.assertEqual(len(security_hooks), 1)
        self.assertEqual(len(lint_hooks), 1)

    def test_builtin_security_filter_rejects_outside_workspace_path(self):
        memory_manager = DummyMemoryManager()
        responses = iter(["tool round", "DONE finished"])
        execute_instruction_mock = MagicMock(return_value="should not run")
        session = Session()
        session.set("cwd", str(PROJECT_ROOT))

        with patch.object(agent.task_manager, "create_task", return_value=Task(id="t3", name="task")), \
             patch.object(agent, "create_memory_manager", return_value=memory_manager), \
             patch.object(agent.assembler, "assemble_messages", return_value=[{"role": "user", "content": "task"}]), \
             patch.object(agent, "call_qwen", side_effect=lambda *args, **kwargs: next(responses)), \
             patch.object(agent, "parse_commands", side_effect=lambda response: [("write", ("..\\outside.txt", "x"))] if response == "tool round" else []), \
             patch.object(agent.security_manager, "check_authorization", return_value=(True, None)), \
             patch.object(agent, "execute_instruction", execute_instruction_mock):
            result = agent.run("task", session=session)

        self.assertEqual(result, "DONE finished")
        execute_instruction_mock.assert_not_called()
        tool_feedback_messages = [
            content for role, content in memory_manager.messages
            if role == "user" and content.startswith("Tool Results:\n")
        ]
        self.assertTrue(tool_feedback_messages)
        self.assertIn("文件路径越界", tool_feedback_messages[0])
        self.assertIn("只能访问当前工作目录内的文件", tool_feedback_messages[0])

    def test_builtin_lint_check_hook_reports_python_syntax_error(self):
        memory_manager = DummyMemoryManager()
        responses = iter(["tool round", "DONE finished"])
        session = Session()

        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            session.set("cwd", temp_dir)
            with patch.object(agent.task_manager, "create_task", return_value=Task(id="t4", name="task")), \
                 patch.object(agent, "create_memory_manager", return_value=memory_manager), \
                 patch.object(agent.assembler, "assemble_messages", return_value=[{"role": "user", "content": "task"}]), \
                 patch.object(agent, "call_qwen", side_effect=lambda *args, **kwargs: next(responses)), \
                 patch.object(agent, "parse_commands", side_effect=lambda response: [("write", ("broken.py", "def broken(:\n    pass\n"))] if response == "tool round" else []), \
                 patch.object(agent.security_manager, "check_authorization", return_value=(True, None)):
                result = agent.run("task", session=session)

        self.assertEqual(result, "DONE finished")
        tool_feedback_messages = [
            content for role, content in memory_manager.messages
            if role == "user" and content.startswith("Tool Results:\n")
        ]
        self.assertTrue(tool_feedback_messages)
        self.assertIn("[write] 结果:", tool_feedback_messages[0])
        self.assertIn("[LINT] Python 语法错误", tool_feedback_messages[0])
        self.assertIn("broken.py 未通过语法校验", tool_feedback_messages[0])


if __name__ == "__main__":
    unittest.main()
