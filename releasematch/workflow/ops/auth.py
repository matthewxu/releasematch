# -*- coding: utf-8 -*-
"""
Ops 控制台登录会话（密码 + HttpOnly Cookie）。

@module workflow.ops.auth
@description
  密码来自环境变量 ``RM_OPS_PASSWORD``（可经 .env / 配置页热加载）。
  未设置密码时不做登录门禁（启动时打印警告）；设置后校验 Cookie 会话。
"""

from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional, Tuple

# Cookie 名（HttpOnly）
OPS_SESSION_COOKIE: str = "rm_ops_session"

# 环境变量：登录密码（非空则启用门禁）
ENV_OPS_PASSWORD: str = "RM_OPS_PASSWORD"
# 环境变量：会话有效小时数
ENV_OPS_SESSION_HOURS: str = "RM_OPS_SESSION_HOURS"
# 环境变量：显式关闭门禁（1/true 时即使设了密码也不校验；仅本地排障）
ENV_OPS_AUTH_DISABLED: str = "RM_OPS_AUTH_DISABLED"

# 默认会话时长（小时）
DEFAULT_SESSION_HOURS: float = 72.0

# 进程内会话表：token → {exp, pwd_fp}
_SESSIONS: Dict[str, Dict[str, Any]] = {}
# 保护会话表的锁（ThreadingHTTPServer）
_LOCK = threading.Lock()


def _env_bool(name: str, default: bool = False) -> bool:
    """
    解析布尔环境变量。

    @param name: 变量名
    @param default: 默认值
    @returns: 是否为真
    """
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def get_ops_password() -> str:
    """
    读取当前 Ops 登录密码。

    @returns: 密码字符串；未配置为空串
    """
    return os.getenv(ENV_OPS_PASSWORD, "").strip()


def get_session_hours() -> float:
    """
    读取会话有效期（小时）。

    @returns: 小时数，至少 1
    """
    raw = os.getenv(ENV_OPS_SESSION_HOURS, "").strip()
    try:
        hours = float(raw) if raw else DEFAULT_SESSION_HOURS
    except ValueError:
        hours = DEFAULT_SESSION_HOURS
    return max(1.0, hours)


def is_auth_disabled() -> bool:
    """
    是否显式关闭登录门禁。

    @returns: True 表示不校验密码
    """
    return _env_bool(ENV_OPS_AUTH_DISABLED, False)


def is_auth_required() -> bool:
    """
    是否启用登录门禁。

    @returns: 已配置密码且未显式关闭时为 True
    """
    if is_auth_disabled():
        return False
    return bool(get_ops_password())


def password_fingerprint(password: str) -> str:
    """
    密码指纹（改密后使旧会话失效）。

    @param password: 明文密码
    @returns: 短 hex 摘要
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()[:24]


def clear_all_sessions() -> int:
    """
    清除全部会话（改密 / 登出全部）。

    @returns: 清除条数
    """
    with _LOCK:
        n = len(_SESSIONS)
        _SESSIONS.clear()
        return n


def create_session() -> Tuple[str, int]:
    """
    创建新会话 token。

    @returns: (token, max_age_sec)
    """
    token = secrets.token_urlsafe(32)
    max_age = int(get_session_hours() * 3600)
    pwd = get_ops_password()
    with _LOCK:
        _SESSIONS[token] = {
            "exp": time.time() + max_age,
            "pwd_fp": password_fingerprint(pwd),
        }
    return token, max_age


def revoke_session(token: Optional[str]) -> None:
    """
    撤销单个会话。

    @param token: Cookie 中的会话 token
    @returns: None
    """
    if not token:
        return
    with _LOCK:
        _SESSIONS.pop(token, None)


def verify_session(token: Optional[str]) -> bool:
    """
    校验会话是否有效。

    @param token: Cookie 中的会话 token
    @returns: 有效为 True
    """
    if not token:
        return False
    pwd = get_ops_password()
    if not pwd:
        return False
    now = time.time()
    fp = password_fingerprint(pwd)
    with _LOCK:
        row = _SESSIONS.get(token)
        if not row:
            return False
        if float(row.get("exp") or 0) < now:
            _SESSIONS.pop(token, None)
            return False
        if row.get("pwd_fp") != fp:
            _SESSIONS.pop(token, None)
            return False
        return True


def parse_session_cookie(cookie_header: Optional[str]) -> Optional[str]:
    """
    从 Cookie 头解析会话 token。

    @param cookie_header: HTTP Cookie 头
    @returns: token 或 None
    """
    if not cookie_header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:  # noqa: BLE001
        return None
    morsel = jar.get(OPS_SESSION_COOKIE)
    if not morsel:
        return None
    value = (morsel.value or "").strip()
    return value or None


def build_set_cookie(token: str, max_age: int) -> str:
    """
    构造登录成功的 Set-Cookie 头值。

    @param token: 会话 token
    @param max_age: 秒
    @returns: Set-Cookie 字符串（不含头名）
    """
    # 本机 HTTP：不加 Secure；HttpOnly + SameSite=Strict
    return (
        f"{OPS_SESSION_COOKIE}={token}; Path=/; Max-Age={max_age}; "
        "HttpOnly; SameSite=Strict"
    )


def build_clear_cookie() -> str:
    """
    构造清除会话的 Set-Cookie。

    @returns: Set-Cookie 字符串
    """
    return (
        f"{OPS_SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"
    )


def check_password(candidate: str) -> bool:
    """
    恒定时间比较登录密码。

    @param candidate: 用户输入
    @returns: 是否匹配
    """
    expected = get_ops_password()
    if not expected:
        return False
    return secrets.compare_digest(
        candidate.encode("utf-8"),
        expected.encode("utf-8"),
    )


def auth_status(*, cookie_header: Optional[str] = None) -> Dict[str, Any]:
    """
    汇总认证状态（供 /api/auth/status）。

    @param cookie_header: 请求 Cookie
    @returns: auth_required / authenticated / session_hours 等
    """
    required = is_auth_required()
    token = parse_session_cookie(cookie_header)
    authenticated = (not required) or verify_session(token)
    return {
        "ok": True,
        "auth_required": required,
        "auth_disabled": is_auth_disabled(),
        "password_configured": bool(get_ops_password()),
        "authenticated": authenticated,
        "session_hours": get_session_hours(),
        "cookie_name": OPS_SESSION_COOKIE,
    }


def is_public_path(path: str) -> bool:
    """
    未登录也可访问的路径。

    @param path: URL path
    @returns: 是否公开
    """
    if path in (
        "/login.html",
        "/login.js",
        "/ops.css",
        "/api/auth/status",
        "/api/auth/login",
    ):
        return True
    return False


def startup_auth_message() -> str:
    """
    启动时打印的认证说明。

    @returns: 单行日志
    """
    if is_auth_disabled():
        return "[ops] 登录门禁已关闭（RM_OPS_AUTH_DISABLED=1）— 仅建议本机排障使用"
    if not get_ops_password():
        return (
            "[ops] 警告: 未设置 RM_OPS_PASSWORD，登录保护未启用。"
            "请在 .env 或配置页设置后热加载。"
        )
    return (
        f"[ops] 登录门禁已启用（会话 {get_session_hours():g}h，"
        "Cookie HttpOnly）→ /login.html"
    )
