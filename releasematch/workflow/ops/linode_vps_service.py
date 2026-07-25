# -*- coding: utf-8 -*-
"""
Ops Linode VPS 增删（封装 ``linode_vps.py`` 子进程）。

@module workflow.ops.linode_vps_service
@description
  仅本机 Ops（127.0.0.1）调用。通过 ``--json`` 子进程读写 Linode，
  不把 token / root_pass 回传给浏览器。开通可后台轮询；销毁需 confirm。
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT

# Linode CLI 脚本（独立包，不 import workflow）
LINODE_CLI: Path = PROJECT_ROOT / "workflow" / "torrent_sources" / "linode_vps.py"
# 可选：开通后顺带装 Jackett
ONECLICK_SCRIPT: Path = PROJECT_ROOT / "scripts" / "install_jackett_oneclick.sh"
# 本地配置（gitignore）
LINODE_LOCAL: Path = PROJECT_ROOT / "workflow" / "torrent_sources" / "linode.local.json"
LINODE_EXAMPLE: Path = PROJECT_ROOT / "workflow" / "torrent_sources" / "linode.example.json"

# 进度：idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "percent": 0,
    "message": "",
    "log_tail": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
    "action": None,
    "result": None,
    "returncode": None,
    "ok": None,
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None
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
    追加日志行。

    @param line: 原始输出
    """
    text = (line or "").rstrip("\n")
    if not text:
        return
    # 不把 root 密码写进 UI 日志
    if "root_pass=" in text or '"root_pass"' in text:
        text = "[redacted] root_pass 已隐藏（见 linode.local.json / create 本机输出）"
    with _PROGRESS_LOCK:
        _LOG_LINES.append(text)
        if len(_LOG_LINES) > _LOG_MAX_LINES:
            del _LOG_LINES[: len(_LOG_LINES) - _LOG_MAX_LINES]
        _PROGRESS["log_tail"] = "\n".join(_LOG_LINES[-120:])
        _PROGRESS["message"] = text[:200]


def get_progress() -> Dict[str, Any]:
    """
    返回开通/销毁进度快照。

    @returns: status / percent / message / result / …
    """
    with _PROGRESS_LOCK:
        snap = dict(_PROGRESS)
        # 再次确保不泄露密码
        result = snap.get("result")
        if isinstance(result, dict) and "root_pass" in result:
            result = dict(result)
            result["root_pass"] = "***"
            snap["result"] = result
        return snap


def _redact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    去掉敏感字段后再回传 UI。

    @param payload: CLI JSON
    @returns: 脱敏副本
    """
    out = dict(payload)
    if "root_pass" in out:
        out["root_pass"] = "***" if out.get("root_pass") else ""
        out["root_pass_present"] = bool(payload.get("root_pass"))
    return out


def _parse_json_stdout(stdout: str) -> Dict[str, Any]:
    """
    从 CLI stdout 解析最后一行 JSON。

    @param stdout: 标准输出
    @returns: 解析结果；失败则含 ok=False
    """
    lines = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
    if not lines:
        return {"ok": False, "error": "CLI 无 JSON 输出"}
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"JSON 解析失败: {exc}", "raw": lines[-1][:500]}
    if not isinstance(data, dict):
        return {"ok": False, "error": "CLI JSON 非对象"}
    return data


def _run_cli(
    args: List[str],
    *,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    同步执行 ``linode_vps.py … --json``。

    @param args: 子命令与参数（不含 --json）
    @param timeout: 超时秒数
    @returns: CLI JSON + returncode / stderr
    """
    if not LINODE_CLI.is_file():
        return {"ok": False, "error": f"找不到 {LINODE_CLI}"}
    cmd = [sys.executable, str(LINODE_CLI), *args, "--json"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"CLI 超时（>{timeout}s）", "cmd": args}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "cmd": args}

    payload = _parse_json_stdout(proc.stdout or "")
    if proc.returncode != 0 and payload.get("ok") is not False:
        payload = {
            "ok": False,
            "error": payload.get("error")
            or (proc.stderr or "").strip()
            or f"exit={proc.returncode}",
            **{k: v for k, v in payload.items() if k not in ("ok", "error")},
        }
    payload["returncode"] = proc.returncode
    if proc.stderr and proc.stderr.strip():
        payload["stderr_tail"] = proc.stderr.strip()[-800:]
    return payload


