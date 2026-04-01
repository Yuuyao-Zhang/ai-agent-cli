"""安全策略模块.

该模块实现了 SecurityManager 类，提供多层次的安全检查机制，
包括 URI 白名单过滤、命令风险等级评估、二维 ACL（访问控制矩阵）
以及意图歧义检测等功能。
"""

import json
import re
from typing import Tuple, Optional, Any, Dict, List
from urllib.parse import urlparse

from common.config import config
from common.constant import (
    PERM_EXEC,
    PERM_READ,
    PERM_WRITE,
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_SAFE,
    SENSITIVE_PATH_PATTERNS,
)
from common.io_utils import input_request


class URISecurityPolicy:
    """URI 安全策略类.

    用于验证 URI 是否来自预批准的可信域名。
    """

    def __init__(self, allowed_domains: set = None):
        """初始化 URI 安全策略.

        Args:
            allowed_domains: 可信域名集合
        """
        # 默认可信域名
        default_domains = {
            "github.com",
            "gitee.com",
            "pypi.org",
            "python.org",
            "stackoverflow.com",
            "google.com",
            "baidu.com",
            "raw.githubusercontent.com"
        }

        env_domains = config.security.trusted_domains

        if env_domains:
            env_domains_set = set(d.strip() for d in env_domains.split(',') if d.strip())
            if allowed_domains:
                allowed_domains.update(env_domains_set)
            else:
                allowed_domains = env_domains_set

        self.allowed_domains = allowed_domains or default_domains

    def is_allowed(self, uri: str) -> bool:
        """检查 URI 是否在白名单中.

        Args:
            uri: 要检查的 URI 字符串

        Returns:
            如果 URI 来自白名单中的域名或为本地文件路径，返回 True；
            否则返回 False
        """
        return URISecurityPolicy.check_uri_allowed(uri, self.allowed_domains)

    @staticmethod
    def check_uri_allowed(uri: str, allowed_domains: set) -> bool:
        """检查 URI 是否在白名单中 (静态方法).

        Args:
            uri: 要检查的 URI 字符串
            allowed_domains: 可信域名集合

        Returns:
            如果 URI 来自白名单中的域名或为本地文件路径，返回 True；
            否则返回 False
        """
        try:
            parsed = urlparse(uri)
            if not parsed.scheme or parsed.scheme == 'file':
                return True
            domain = parsed.netloc.lower()
            return domain in allowed_domains
        except Exception:
            return False

    def validate_command(self, command: str) -> bool:
        """验证命令中是否包含可疑 URL.

        该方法检查命令字符串中是否包含 HTTP 或 HTTPS URL，
        并验证这些 URL 是否在白名单中。

        Args:
            command: 要检查的命令字符串

        Returns:
            如果命令中不包含任何不在白名单中的 URL，返回 True；
            否则返回 False
        """
        urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', command)
        for url in urls:
            if not URISecurityPolicy.check_uri_allowed(url, self.allowed_domains):
                return False
        return True


