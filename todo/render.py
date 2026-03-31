"""To-do 可视化渲染模块.

该模块实现了 To-do 列表的可视化渲染器，展示当前规划与执行进度，
包括进度条、任务列表和状态图标等。
"""

from typing import List

from todo.store import ToDoItem, ToDoStatus


class ToDoRenderer:
    """To-do 渲染器类.

    负责将 To-do 列表渲染为可视化的文本格式，包括进度条和状态图标。
    """

    @staticmethod
    def render(todos: List[ToDoItem]) -> str:
        """渲染 To-do 列表为可视化文本.

        Args:
            todos: To-do 项目列表

        Returns:
            渲染后的可视化文本，包含进度条和任务列表
        """
        if not todos:
            return "No tasks planned."

        lines = ["\n[Task Plan]"]

        # 统计进度
        total = len(todos)
        completed = len([t for t in todos if t.status == ToDoStatus.COMPLETED])
        progress = (completed / total) * 100 if total > 0 else 0

        # 进度条
        bar_len = 20
        filled = int(progress / 100 * bar_len)
        bar = "#" * filled + "-" * (bar_len - filled)
        lines.append(f"Progress: [{bar}] {completed}/{total} ({int(progress)}%)")
        lines.append("-" * 40)

        # 状态图标映射
        status_symbols = {
            ToDoStatus.PENDING: "[ ]",
            ToDoStatus.IN_PROGRESS: "[>]",
            ToDoStatus.COMPLETED: "[x]",
            ToDoStatus.FAILED: "[!]",
            ToDoStatus.SKIPPED: "[>]"
        }

        # 任务列表
        for todo in todos:
            symbol = status_symbols.get(todo.status, "?")
            lines.append(f"{todo.id}. {symbol} {todo.content} ({todo.priority})")

        lines.append("-" * 40)
        return "\n".join(lines)


# 全局渲染器实例
renderer = ToDoRenderer()
