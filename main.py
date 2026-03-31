"""主程序入口模块.

该模块是 Agent 系统的主入口，提供交互式命令行界面和单次任务执行模式。
支持持久化 To-do 列表、状态机、可视化进度、上下文感知、知识管理等功能。

Attributes:
    banner: 横幅文字
"""

import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.agent import run  # noqa: E402
from common.io_utils import input_request, info, error, Colors, safe_text  # noqa: E402
from state.manager import task_manager  # noqa: E402
from state.session import Session  # noqa: E402
from llm.terminal import log_output  # noqa: E402
from todo.render import renderer  # noqa: E402
from todo.store import to_do_store  # noqa: E402
from common.config import config  # noqa: E402
from skill.manager import manager  # noqa: E402
from mcp.registry import registry, sanitize_server_url  # noqa: E402
from swarm.planner import MapReducePlanner  # noqa: E402
from swarm.scheduler import SwarmScheduler  # noqa: E402
from swarm.consensus import ConsensusStrategy  # noqa: E402
from engine.hooks import HookRegistry, HookType  # noqa: E402
from state.checkpoint import checkpoint_manager  # noqa: E402
from state.branch import branch_manager  # noqa: E402

from knowledge import knowledge_manager  # noqa: E402
from common.logger import logger  # noqa: E402
from mcp.registry import registry as tool_registry  # noqa: E402

try:
    from common.config_file import config_file_manager
    CONFIG_FILE_AVAILABLE = True
except ImportError:
    CONFIG_FILE_AVAILABLE = False


def print_banner():
    """打印 AI Assistant 的 banner."""
    banner = f"""
{Colors.HEADER}╔══════════════════════════════════════════════════════╗
║                    AI Assistant                        ║
╚══════════════════════════════════════════════════════╝{Colors.RESET}
    """
    print(safe_text(banner))


def print_final_result(result: str) -> None:
    """打印最终结果.

    Args:
        result: 最终结果字符串
    """
    separator = f"{Colors.GREEN}{'=' * 60}{Colors.RESET}"
    print(safe_text(f"\n{separator}"))
    print(safe_text(f"{Colors.GREEN}{Colors.BOLD}FINAL RESULT:{Colors.RESET}"))
    print(safe_text(result))
    print(safe_text(f"{separator}\n"))


def show_plan():
    """显示当前任务规划."""
    todos = to_do_store.get_all()
    if todos:
        print(renderer.render(todos))


def show_tasks():
    """显示所有活跃任务."""
    active_tasks = task_manager.get_active_tasks()
    if active_tasks:
        print("\n[活跃任务]:")
        for task in active_tasks:
            print(f"  - {task.id}: {task.name} ({task.status.value})")
    else:
        print("\n无活跃任务。")


class QuitException(Exception):
    """用户主动退出异常."""
    pass


def quit_handler():
    """处理退出命令.

    Raises:
        QuitException: 抛出退出异常
    """
    raise QuitException()


def clear_handler():
    """处理清空命令.

    清空当前 To-do 列表并显示提示信息。
    """
    to_do_store.clear()
    info("To-do 列表已清空。")


def undo_handler():
    """处理撤销命令.

    撤销最后一次更改并显示当前任务规划。
    """
    if to_do_store.rollback():
        info("已撤销上一次更改。")
        show_plan()
    else:
        info("无可撤销内容。")


def show_skills():
    """显示所有可用 Skills."""
    skills = manager.skills
    if not skills:
        print("\n未加载任何技能。")
        return
    print("\n[可用技能]:")
    for name, skill in skills.items():
        print(f"  - {name}: {skill.description}")


def show_tools():
    """显示所有可用工具."""
    tools = registry.list_all_tools()
    print("\n[可用工具]:")
    if not tools:
        print("  (无)")
    for tool in tools:
        print(f"  - {tool}")


def show_hooks():
    """显示已注册的 Hooks."""
    print("\n[已注册的 Hooks]:")
    r = HookRegistry.get_instance()
    has_hooks = False
    for t in HookType:
        hooks = r.hooks.get(t, [])
        if hooks:
            has_hooks = True
            print(f"  {t.name}:")
            for h in hooks:
                print(f"    - {h.callback.__name__} (优先级: {h.priority})")

    if not has_hooks:
        print("  (无)")


def connect_mcp_handler():
    """处理连接 MCP Server."""
    url = input_request("请输入 MCP Server URL: ")
    if url:
        registry.connect_mcp_server(url)