class SecurityManager:
    """安全管理器类.

    提供多层次的安全检查机制，包括：
    1. URI 白名单验证
    2. 命令风险等级评估
    3. 二维 ACL 矩阵（角色×工具）检查
    4. 意图歧义检测
    5. 用户确认机制

    Attributes:
        uri_policy: URI 安全策略
        acl_matrix: 二维 ACL 权限矩阵
        current_role: 当前用户角色
        sensitive_patterns: 敏感操作正则库
        sensitive_paths: 敏感路径模式
    """

    def __init__(self, current_role: str = "admin"):
        """初始化安全管理器.

        Args:
            current_role: 当前用户角色，默认为 "admin"
        """
        # 当前角色
        self.current_role = current_role

        # URI 安全策略
        self.uri_policy = URISecurityPolicy()

        # ============================================
        # 1. 二维 ACL 权限矩阵 (角色 × 工具)
        # ============================================
        # 结构: {角色名: {工具名: 权限级别}}
        self.acl_matrix: Dict[str, Dict[str, str]] = {
            # 管理员：拥有所有权限
            'admin': {
                'read': PERM_READ,
                'todo': PERM_READ,
                'write': PERM_WRITE,
                'edit': PERM_WRITE,
                'bash': PERM_EXEC,
                'subtask': PERM_EXEC,
                'tool': PERM_EXEC  # MCP Tool support
            },
            # 普通用户：不能执行 bash 和 subtask
            'user': {
                'read': PERM_READ,
                'todo': PERM_READ,
                'write': PERM_WRITE,
                'edit': PERM_WRITE,
                'tool': PERM_EXEC  # Allow MCP tools for user
            },
            # 访客：只有只读权限
            'guest': {
                'read': PERM_READ
            }
        }

        # 尝试从环境变量加载自定义 ACL 矩阵
        env_acl = config.security.acl_config
        if env_acl:
            try:
                custom_acl = json.loads(env_acl)
                # 合并自定义 ACL 到默认矩阵
                for role, role_perms in custom_acl.items():
                    if role in self.acl_matrix:
                        self.acl_matrix[role].update(role_perms)
                    else:
                        self.acl_matrix[role] = role_perms
            except json.JSONDecodeError:
                pass  # 忽略无效 JSON

        # ============================================
        # 2. 敏感操作正则库 (针对 Bash)
        # ============================================
        self.sensitive_patterns: List[Tuple[str, int, str]] = [
            (r'rm\s+-[rf]+', RISK_CRITICAL, "High-risk deletion (rm -rf)"),
            (r'chmod\s+', RISK_HIGH, "Permission change (chmod)"),
            (r'chown\s+', RISK_HIGH, "Ownership change (chown)"),
            (r'mv\s+', RISK_MEDIUM, "File movement (mv)"),
            (r'>\s*/dev/s', RISK_CRITICAL, "Device write operation"),
            (r':\(\)\{\s*:\|:&', RISK_CRITICAL, "Fork bomb pattern"),
            (r'wget|curl', RISK_MEDIUM, "Network download"),
            (r'pip\s+install', RISK_MEDIUM, "Package installation"),
            (r'format|mkfs', RISK_CRITICAL, "Disk formatting"),
        ]

        # 3. 敏感路径 (针对 Write/Edit)
        self.sensitive_paths = SENSITIVE_PATH_PATTERNS

    # ============================================
    # ACL 矩阵相关方法
    # ============================================

    def set_current_role(self, role: str) -> None:
        """设置当前用户角色.

        Args:
            role: 角色名称
        """
        if role not in self.acl_matrix:
            raise ValueError(f"Unknown role: {role}. Available roles: {list(self.acl_matrix.keys())}")
        self.current_role = role

    def get_permission(self, tool: str, role: Optional[str] = None) -> Optional[str]:
        """获取指定角色对工具的权限.

        Args:
            tool: 工具名称
            role: 角色名称，默认为当前角色

        Returns:
            权限级别，如果角色或工具没有对应的权限则返回 None
        """
        role_to_check = role or self.current_role
        role_perms = self.acl_matrix.get(role_to_check, {})
        return role_perms.get(tool)

    def has_permission(self, tool: str, required_perm: str, role: Optional[str] = None) -> bool:
        """检查角色是否拥有工具的指定权限.

        Args:
            tool: 工具名称
            required_perm: 需要的权限级别
            role: 角色名称，默认为当前角色

        Returns:
            如果角色拥有所需权限返回 True，否则返回 False
        """
        actual_perm = self.get_permission(tool, role)
        return actual_perm == required_perm

    def can_use_tool(self, tool: str, role: Optional[str] = None) -> bool:
        """检查角色是否可以使用某个工具.

        Args:
            tool: 工具名称
            role: 角色名称，默认为当前角色

        Returns:
            如果角色可以使用工具返回 True，否则返回 False
        """
        if self.get_permission(tool, role) is not None:
            return True

        try:
            from mcp.registry import registry
            return self.get_permission('tool', role) is not None and registry.get_tool(tool) is not None
        except Exception:
            return False

    def list_roles(self) -> List[str]:
        """获取所有可用角色列表.

        Returns:
            角色名称列表
        """
        return list(self.acl_matrix.keys())

    def list_tools_for_role(self, role: Optional[str] = None) -> List[str]:
        """获取指定角色可以使用的工具列表.

        Args:
            role: 角色名称，默认为当前角色

        Returns:
            工具名称列表
        """
        role_to_check = role or self.current_role
        role_perms = self.acl_matrix.get(role_to_check, {})
        return list(role_perms.keys())

    # ============================================
    # 安全检测方法
    # ============================================

    def _detect_ambiguity(self, tool: str, args: Any) -> Tuple[bool, str]:
        """设计意图歧义分析 (基于启发式规则).

        Args:
            tool: 工具名称
            args: 工具参数

        Returns:
            (是否有歧义, 歧义原因描述)
        """
        # 规则 1: 编辑操作如果替换内容极短或为空，可能存在歧义
        if tool == 'edit' and isinstance(args, (list, tuple)) and len(args) >= 2:
            old_str = args[1]
            if len(old_str) < 3:
                return True, "Ambiguous edit target (content too short)"

        # 规则 2: 写入操作如果内容为空，可能存在歧义
        if tool == 'write' and isinstance(args, (list, tuple)) and len(args) >= 2:
            content = args[1]
            if not content.strip():
                return True, "Ambiguous write (empty content)"

        # 规则 3: Bash 命令使用通配符但未指定明确路径
        if tool == 'bash' and isinstance(args, str):
            if '*' in args and '/' not in args and '\\' not in args:
                return True, "Ambiguous wildcard usage (global scope)"

        return False, ""

    def _check_sensitive_path(self, path: str) -> bool:
        """检查路径是否包含敏感目录.

        Args:
            path: 文件路径

        Returns:
            是否包含敏感目录
        """
        for sensitive_path in self.sensitive_paths:
            if re.search(sensitive_path, path, re.IGNORECASE):
                return True
        return False

    def _calculate_risk_score(self, tool: str, args: Any) -> Tuple[int, str]:
        """风险评分引擎.

        Args:
            tool: 工具名称
            args: 工具参数

        Returns:
            (风险评分, 原因描述)
        """
        base_score = RISK_SAFE
        reason = "Safe operation"

        # 基础评分
        if tool in ['write', 'edit']:
            base_score = RISK_LOW
            reason = "File modification"

            # 敏感路径检测
            path = args[0] if isinstance(args, (list, tuple)) and len(args) > 0 else ""
            if path and self._check_sensitive_path(path):
                base_score = RISK_HIGH
                reason = "Modification of sensitive system path"

        elif tool == 'bash':
            base_score = RISK_MEDIUM
            reason = "System command execution"

            # 深度检测 Bash 命令
            if isinstance(args, str):
                # 1. URI 检查
                if not self.uri_policy.validate_command(args):
                    return RISK_HIGH, "Untrusted URL detected"

                # 2. 敏感模式匹配
                for pattern, risk, desc in self.sensitive_patterns:
                    if re.search(pattern, args):
                        if risk > base_score:
                            base_score = risk
                            reason = f"Sensitive operation: {desc}"

        # 歧义性作为加权因子
        is_ambiguous, ambiguity_reason = self._detect_ambiguity(tool, args)
        if is_ambiguous:
            base_score += 2
            reason += f" + {ambiguity_reason}"

        return base_score, reason

    def check_authorization(
        self,
        tool: str,
        args: Any,
        uncertainty_flag: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """执行完整的安全检查.

        Args:
            tool: 工具名称
            args: 工具参数
            uncertainty_flag: 是否触发了不确定性检测

        Returns:
            (是否允许, 原因或澄清说明)
        """
        # ============================================
        # 1. ACL 权限检查
        # ============================================
        if not self.can_use_tool(tool):
            return False, f"Role '{self.current_role}' has no permission to use tool '{tool}'"

        # 2. 风险评分
        risk_score, reason = self._calculate_risk_score(tool, args)

        # 如果触发了不确定性检测，强制提升风险
        if uncertainty_flag:
            risk_score = max(risk_score + 2, RISK_HIGH)
            reason += " + Uncertainty Detected"

        # 3. 自动通过低风险操作
        if risk_score < RISK_MEDIUM:
            return True, None

        # 4. HITL 中断流程 (冻结等待确认)
        return self._hitl_confirm(tool, args, risk_score, reason)

    def _hitl_confirm(
        self,
        tool: str,
        args: Any,
        risk: int,
        reason: str
    ) -> Tuple[bool, Optional[str]]:
        """交互式确认流程.

        Args:
            tool: 工具名称
            args: 工具参数
            risk: 风险评分
            reason: 风险原因

        Returns:
            (是否允许, 原因或澄清说明)
        """
        # 风险颜色映射
        color_code = "\033[93m" if risk < RISK_HIGH else "\033[91m"
        reset_code = "\033[0m"

        print(f"\n{color_code}[SECURITY INTERRUPT] Risk Score: {risk}/10{reset_code}")
        print(f"Operation: {tool}")
        print(f"Args: {args}")
        print(f"Reason: {reason}")

        # 引导澄清模板
        if risk >= RISK_HIGH:
            print("⚠️  High risk operation detected. Please confirm intent.")

        try:
            while True:
                # 二次鉴权流程
                choice = input_request(f"{color_code}Execute this command? (Y/n): {reset_code}").strip().lower()

                if choice in ['y', 'yes', '']:
                    return True, None
                elif choice in ['n', 'no']:
                    # 建立澄清对话模板
                    print("\n[Clarification] Operation cancelled.")
                    clarification = input_request("Please clarify your requirement (or press Enter to skip): ")
                    if clarification:
                        print(f"Recorded clarification: {clarification}")
                        return False, clarification
                    return False, "User cancelled operation."
                else:
                    print("Invalid input. Please enter Y or n.")
        except KeyboardInterrupt:
            print("\n[Security] Operation cancelled by user (KeyboardInterrupt).")
            return False, "User cancelled operation (KeyboardInterrupt)."


# 全局安全管理器实例
security_manager = SecurityManager()
