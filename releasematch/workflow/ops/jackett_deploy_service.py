# -*- coding: utf-8 -*-
"""
Ops 一键部署 Jackett + FlareSolverr（封装 install_jackett_oneclick.sh）。

@module workflow.ops.jackett_deploy_service
@description
  在本机后台跑 ``scripts/install_jackett_oneclick.sh``（SSH 到 VPS 装 Docker 栈），
  UI 轮询进度。默认值可从 ``servers.local.json`` 预填（密码不回传明文，仅标记已配置）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT
from workflow.ops import config_service

# 一键安装脚本路径
ONECLICK_SCRIPT: Path = PROJECT_ROOT / "scripts" / "install_jackett_oneclick.sh"
# 本地服务器凭据（勿提交）
SERVERS_LOCAL_PATH: Path = (
    PROJECT_ROOT / "workflow" / "torrent_sources" / "servers.local.json"
)

# 进度状态：idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "percent": 0,
    "message": "",
    "log_tail": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
    "host": None,
    "returncode": None,
    "ok": None,
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None
# 日志环形缓冲（行）
_LOG_LINES: List[str] = []
_LOG_MAX_LINES: int = 400


def _set_progress(**kwargs: Any) -> None:
    """
    合并更新进度字典。

    @param kwargs: 要覆盖的字段
    """
    with _PROGRESS_LOCK:
        _PROGRESS.update(kwargs)
        if "log_tail" not in kwargs:
            _PROGRESS["log_tail"] = "\n".join(_LOG_LINES[-120:])


def _append_log(line: str) -> None:
    """
    追加一行日志到缓冲并刷新 log_tail。

    @param line: 原始输出行
    """
    text = (line or "").rstrip("\n")
    if not text:
        return
    with _PROGRESS_LOCK:
        _LOG_LINES.append(text)
        if len(_LOG_LINES) > _LOG_MAX_LINES:
            del _LOG_LINES[: len(_LOG_LINES) - _LOG_MAX_LINES]
        _PROGRESS["log_tail"] = "\n".join(_LOG_LINES[-120:])
        # 用末行做短消息
        _PROGRESS["message"] = text[:200]


def get_progress() -> Dict[str, Any]:
    """
    返回当前部署进度快照。

    @returns: status / percent / message / log_tail / …
    """
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _first_server_entry() -> Optional[Dict[str, Any]]:
    """
    读取 servers.local.json 中第一个含 host 的条目。

    @returns: 条目 dict 或 None
    """
    if not SERVERS_LOCAL_PATH.is_file():
        return None
    try:
        raw = json.loads(SERVERS_LOCAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    for key, val in raw.items():
        if key.startswith("_") or not isinstance(val, dict):
            continue
        if val.get("host"):
            out = dict(val)
            out["_key"] = key
            return out
    return None


def load_defaults() -> Dict[str, Any]:
    """
    供 Ops 表单预填的默认值（密码不回传明文）。

    @returns: host/user/port/has_password/dashboard 等
    """
    entry = _first_server_entry()
    deps = {
        "ssh": bool(shutil.which("ssh")),
        "sshpass": bool(shutil.which("sshpass")),
        "oneclick_script": ONECLICK_SCRIPT.is_file(),
    }
    if not entry:
        return {
            "ok": True,
            "source": None,
            "host": "",
            "user": "root",
            "port": 22,
            "has_password": False,
            "password_hint": "",
            "public_url": "",
            "dashboard_url": "",
            "admin_password_default": "345621",
            "deps": deps,
            "script": str(ONECLICK_SCRIPT.relative_to(PROJECT_ROOT)),
        }

    ssh = entry.get("ssh") if isinstance(entry.get("ssh"), dict) else {}
    jackett = (
        (entry.get("services") or {}).get("jackett")
        if isinstance(entry.get("services"), dict)
        else {}
    )
    password = str(ssh.get("password") or "")
    host = str(entry.get("host") or "")
    return {
        "ok": True,
        "source": entry.get("_key"),
        "label": entry.get("label") or entry.get("_key"),
        "host": host,
        "user": str(ssh.get("user") or "root"),
        "port": int(ssh.get("port") or 22),
        "has_password": bool(password),
        "password_hint": ("已配置（servers.local.json）" if password else ""),
        "public_url": str((jackett or {}).get("public_url") or (f"http://{host}:9117" if host else "")),
        "dashboard_url": str(
            (jackett or {}).get("dashboard_url")
            or (f"http://{host}:9117/UI/Dashboard" if host else "")
        ),
        "admin_password_default": str(
            (jackett or {}).get("admin_password") or os.environ.get("JACKETT_ADMIN_PASSWORD") or "345621"
        ),
        "deps": deps,
        "script": str(ONECLICK_SCRIPT.relative_to(PROJECT_ROOT)),
    }


def _resolve_password(password: Optional[str], *, use_servers_password: bool) -> str:
    """
    解析 SSH 密码：请求体优先，否则 servers.local.json。

    @param password: UI 传入的密码（可空）
    @param use_servers_password: True 且 password 空时读本地凭据
    @returns: 明文密码
    """
    if password and str(password).strip():
        return str(password).strip()
    if use_servers_password:
        entry = _first_server_entry()
        if entry:
            ssh = entry.get("ssh") if isinstance(entry.get("ssh"), dict) else {}
            pw = str(ssh.get("password") or "").strip()
            if pw:
                return pw
    return ""


def start_deploy(
    *,
    host: str,
    password: Optional[str] = None,
    user: str = "root",
    port: int = 22,
    with_indexers: bool = True,
    indexer_profile: str = "all",
    sync_key: bool = True,
    force_recreate: bool = True,
    dry_run: bool = False,
    use_servers_password: bool = True,
    admin_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    后台启动一键安装（立即返回，前端轮询 progress）。

    @param host: VPS IP/域名
    @param password: SSH 密码；空则尝试 servers.local.json
    @param user: SSH 用户
    @param port: SSH 端口
    @param with_indexers: 写入默认 indexer
    @param indexer_profile: all|cn|intl
    @param sync_key: 同步 API Key 到 accounts.local.json
    @param force_recreate: FORCE_RECREATE=1
    @param dry_run: 仅预览
    @param use_servers_password: password 空时读本地
    @param admin_password: Jackett Dashboard 密码（环境变量）
    @returns: {ok, started|already_running, progress}
    """
    global _WORKER

    host_norm = str(host or "").strip()
    if not host_norm:
        return {"ok": False, "error": "缺少 host（VPS IP）"}

    profile = str(indexer_profile or "all").strip().lower()
    if profile not in ("all", "cn", "intl"):
        return {"ok": False, "error": "indexer_profile 须为 all|cn|intl"}

    if not ONECLICK_SCRIPT.is_file():
        return {"ok": False, "error": f"找不到脚本 {ONECLICK_SCRIPT}"}

    pw = _resolve_password(password, use_servers_password=use_servers_password)
    if not pw and not dry_run:
        return {
            "ok": False,
            "error": "缺少 SSH 密码；请填写或在 servers.local.json 配置",
        }

    # 密码只经环境变量 SSHPASS 传递，避免出现在进程命令行
    cmd: List[str] = [
        "bash",
        str(ONECLICK_SCRIPT),
        "--host",
        host_norm,
        "--user",
        str(user or "root"),
        "--port",
        str(int(port or 22)),
        "--indexer-profile",
        profile,
    ]
    if with_indexers:
        cmd.append("--with-indexers")
    else:
        cmd.append("--no-indexers")
    if not sync_key:
        cmd.append("--no-sync")
    if not force_recreate:
        cmd.append("--no-force")
    if dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    env["SSHPASS"] = pw or ""
    env["FORCE_RECREATE"] = "1" if force_recreate else "0"
    if admin_password and str(admin_password).strip():
        env["JACKETT_ADMIN_PASSWORD"] = str(admin_password).strip()

    with _PROGRESS_LOCK:
        if _PROGRESS.get("status") == "running" and _WORKER and _WORKER.is_alive():
            return {
                "ok": True,
                "started": False,
                "already_running": True,
                "progress": dict(_PROGRESS),
            }
        _LOG_LINES.clear()
        _PROGRESS.update(
            {
                "status": "running",
                "percent": 5,
                "message": f"启动安装 {user}@{host_norm}…",
                "log_tail": "",
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "host": host_norm,
                "returncode": None,
                "ok": None,
            }
        )

    def _worker() -> None:
        """后台线程：流式跑 oneclick，更新进度。"""
        rc = -1
        try:
            _append_log(f"$ bash scripts/install_jackett_oneclick.sh --host {host_norm} …")
            _set_progress(percent=10, message="SSH 安装 Docker / Jackett / FlareSolverr…")
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                _append_log(line)
                low = line.lower()
                # 粗粒度进度（按脚本阶段关键字）
                if "docker" in low and "install" in low:
                    _set_progress(percent=25)
                elif "jackett" in low and ("pull" in low or "creat" in low):
                    _set_progress(percent=45)
                elif "flaresolverr" in low:
                    _set_progress(percent=60)
                elif "indexer" in low:
                    _set_progress(percent=75)
                elif "api key" in low or "sync" in low:
                    _set_progress(percent=88)
                elif "安装完成" in line or "dashboard:" in low:
                    _set_progress(percent=95)
            rc = proc.wait(timeout=3600)
            ok = rc == 0
            if ok and sync_key and not dry_run:
                # 同步 Key 后热加载 accounts 到当前 Ops 进程
                try:
                    config_service.apply_runtime_reload()
                    _append_log("[ops] 已热加载 accounts.local.json 到当前进程")
                except Exception as exc:  # noqa: BLE001
                    _append_log(f"[ops] 热加载失败（可手动点「仅加载到进程」）: {exc}")
            _set_progress(
                status="done" if ok else "error",
                percent=100 if ok else 100,
                message=("安装成功" if ok else f"安装失败 exit={rc}"),
                error=None if ok else f"exit_code={rc}",
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                returncode=rc,
                ok=ok,
            )
        except Exception as exc:  # noqa: BLE001
            _append_log(f"[error] {exc}")
            _set_progress(
                status="error",
                percent=100,
                message=str(exc)[:200],
                error=str(exc),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                returncode=rc,
                ok=False,
            )

    _WORKER = threading.Thread(target=_worker, name="ops-jackett-deploy", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}
