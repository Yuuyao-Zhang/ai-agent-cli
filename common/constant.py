"""常量配置模块.

该模块定义了系统的核心不可变常量。
可配置的参数（如 Token 限制、超时时间等）已迁移至 config.yaml 中。
"""

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

# ==================== 应用配置 ====================
# 应用程序的通用配置
IGNORED_DIRS: set[str] = {
    "__pycache__", "venv", "node_modules",
    ".git", ".svn", ".hg", "dist", "build"
}
IGNORED_FILE_PREFIX: str = "."

# Token 估算比例（字符数 / Token 数）
TOKEN_ESTIMATE_RATIO: int = 4