def load_defaults() -> Dict[str, Any]:
    """
    Ops 表单预填（不含 token / 密码明文）。

    @returns: label/region/type/image/deps/config 是否就绪
    """
    deps = {
        "cli": LINODE_CLI.is_file(),
        "config_local": LINODE_LOCAL.is_file(),
        "config_example": LINODE_EXAMPLE.is_file(),
        "linode_api4": False,
        "oneclick_script": ONECLICK_SCRIPT.is_file(),
    }
    try:
        import linode_api4  # noqa: F401

        deps["linode_api4"] = True
    except ImportError:
        deps["linode_api4"] = False

    base: Dict[str, Any] = {
        "ok": True,
        "label": "",
        "region": "jp-osa",
        "type": "g6-nanode-1",
        "image": "linode/debian12",
        "ssh_user": "root",
        "ssh_port": 22,
        "has_ssh_password": False,
        "has_token": False,
        "config_path": None,
        "deps": deps,
        "script": str(LINODE_CLI.relative_to(PROJECT_ROOT)),
        "docs": "docs/linode-vps-lifecycle.md",
    }

    if not LINODE_CLI.is_file():
        base["ok"] = False
        base["error"] = f"缺少 CLI {LINODE_CLI.name}"
        return base

    raw = _run_cli(["defaults"], timeout=30)
    if not raw.get("ok"):
        # defaults 不要求 token；若失败多半是无配置文件
        base["ok"] = True
        base["defaults_error"] = raw.get("error")
        base["hint"] = (
            "请复制 linode.example.json → linode.local.json 并填写 token / defaults"
        )
        return base

    base.update(
        {
            "label": raw.get("label") or "",
            "region": raw.get("region") or base["region"],
            "type": raw.get("type") or base["type"],
            "image": raw.get("image") or base["image"],
            "ssh_user": raw.get("ssh_user") or "root",
            "ssh_port": int(raw.get("ssh_port") or 22),
            "has_ssh_password": bool(raw.get("has_ssh_password")),
            "config_path": raw.get("config_path"),
        }
    )
    # Token：仅探测环境或本地文件是否像已配置（不回传）
    import os

    if os.environ.get("LINODE_TOKEN", "").strip():
        base["has_token"] = True
    elif LINODE_LOCAL.is_file():
        try:
            cfg = json.loads(LINODE_LOCAL.read_text(encoding="utf-8"))
            tok = str((cfg or {}).get("token") or "").strip()
            base["has_token"] = bool(tok) and tok not in (
                "YOUR_LINODE_PERSONAL_ACCESS_TOKEN",
                "YOUR_TOKEN",
            )
        except (OSError, json.JSONDecodeError):
            base["has_token"] = False
    return base


def list_instances() -> Dict[str, Any]:
    """
    列出 Linode 实例（脱敏）。

    @returns: ok / instances / error
    """
    raw = _run_cli(["list"], timeout=60)
    if not raw.get("ok") and "instances" not in raw and "items" not in raw:
        # list 成功时 payload 可能是 {ok, instances:[...]}
        return {
            "ok": False,
            "error": raw.get("error") or "list 失败",
            "stderr_tail": raw.get("stderr_tail"),
            "instances": [],
        }
    instances = raw.get("instances") or raw.get("items") or raw.get("linodes") or []
    if not isinstance(instances, list):
        instances = []
    safe: List[Dict[str, Any]] = []
    for row in instances:
        if not isinstance(row, dict):
            continue
        safe.append(
            {
                "id": row.get("id"),
                "label": row.get("label"),
                "status": row.get("status"),
                "region": row.get("region"),
                "type": row.get("type") or row.get("ltype"),
                "ipv4": row.get("ipv4") or row.get("ip"),
            }
        )
    return {
        "ok": True,
        "instances": safe,
        "count": len(safe),
        "returncode": raw.get("returncode"),
    }