def swarm_handler(main_session: Session):
    """处理 Swarm 任务 (MapReduce)."""
    task = input_request("请输入 Swarm 任务描述: ")
    if not task:
        return

    info(f"正在分析并分解任务: {task}")
    logger.info(f"Starting Swarm task: {task}")

    # 1. Map: Decompose
    subtasks = MapReducePlanner.decompose(task)
    if not subtasks:
        info("任务分解失败。")
        return

    info(f"已分解为 {len(subtasks)} 个子任务:")
    for t in subtasks:
        print(f"  - {t.id}: {t.description}")

    # 2. Parallel Execution
    scheduler = SwarmScheduler(max_workers=min(len(subtasks), 5))
    try:
        results = scheduler.run_batch(subtasks, main_session)
    finally:
        scheduler.shutdown()

    info("所有子任务已完成。结果如下:")
    for tid, res in results.items():
        print(f"  [{tid}] 结果长度: {len(res)}")

    # 3. Reduce: Consensus/Aggregation
    info("正在聚合结果...")
    final_result = ConsensusStrategy.map_reduce(results, task)

    print_final_result(final_result)
    main_session.add_message("assistant", f"Swarm 任务已完成。结果:\n{final_result}")
    logger.info("Swarm task completed")


def checkpoint_handler(session: Session):
    """处理快照管理."""
    print("\n[Checkpoint Menu]")
    print("1. Create Checkpoint")
    print("2. Load Checkpoint")
    print("3. List Checkpoints")
    choice = input_request("Select option (1-3): ")

    if choice == "1":
        desc = input_request("Description: ") or "Manual Save"
        cid = checkpoint_manager.create_checkpoint(session, desc)
        info(f"Checkpoint created: {cid}")
        logger.info(f"Checkpoint created: {cid}")

    elif choice == "2":
        cps = checkpoint_manager.list_checkpoints()
        if not cps:
            info("No checkpoints found.")
            return

        for i, cp in enumerate(cps):
            print(f"{i}. [{cp['time']}] {cp['desc']} (ID: {cp['id']})")

        idx_str = input_request("Select index: ")
        if idx_str.isdigit():
            idx = int(idx_str)
            if 0 <= idx < len(cps):
                cid = cps[idx]['id']
                new_session = checkpoint_manager.load_checkpoint(cid)
                if new_session:
                    # In-place restore
                    session.history = new_session.history
                    session.namespace = new_session.namespace
                    session.task_stack = new_session.task_stack
                    session.depth = new_session.depth
                    # 恢复记忆字段 (Issue 3 Fix)
                    session.global_summary = new_session.global_summary
                    session.summarized_index = new_session.summarized_index

                    # 重新初始化 MemoryManager 吗？Agent.run 会新建，但 Main Loop 里的 session 已更新
                    info("Session restored successfully.")
                    logger.info(f"Session restored from checkpoint: {cid}")
                else:
                    error("Failed to load checkpoint.")
        else:
            error("Invalid index.")

    elif choice == "3":
        cps = checkpoint_manager.list_checkpoints()
        print("\n[Available Checkpoints]:")
        for cp in cps:
            print(f"- {cp['time']} | {cp['id']} | {cp['desc']}")


def branch_handler(session: Session):
    """处理分支管理."""
    print("\n[Branch Menu]")
    print("1. Create Branch from Current")
    print("2. Switch Branch")
    print("3. List Branches")
    choice = input_request("Select option (1-3): ")

    if choice == "1":
        name = input_request("Branch Name: ")
        if name:
            branch_manager.create_branch(name, session)
            info(f"Branch '{name}' created.")
            logger.info(f"Branch created: {name}")

    elif choice == "2":
        branches = branch_manager.list_branches()
        print(f"Branches: {branches}")
        name = input_request("Branch Name to Switch: ")
        new_sess = branch_manager.switch_branch(name)
        if new_sess:
            # 同样需要原地更新 main_session
            session.history = new_sess.history
            session.namespace = new_sess.namespace
            session.task_stack = new_sess.task_stack
            session.depth = new_sess.depth
            # 恢复记忆字段 (Issue 3 Fix)
            session.global_summary = new_sess.global_summary
            session.summarized_index = new_sess.summarized_index

            info(f"Switched to branch '{name}'.")
            logger.info(f"Switched to branch: {name}")
        else:
            error("Branch not found.")

    elif choice == "3":
        branches = branch_manager.list_branches()
        print("\n[Active Branches]:")
        current = branch_manager.current_branch_id or "Main"
        for b in branches:
            marker = "*" if b == current else " "
            print(f"{marker} {b}")


def history_handler(session: Session):
    """查看记忆状态."""
    # MemoryManager 将 global_summary 存储在 session.global_summary (dataclass 字段)
    # 而不是 session namespace 中，所以直接访问字段
    summary = session.global_summary or "(None)"
    print(f"\n[Long Term Memory (Summary)]: {len(summary)} chars")
    print(summary[:200] + "..." if len(summary) > 200 else summary)
    print(f"\n[Short Term Memory]: {len(session.history)} messages")
    print(f"[Summarized Index]: {session.summarized_index} (已压缩的历史消息数)")


