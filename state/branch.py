"""分支管理模块.

支持多线探索与对比，管理多个活跃的 Session 分支。
"""

from typing import Dict, List, Optional

from state.session import Session


class BranchManager:
    """分支管理器."""

    def __init__(self):
        self.branches: Dict[str, Session] = {}
        self.current_branch_id: Optional[str] = None

    def create_branch(self, name: str, base_session: Session) -> str:
        """从现有 Session 创建新分支.

        使用 Snapshot 机制进行深拷贝，避免 deepcopy 处理不可序列化对象的问题。
        """
        # 使用 Session 的 snapshot 机制进行深拷贝
        # 这比 raw deepcopy 更可靠，因为 Snapshot 已处理 Channel 等不可序列化对象
        snapshot = base_session.create_snapshot()

        # 创建新 Session 并从 snapshot 恢复
        new_session = Session()
        snapshot.restore_to(new_session)

        # 更新 session 的 task_stack 以区分分支
        new_session.task_stack.append(f"[Branch: {name}]")

        self.branches[name] = new_session
        return name

    def switch_branch(self, name: str) -> Optional[Session]:
        """切换到指定分支."""
        if name in self.branches:
            self.current_branch_id = name
            return self.branches[name]
        return None

    def list_branches(self) -> List[str]:
        return list(self.branches.keys())

    def merge_branch(self, source_name: str, target_name: str):
        """(高级功能) 合并分支 - 合并对话历史.

        将源分支的差异化对话历史合并到目标分支中，并添加合并标记。
        """
        if source_name not in self.branches or target_name not in self.branches:
            return

        source = self.branches[source_name]
        target = self.branches[target_name]

        # 寻找共同前缀长度 (寻找分歧点)
        common_len = 0
        min_len = min(len(source.history), len(target.history))
        for i in range(min_len):
            # 简单比较 content 和 role
            if (source.history[i].get("role") != target.history[i].get("role") or
                    source.history[i].get("content") != target.history[i].get("content")):
                break
            common_len += 1

        # 获取源分支的新消息
        new_messages = source.history[common_len:]

        if new_messages:
            # 添加合并标记
            target.add_message("system", f"Merging branch '{source_name}' into '{target_name}'.")
            # 追加新消息
            target.history.extend(new_messages)


# 全局实例
branch_manager = BranchManager()