def delete_instance(
    *,
    instance_id: Optional[int] = None,
    label: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    同步销毁实例（须 confirm=True）。

    @param instance_id: Linode 实例 ID
    @param label: 实例 label
    @param confirm: 必须为 True
    @returns: CLI 脱敏结果
    """
    if not confirm:
        return {"ok": False, "error": "销毁须 confirm=true"}
    iid = int(instance_id) if instance_id is not None else None
    lab = str(label or "").strip() or None
    if iid is None and not lab:
        return {"ok": False, "error": "请提供 instance_id 或 label"}

    args: List[str] = ["delete", "--yes"]
    if iid is not None:
        args.extend(["--id", str(iid)])
    if lab:
        args.extend(["--label", lab])

    raw = _run_cli(args, timeout=120)
    return {
        "ok": bool(raw.get("ok")),
        "action": "delete",
        "result": _redact_payload(raw),
        "error": None if raw.get("ok") else (raw.get("error") or "delete 失败"),
    }


def start_create(
    *,
    label: Optional[str] = None,
    region: Optional[str] = None,
    ltype: Optional[str] = None,
    image: Optional[str] = None,
    with_jackett: bool = False,
    with_indexers: bool = True,
) -> Dict[str, Any]:
    """
    后台开通 VPS（可选顺带 ``--provision-linode`` 装 Jackett）。

    @param label: 实例标签；空则用 linode.local.json defaults
    @param region: 区域
    @param ltype: 机型（API 字段 type）
    @param image: 镜像
    @param with_jackett: True 时跑一键脚本开通+装机
    @param with_indexers: 装 Jackett 时是否写 indexer
    @returns: {ok, started|already_running, progress}
    """
    global _WORKER

    if not LINODE_CLI.is_file():
        return {"ok": False, "error": f"找不到 {LINODE_CLI}"}
    if with_jackett and not ONECLICK_SCRIPT.is_file():
        return {"ok": False, "error": f"找不到 {ONECLICK_SCRIPT}"}

    defaults = load_defaults()
    if not defaults.get("has_token") and not with_jackett:
        # provision 脚本也会读同一配置；仍给提示但不硬拦（CLI 会报错）
        pass

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
                "message": "启动 Linode 开通…",
                "log_tail": "",
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "action": "provision" if with_jackett else "create",
                "result": None,
                "returncode": None,
                "ok": None,
            }
        )

    label_s = str(label or "").strip() or None
    region_s = str(region or "").strip() or None
    type_s = str(ltype or "").strip() or None
    image_s = str(image or "").strip() or None

    def _worker() -> None:
        """后台：create 或 provision-linode。"""
        rc = -1
        try:
            if with_jackett:
                cmd = [
                    "bash",
                    str(ONECLICK_SCRIPT),
                    "--provision-linode",
                ]
                if with_indexers:
                    cmd.append("--with-indexers")
                else:
                    cmd.append("--no-indexers")
                _append_log("$ bash scripts/install_jackett_oneclick.sh --provision-linode …")
                _set_progress(percent=10, message="购买 Linode 并安装 Jackett…")
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    _append_log(line)
                    low = line.lower()
                    if "create" in low or "linode" in low:
                        _set_progress(percent=30)
                    elif "ssh" in low or "waiting" in low:
                        _set_progress(percent=50)
                    elif "docker" in low or "jackett" in low:
                        _set_progress(percent=70)
                    elif "完成" in line or "dashboard" in low:
                        _set_progress(percent=90)
                rc = proc.wait(timeout=3600)
                ok = rc == 0
                _set_progress(
                    status="done" if ok else "error",
                    percent=100,
                    message=("开通+装机成功" if ok else f"失败 exit={rc}"),
                    error=None if ok else f"exit_code={rc}",
                    finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    returncode=rc,
                    ok=ok,
                    result={"ok": ok, "action": "provision"},
                )
                return

            args: List[str] = ["create"]
            if label_s:
                args.extend(["--label", label_s])
            if region_s:
                args.extend(["--region", region_s])
            if type_s:
                args.extend(["--type", type_s])
            if image_s:
                args.extend(["--image", image_s])
            _append_log(f"$ python linode_vps.py {' '.join(args)} --json")
            _set_progress(percent=15, message="调用 Linode API 创建实例…")
            cmd = [sys.executable, str(LINODE_CLI), *args, "--json"]
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.stdout is not None and proc.stderr is not None

            def _drain_err() -> None:
                """流式读 stderr 到日志。"""
                for line in proc.stderr:
                    _append_log(line)

            err_thread = threading.Thread(target=_drain_err, daemon=True)
            err_thread.start()
            stdout_data = proc.stdout.read()
            rc = proc.wait(timeout=400)
            err_thread.join(timeout=5)
            _set_progress(percent=85, message="解析创建结果…")
            payload = _parse_json_stdout(stdout_data or "")
            ok = bool(payload.get("ok")) and rc == 0
            safe = _redact_payload(payload)
            if ok:
                _append_log(
                    f"created id={safe.get('id')} label={safe.get('label')} "
                    f"ipv4={safe.get('ipv4')} status={safe.get('status')}"
                )
            else:
                _append_log(f"create failed: {payload.get('error') or rc}")
            _set_progress(
                status="done" if ok else "error",
                percent=100,
                message=(
                    f"开通成功 ipv4={safe.get('ipv4')}"
                    if ok
                    else (payload.get("error") or f"exit={rc}")
                ),
                error=None if ok else (payload.get("error") or f"exit_code={rc}"),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                returncode=rc,
                ok=ok,
                result=safe,
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

    _WORKER = threading.Thread(target=_worker, name="ops-linode-create", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}