def knowledge_handler():
    """处理知识管理."""
    print("\n[Knowledge Menu]")
    print(f"Default Knowledge Dir: {knowledge_manager.default_knowledge_dir}")
    print("1. Search Knowledge")
    print("2. Index File")
    print("3. Index Directory")
    print("4. List All Knowledge")
    print("5. Add Custom Knowledge")
    print("6. Sync Default Knowledge Directory")
    choice = input_request("Select option (1-6): ")

    if choice == "1":
        query = input_request("Search query: ")
        if query:
            results = knowledge_manager.search(query, top_k=5)
            if results:
                print(f"\nFound {len(results)} results:")
                for i, (entry, score) in enumerate(results, 1):
                    print(f"\n{i}. [Score: {score:.2f}] {entry.tags}")
                    print(entry.content[:300] + "..." if len(entry.content) > 300 else entry.content)
            else:
                info("No results found.")

    elif choice == "2":
        file_path = input_request("File path: ")
        if file_path:
            entry_id = knowledge_manager.index_file(file_path)
            if entry_id:
                info(f"File indexed: {entry_id}")
                logger.info(f"File indexed: {file_path}")
            else:
                error("Failed to index file.")

    elif choice == "3":
        dir_path = input_request("Directory path: ")
        ext_str = input_request("Extensions (comma separated, e.g., .py,.md): ")
        extensions = [e.strip() for e in ext_str.split(",")] if ext_str else None
        if dir_path:
            count = knowledge_manager.index_directory(dir_path, extensions=extensions)
            info(f"Indexed {count} files.")
            logger.info(f"Indexed {count} files from {dir_path}")

    elif choice == "4":
        knowledge_manager.sync_auto_sources()
        entries = knowledge_manager.list_all()
        print(f"\nTotal knowledge entries: {len(entries)}")
        for entry in entries:
            print(f"  - {entry.id}: {entry.tags} ({len(entry.content)} chars)")

    elif choice == "5":
        content = input_request("Knowledge content: ")
        tags_str = input_request("Tags (comma separated): ")
        tags = [t.strip() for t in tags_str.split(",")] if tags_str else []
        if content:
            entry_id = knowledge_manager.add_knowledge(content, tags=tags)
            info(f"Knowledge added: {entry_id}")
            logger.info(f"Knowledge added: {entry_id}")

    elif choice == "6":
        result = knowledge_manager.sync_auto_sources(tags=["knowledge", "python"])
        info(
            "Synced knowledge directory: "
            f"indexed={result['indexed']}, "
            f"updated={result['updated']}, "
            f"removed={result['removed']}, "
            f"skipped={result['skipped']}"
        )
        logger.info(f"Knowledge directory synced: {knowledge_manager.default_knowledge_dir}")


def config_handler():
    """处理配置管理."""
    print("\n[Config Menu]")
    print("1. Show Current Config")
    print("2. Reload Config")
    if CONFIG_FILE_AVAILABLE:
        print("3. Create Default Config File")
    choice = input_request("Select option (1-3): ")

    if choice == "1":
        print("\n[Current Config]:")
        print(f"  LLM Model: {config.get_llm_model()}")
        print(f"  Debug Mode: {config.is_debug_mode()}")
        print(f"  Log Level: {config.get_log_level()}")
        print(f"  To-do Path: {config.get_todo_storage_path()}")
        print(f"  Checkpoint Dir: {config.get_checkpoint_dir()}")
        print(f"  Vector DB Dir: {config.get_vector_db_dir()}")

    elif choice == "2":
        if CONFIG_FILE_AVAILABLE:
            config_file_manager.reload()
            info("Config reloaded.")
            logger.info("Config reloaded")
        else:
            info("Config file not available.")

    elif choice == "3" and CONFIG_FILE_AVAILABLE:
        path = input_request("Config file path (default: agent_config.yaml): ") or "agent_config.yaml"
        config_file_manager.create_default_config(path)


def demo_handler(main_session: Session):
    info("正在运行 Demo 流程")
    try:
        def word_count_tool(args: dict):
            text = str(args.get("text", ""))
            return {"words": len(text.split()), "chars": len(text), "preview": text[:50]}
        tool_registry.register_local_tool("word_count", word_count_tool)
    except Exception:
        pass
    task = "围绕“Agent Harness 的最小实现要点”，给出分解任务：资料收集、要点整理、风险与取舍，并最终汇总为一段 200 字说明。"
    info(f"正在分解: {task}")
    logger.info("Demo: decompose")
    subtasks = MapReducePlanner.decompose(task, num_parts=3)
    if not subtasks:
        info("任务分解失败。")
        return
    info(f"生成子任务: {len(subtasks)}")
    scheduler = SwarmScheduler(max_workers=min(len(subtasks), 3))
    try:
        results = scheduler.run_batch(subtasks, main_session)
    finally:
        scheduler.shutdown()
    info("正在汇总结果")
    final_result = ConsensusStrategy.map_reduce(results, task)
    print_final_result(final_result)
    main_session.add_message("assistant", f"Demo 完成:\n{final_result}")
    logger.info("Demo completed")


