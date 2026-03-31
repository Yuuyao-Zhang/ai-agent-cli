"""常量配置模块.

该模块定义了 v3 Agent 系统的各种常量配置，包括递归深度限制、
每 Agent 最大回合数、缓冲区大小限制以及 Token 预算等。
所有配置值都在这里集中管理，便于统一调整。
"""

# ==================== Agent 行为限制 ====================
# 防止资源耗尽和无限循环
MAX_RECURSION_DEPTH: int = 10
MAX_TURNS_PER_AGENT: int = 20

# ==================== 缓冲区与 Token 限制 ====================
# 管理内存使用和 API 调用
MAX_BUFFER_LINES: int = 50
MAX_TOTAL_TOKENS_PER_AGENT: int = 8000

# ==================== 上下文配置比例 ====================
# 构建上下文时的占比分配
SYSTEM_RATIO: float = 0.2
HISTORY_RATIO: float = 0.6
FILE_TREE_RATIO: float = 0.05
TERMINAL_RATIO: float = 0.05
DYNAMIC_RATIO: float = 0.1

# ==================== 文件操作限制 ====================
# 限制文件系统操作的资源消耗
FILE_TREE_MAX_DEPTH: int = 3
FILE_TREE_MAX_LINES: int = 50
FILE_REF_TRUNCATE_LENGTH: int = 500
RECENT_FILE_OPS_LIMIT: int = 5

# ==================== 安全策略常量 ====================
# 风险等级、权限控制和访问限制
RISK_SAFE: int = 0
RISK_LOW: int = 3
RISK_MEDIUM: int = 5
RISK_HIGH: int = 8
RISK_CRITICAL: int = 10

# 权限级别
PERM_READ: str = "readonly"
PERM_WRITE: str = "readwrite"
PERM_EXEC: str = "execute"

# 风险等级字典（兼容旧代码）
RISK_LEVELS: dict[str, int] = {
    "safe": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}

# 需要用户确认的高风险命令
DANGEROUS_COMMANDS: list[str] = [
    "rm", "del", "format", "mkfs",
    "dd", "fdisk", "diskpart"
]

# 文件访问限制
RESTRICTED_PATHS: list[str] = [
    "/etc/passwd", "/etc/shadow",
    "C:\\Windows\\System32"
]

# 敏感路径模式
SENSITIVE_PATH_PATTERNS: list[str] = [
    r'[/\\]etc[/\\]',
    r'C:[/\\]Windows',
    r'/usr/',
    r'/bin/',
    r'/sbin/'
]

# 默认可信域名
DEFAULT_TRUSTED_DOMAINS: set[str] = {
    "github.com",
    "gitee.com",
    "pypi.org",
    "python.org",
    "stackoverflow.com",
    "google.com",
    "baidu.com",
    "raw.githubusercontent.com"
}

# ==================== 文本匹配常量 ====================
# 检测和解析 Agent 响应
UNCERTAINTY_KEYWORDS: list[str] = [
    "不确定", "uncertain", "maybe", "perhaps",
    "可能", "应该", "probably", "might"
]

END_KEYWORDS: list[str] = [
    "任务完成", "done", "completed",
    "success", "finished", "ok"
]

INCOMPLETE_MARKERS: list[str] = [
    "...", "待续", "to be continued",
    "稍后", "later"
]

MIN_RESPONSE_LENGTH: int = 10

# ==================== LLM 配置默认值 ====================
# 与 LLM API 交互的配置
LLM_MAX_RETRIES: int = 3
LLM_RETRY_DELAY: float = 1.0
LLM_TIMEOUT: int = 60

# ==================== 应用配置 ====================
# 应用程序的通用配置
IGNORED_DIRS: set[str] = {
    "__pycache__", "venv", "node_modules",
    ".git", ".svn", ".hg", "dist", "build"
}
IGNORED_FILE_PREFIX: str = "."

# Token 估算比例（字符数 / Token 数）
TOKEN_ESTIMATE_RATIO: int = 4

# 终端输出行数限制
TERMINAL_OUTPUT_LINES: int = 20
