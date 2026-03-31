"""状态检查点与快照管理模块.

实现 Checkpoint 快照机制，保存任意时刻完整状态。
"""

import copy
import pickle
import time
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from state.session import Session

CHECKPOINT_DIR = "checkpoints"


@dataclass
class Checkpoint:
    """状态快照."""
    id: str
    timestamp: float
    description: str
    session_state: Session  # 序列化的 Session 对象
    tags: List[str] = field(default_factory=list)


class CheckpointManager:
    """快照管理器."""

    def __init__(self, root_dir: str = CHECKPOINT_DIR):
        """初始化快照管理器.

        Args:
            root_dir: 快照存储根目录
        """
        self.root_dir = root_dir
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir, exist_ok=True)

    def create_checkpoint(self, session: Session, description: str = "Auto-save", tags: List[str] = None) -> str:
        """创建当前会话的快照.

        Args:
            session: 会话对象
            description: 快照描述
            tags: 标签列表

        Returns:
            快照ID
        """
        checkpoint_id = str(uuid.uuid4())[:8]
        # 使用 copy.deepcopy 深拷贝 session，确保快照不随原对象变化
        # Session 对象的 __getstate__/__setstate__ 已处理不可序列化的 Channel

        cp = Checkpoint(
            id=checkpoint_id,
            timestamp=time.time(),
            description=description,
            session_state=copy.deepcopy(session),  # 深拷贝确保快照独立性
            tags=tags or []
        )

        file_path = os.path.join(self.root_dir, f"{checkpoint_id}.pkl")
        with open(file_path, "wb") as f:
            pickle.dump(cp, f)

        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Session]:
        """加载快照并恢复 Session.

        Args:
            checkpoint_id: 快照ID

        Returns:
            恢复的会话对象，如果失败则返回None
        """
        file_path = os.path.join(self.root_dir, f"{checkpoint_id}.pkl")
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            cp: Checkpoint = pickle.load(f)
            return cp.session_state

    def list_checkpoints(self) -> List[Dict]:
        """列出所有快照.

        Returns:
            快照信息列表，按时间倒序排列
        """
        results = []
        if not os.path.exists(self.root_dir):
            return []

        for filename in os.listdir(self.root_dir):
            if filename.endswith(".pkl"):
                try:
                    path = os.path.join(self.root_dir, filename)
                    with open(path, "rb") as f:
                        cp = pickle.load(f)
                        results.append({
                            "id": cp.id,
                            "time": cp.timestamp,  # 使用原始时间戳
                            "display_time": time.ctime(cp.timestamp),
                            "desc": cp.description,
                            "tags": cp.tags,
                        })
                except Exception:
                    continue
        return sorted(results, key=lambda x: x["time"], reverse=True)


# 全局实例
checkpoint_manager = CheckpointManager()