# Command Handlers
COMMAND_HANDLERS = {
    "q": quit_handler,
    "quit": quit_handler,
    "exit": quit_handler,
    "plan": show_plan,
    "tasks": show_tasks,
    "clear": clear_handler,
    "undo": undo_handler,
    "skills": show_skills,
    "tools": show_tools,
    "connect": connect_mcp_handler,
    "hooks": show_hooks,
}


def main():
    """主函数，处理程序初始化和主事件循环."""
    try:
        print_banner()
        if not config.get_llm_api_key():
            print(
                f"{Colors.YELLOW}警告: 未设置 DASHSCOPE_API_KEY 环境变量。{Colors.RESET}"
            )
            print(
                "请使用以下命令设置: set DASHSCOPE_API_KEY=your_key (Windows) "
                "或 export DASHSCOPE_API_KEY=your_key (Linux/Mac)"
            )
            print("或使用 'config' 命令创建配置文件。")

        info("正在初始化 v7 Agent...")
        info("特性: 知识管理, 配置文件, 日志系统, 分层记忆, 快照回溯, 蜂群智能")
        logger.info("v7 Agent initialized")

        # 初始化 Skill 系统
        manager.initialize()
        manager.start_hot_reload()

        # 自动连接配置的 MCP 服务器
        if CONFIG_FILE_AVAILABLE and config_file_manager.config.mcp.servers:
            info(f"正在连接 {len(config_file_manager.config.mcp.servers)} 个 MCP 服务器...")
            for url in config_file_manager.config.mcp.servers:
                safe_url = sanitize_server_url(url)
                try:
                    connected = registry.connect_mcp_server(url)
                    if connected:
                        logger.info(f"Connected to MCP server: {safe_url}")
                    else:
                        logger.error(f"Failed to connect to MCP server: {safe_url}")
                except Exception as e:
                    logger.error(f"Failed to connect to MCP server {safe_url}: {e}")

        # 检查是否有残留任务并提示
        if to_do_store.get_all():
            info("已加载上次会话的 To-do 列表。")
            info("输入 'plan' 查看, 或输入 'clear' 清空。")

        # 主事件循环
        # 如果有命令行参数，作为单次任务执行
        if len(sys.argv) > 1:
            task = sys.argv[1]
            if task.strip().lower() == "demo":
                main_session = Session()
                demo_handler(main_session)
            else:
                log_output(f"System: 开始执行单次任务: {task}")
                logger.info(f"Starting single task: {task}")
                result = run(task)
                print_final_result(result)
                show_plan()
        else:
            # 交互式循环
            main_session = Session()

            while True:
                try:
                    task = input_request(
                        "\n用户 (kn知识, config配置, cp快照, br分支, mem记忆, swarm蜂群, q退出)> "
                    )
                    cmd = task.strip().lower()

                    # Dispatch command
                    if cmd in COMMAND_HANDLERS:
                        COMMAND_HANDLERS[cmd]()
                        continue

                    if cmd == "swarm":
                        swarm_handler(main_session)
                        continue

                    if cmd == "demo":
                        demo_handler(main_session)
                        continue

                    if cmd in ["cp", "checkpoint"]:
                        checkpoint_handler(main_session)
                        continue

                    if cmd in ["br", "branch"]:
                        branch_handler(main_session)
                        continue

                    if cmd in ["mem", "memory", "history"]:
                        history_handler(main_session)
                        continue

                    if cmd in ["kn", "knowledge"]:
                        knowledge_handler()
                        continue

                    if cmd == "config":
                        config_handler()
                        continue

                    if not task.strip():
                        continue

                    log_output(f"用户输入: {task}")
                    logger.info(f"User input: {task}")

                    # 执行任务
                    result = run(task, main_session)

                    # 美化输出最终结果
                    print_final_result(result)

                    # 每次交互后显示最新进度
                    show_plan()

                except QuitException:
                    info("用户退出。")
                    break
                except KeyboardInterrupt:
                    info("\n已中断。")
                    # 仅在 Ctrl+C 时提示保存
                    if input_request("Save checkpoint? (y/n): ").lower() == 'y':
                        checkpoint_manager.create_checkpoint(main_session, "Exit Save")
                    break
                except Exception as e:
                    info(f"错误: {e}")
                    log_output(f"错误: {e}")
                    logger.error(f"Error: {e}", exc_info=True)
    finally:
        # Ensure terminal state is restored (colors reset)
        print(Colors.RESET, end="")
        info("会话已关闭。")
        logger.info("Session closed")


if __name__ == "__main__":
    main()
