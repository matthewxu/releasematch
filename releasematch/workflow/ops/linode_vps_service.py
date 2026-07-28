# -*- coding: utf-8 -*-
"""
Ops Linode VPS 增删（封装 ``linode_vps.py`` 子进程）。

@module workflow.ops.linode_vps_service
@description
  仅本机 Ops（127.0.0.1）调用。通过 ``--json`` 子进程读写 Linode，
  不把 token / root_pass 回传给浏览器。开通/销毁均为后台任务，
  进度含 ``phases[]`` 分项状态 + ``log_tail`` 供 UI 详细反馈。
"""

from __future__ import annotations

import json
import os
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
    "phase": "",
    "phases": [],
    "log_tail": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
    "elapsed_sec": 0,
    "action": None,
    "target": None,
    "result": None,
    "returncode": None,
    "ok": None,
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None
_LOG_LINES: List[str] = []
_LOG_MAX_LINES: int = 500
_STARTED_MONO: float = 0.0


def _utc_now() -> str:
    """UTC ISO 时间戳。"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _elapsed() -> int:
    """自任务开始经过的秒数。"""
    if _STARTED_MONO <= 0:
        return 0
    return int(max(0, time.monotonic() - _STARTED_MONO))


def _set_progress(**kwargs: Any) -> None:
    """
    合并更新进度字典。

    @param kwargs: 要覆盖的字段
    """
    with _PROGRESS_LOCK:
        _PROGRESS.update(kwargs)
        _PROGRESS["elapsed_sec"] = _elapsed()
        if "log_tail" not in kwargs:
            _PROGRESS["log_tail"] = "\n".join(_LOG_LINES[-160:])


def _append_log(line: str) -> None:
    """
    追加日志行（脱敏 root_pass）。

    @param line: 原始输出
    """
    text = (line or "").rstrip("\n")
    if not text:
        return
    if "root_pass=" in text or '"root_pass"' in text:
        text = "[redacted] root_pass 已隐藏（见 linode.local.json / create 本机输出）"
    with _PROGRESS_LOCK:
        _LOG_LINES.append(text)
        if len(_LOG_LINES) > _LOG_MAX_LINES:
            del _LOG_LINES[: len(_LOG_LINES) - _LOG_MAX_LINES]
        _PROGRESS["log_tail"] = "\n".join(_LOG_LINES[-160:])
        _PROGRESS["message"] = text[:240]
        _PROGRESS["elapsed_sec"] = _elapsed()


def _init_phases(specs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    初始化分项阶段列表。

    @param specs: [{id, label}, …]
    @returns: phases（status=pending）
    """
    return [
        {
            "id": str(s["id"]),
            "label": str(s["label"]),
            "status": "pending",
            "detail": "",
            "at": None,
        }
        for s in specs
    ]


def _set_phase(phase_id: str, status: str, detail: str = "", *, percent: Optional[int] = None) -> None:
    """
    更新某一阶段状态，并标记当前 phase。

    @param phase_id: 阶段 id
    @param status: pending|running|done|error|skipped
    @param detail: 短说明
    @param percent: 可选总进度 0–100
    """
    with _PROGRESS_LOCK:
        phases = list(_PROGRESS.get("phases") or [])
        found = False
        for p in phases:
            if p.get("id") == phase_id:
                p["status"] = status
                if detail:
                    p["detail"] = detail[:300]
                if status in ("running", "done", "error"):
                    p["at"] = _utc_now()
                found = True
                break
        if not found:
            phases.append(
                {
                    "id": phase_id,
                    "label": phase_id,
                    "status": status,
                    "detail": detail[:300],
                    "at": _utc_now(),
                }
            )
        # 进入 running 时，把前序 pending 保持；当前标 running
        _PROGRESS["phases"] = phases
        _PROGRESS["phase"] = phase_id
        if detail:
            _PROGRESS["message"] = detail[:240]
        if percent is not None:
            _PROGRESS["percent"] = int(percent)
        _PROGRESS["elapsed_sec"] = _elapsed()


def get_progress() -> Dict[str, Any]:
    """
    返回开通/销毁进度快照（含 phases）。

    @returns: status / percent / phases / log_tail / result / …
    """
    with _PROGRESS_LOCK:
        snap = dict(_PROGRESS)
        snap["elapsed_sec"] = _elapsed() if snap.get("status") == "running" else snap.get(
            "elapsed_sec", 0
        )
        snap["phases"] = [dict(p) for p in (snap.get("phases") or [])]
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
        # 完整注释：旧版 CLI 失败只写 stderr；调用方应附带 stderr_tail
        return {"ok": False, "error": "CLI 无 JSON 输出"}
    # 从末行向前找第一个可解析的 JSON 对象（中间可能有杂讯行）
    data: Any = None
    raw_line = ""
    for ln in reversed(lines):
        try:
            data = json.loads(ln)
            raw_line = ln
            break
        except json.JSONDecodeError:
            continue
    if data is None:
        return {
            "ok": False,
            "error": f"JSON 解析失败: 末行非 JSON",
            "raw": lines[-1][:500],
        }
    if not isinstance(data, dict):
        return {"ok": False, "error": "CLI JSON 非对象", "raw": raw_line[:500]}
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


def _busy() -> bool:
    """是否已有后台任务在跑。"""
    return bool(
        _PROGRESS.get("status") == "running" and _WORKER and _WORKER.is_alive()
    )


def _begin_job(action: str, target: str, phases: List[Dict[str, str]], message: str) -> Optional[Dict[str, Any]]:
    """
    若空闲则初始化进度并返回 None；若忙碌返回 already_running 响应。

    @param action: create|provision|delete
    @param target: 展示用目标描述
    @param phases: 阶段规格
    @param message: 起始消息
    @returns: already_running 响应或 None
    """
    global _STARTED_MONO
    with _PROGRESS_LOCK:
        if _busy():
            return {
                "ok": True,
                "started": False,
                "already_running": True,
                "progress": dict(_PROGRESS),
            }
        _LOG_LINES.clear()
        _STARTED_MONO = time.monotonic()
        _PROGRESS.update(
            {
                "status": "running",
                "percent": 2,
                "message": message,
                "phase": phases[0]["id"] if phases else "",
                "phases": _init_phases(phases),
                "log_tail": "",
                "error": None,
                "started_at": _utc_now(),
                "finished_at": None,
                "elapsed_sec": 0,
                "action": action,
                "target": target,
                "result": None,
                "returncode": None,
                "ok": None,
            }
        )
    return None


def _finish(ok: bool, *, message: str, error: Optional[str], rc: int, result: Any) -> None:
    """标记任务结束。"""
    _set_progress(
        status="done" if ok else "error",
        percent=100,
        message=message,
        error=error,
        finished_at=_utc_now(),
        returncode=rc,
        ok=ok,
        result=result,
        elapsed_sec=_elapsed(),
    )


def _local_ssh_password() -> str:
    """
    从 linode.local.json 读取 defaults.ssh.password（不入日志）。

    @returns: 密码或空串
    """
    if not LINODE_LOCAL.is_file():
        return ""
    try:
        cfg = json.loads(LINODE_LOCAL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    ssh = ((cfg or {}).get("defaults") or {}).get("ssh") or {}
    return str(ssh.get("password") or "")


def _find_listed_instance(
    instances: List[Dict[str, Any]], *, label: Optional[str], instance_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    在 list 结果中按 label / id 找实例。

    @param instances: list_instances 的 instances
    @param label: 标签
    @param instance_id: 可选 id
    @returns: 匹配行或 None
    """
    lab = (label or "").strip()
    for row in instances:
        if not isinstance(row, dict):
            continue
        if instance_id is not None and row.get("id") == instance_id:
            return row
        if lab and str(row.get("label") or "") == lab:
            return row
    return None


def _result_from_listed(row: Dict[str, Any], *, root_pass: str = "") -> Dict[str, Any]:
    """
    用 list 行合成 create 成功结果（create HTTP 卡住时的兜底）。

    @param row: 实例摘要
    @param root_pass: 本地配置密码（可空）
    @returns: 与 CLI create JSON 对齐的字典
    """
    ipv4 = str(row.get("ipv4") or "")
    return {
        "ok": True,
        "action": "create",
        "id": row.get("id"),
        "label": row.get("label"),
        "region": row.get("region"),
        "type": row.get("type"),
        "status": row.get("status"),
        "ipv4": ipv4,
        "ipv4_list": [ipv4] if ipv4 else [],
        "root_pass": root_pass,
        "ssh": f"ssh root@{ipv4}" if ipv4 else "",
        "recovered_from_list": True,
    }


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
    if not raw.get("ok") and "instances" not in raw:
        return {
            "ok": False,
            "error": raw.get("error") or "list 失败",
            "stderr_tail": raw.get("stderr_tail"),
            "instances": [],
        }
    instances = raw.get("instances") or []
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
    启动异步销毁（与 ``start_delete`` 相同）。前端应轮询 progress。

    @param instance_id: 实例 ID
    @param label: label
    @param confirm: 必须 True
    @returns: {ok, started|already_running, progress}
    """
    return start_delete(instance_id=instance_id, label=label, confirm=confirm)


def start_delete(
    *,
    instance_id: Optional[int] = None,
    label: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """
    后台销毁实例（须 confirm=True），前端轮询 ``/api/linode/progress``。

    @param instance_id: Linode 实例 ID
    @param label: 实例 label
    @param confirm: 必须为 True
    @returns: {ok, started|already_running, progress}
    """
    global _WORKER

    if not confirm:
        return {"ok": False, "error": "销毁须 confirm=true"}
    iid = int(instance_id) if instance_id is not None else None
    lab = str(label or "").strip() or None
    if iid is None and not lab:
        return {"ok": False, "error": "请提供 instance_id 或 label"}
    if not LINODE_CLI.is_file():
        return {"ok": False, "error": f"找不到 {LINODE_CLI}"}

    target = f"id={iid}" if iid is not None else f"label={lab}"
    busy = _begin_job(
        "delete",
        target,
        [
            {"id": "prepare", "label": "校验参数"},
            {"id": "resolve", "label": "解析实例"},
            {"id": "delete_api", "label": "调用 delete API"},
            {"id": "finalize", "label": "收尾确认"},
        ],
        f"准备销毁 {target}…",
    )
    if busy:
        return busy

    def _worker() -> None:
        """后台销毁。"""
        rc = -1
        try:
            _set_phase("prepare", "running", f"目标 {target}", percent=8)
            _append_log(f"[delete] target={target}")
            _set_phase("prepare", "done", "参数就绪", percent=15)

            _set_phase("resolve", "running", "查询实例…", percent=25)
            args: List[str] = ["delete", "--yes"]
            if iid is not None:
                args.extend(["--id", str(iid)])
            if lab:
                args.extend(["--label", lab])
            _append_log(f"$ python linode_vps.py {' '.join(args)} --json")
            _set_phase("resolve", "done", f"参数已组好（{target}）", percent=35)

            _set_phase("delete_api", "running", "Linode API 删除中…", percent=45)
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
                for line in proc.stderr:
                    _append_log(line)
                    low = line.lower()
                    if "resolv" in low or "found" in low or "label" in low:
                        _set_phase("resolve", "done", line.strip()[:120], percent=40)
                        _set_phase("delete_api", "running", "正在删除…", percent=55)

            err_t = threading.Thread(target=_drain_err, daemon=True)
            err_t.start()
            stdout_data = proc.stdout.read()
            rc = proc.wait(timeout=180)
            err_t.join(timeout=3)

            _set_phase("finalize", "running", "解析删除结果…", percent=85)
            payload = _parse_json_stdout(stdout_data or "")
            ok = bool(payload.get("ok")) and rc == 0
            safe = _redact_payload(payload)
            if ok:
                _set_phase(
                    "resolve",
                    "done",
                    f"id={safe.get('id')} label={safe.get('label')}",
                )
                _set_phase("delete_api", "done", "API 已接受删除", percent=92)
                _set_phase(
                    "finalize",
                    "done",
                    f"已删除 ipv4={safe.get('ipv4') or '—'}",
                    percent=100,
                )
                _append_log(
                    f"deleted id={safe.get('id')} label={safe.get('label')} "
                    f"ipv4={safe.get('ipv4')}"
                )
                _finish(
                    True,
                    message=f"销毁成功 {safe.get('label') or safe.get('id')}",
                    error=None,
                    rc=rc,
                    result=safe,
                )
            else:
                err = payload.get("error") or f"exit={rc}"
                _set_phase("delete_api", "error", str(err)[:200])
                _set_phase("finalize", "error", str(err)[:200])
                _append_log(f"delete failed: {err}")
                _finish(False, message=str(err)[:200], error=str(err), rc=rc, result=safe)
        except Exception as exc:  # noqa: BLE001
            _append_log(f"[error] {exc}")
            _set_phase("finalize", "error", str(exc)[:200])
            _finish(False, message=str(exc)[:200], error=str(exc), rc=rc, result=None)

    _WORKER = threading.Thread(target=_worker, name="ops-linode-delete", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}


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

    @param label: 实例标签
    @param region: 区域
    @param ltype: 机型
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

    label_s = str(label or "").strip() or None
    region_s = str(region or "").strip() or None
    type_s = str(ltype or "").strip() or None
    image_s = str(image or "").strip() or None
    target = label_s or "(defaults.label)"

    if with_jackett:
        phases = [
            {"id": "prepare", "label": "校验配置"},
            {"id": "buy_vps", "label": "购买 Linode"},
            {"id": "wait_ssh", "label": "等待 SSH"},
            {"id": "install_stack", "label": "安装 Docker/Jackett"},
            {"id": "indexers", "label": "配置 indexer"},
            {"id": "sync_key", "label": "同步 API Key"},
            {"id": "finalize", "label": "完成"},
        ]
        action = "provision"
        msg = f"开通 Linode + Jackett（{target}）…"
    else:
        phases = [
            {"id": "prepare", "label": "校验配置"},
            {"id": "api_create", "label": "调用 create API"},
            {"id": "wait_running", "label": "等待实例 running"},
            {"id": "finalize", "label": "解析结果"},
        ]
        action = "create"
        msg = f"开通 Linode（{target}）…"

    busy = _begin_job(action, target, phases, msg)
    if busy:
        return busy

    def _worker() -> None:
        """后台：create 或 provision-linode。"""
        rc = -1
        try:
            _set_phase("prepare", "running", "检查 CLI / 配置…", percent=5)
            _append_log(f"[create] action={action} target={target}")
            if with_jackett:
                _append_log(
                    f"params label={label_s} region={region_s} type={type_s} "
                    f"image={image_s} with_indexers={with_indexers}"
                )
            else:
                _append_log(
                    f"params label={label_s} region={region_s} type={type_s} image={image_s}"
                )
            defaults = load_defaults()
            if not defaults.get("has_token"):
                _append_log("[warn] 未检测到 token（LINODE_TOKEN / linode.local.json）")
            _set_phase(
                "prepare",
                "done",
                f"config={defaults.get('config_path') or '—'} token={'✓' if defaults.get('has_token') else '✗'}",
                percent=12,
            )

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
                _set_phase("buy_vps", "running", "购买实例中…", percent=18)
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
                    if "已存在" in line or "die" in low and "label" in low:
                        _set_phase("buy_vps", "error", line.strip()[:200])
                    elif "create" in low or "购买" in line or "已创建" in line or "linode" in low:
                        _set_phase("buy_vps", "running", line.strip()[:160], percent=28)
                        if "已创建" in line or "ipv4" in low:
                            _set_phase("buy_vps", "done", line.strip()[:160], percent=35)
                    elif "ssh" in low or "wait" in low or "等待" in line:
                        _set_phase("wait_ssh", "running", line.strip()[:160], percent=48)
                    elif "docker" in low:
                        _set_phase("wait_ssh", "done", "SSH 可用", percent=55)
                        _set_phase(
                            "install_stack", "running", line.strip()[:160], percent=62
                        )
                    elif "jackett" in low or "flaresolverr" in low:
                        _set_phase(
                            "install_stack", "running", line.strip()[:160], percent=72
                        )
                    elif "indexer" in low:
                        _set_phase("install_stack", "done", "栈已安装", percent=78)
                        _set_phase("indexers", "running", line.strip()[:160], percent=84)
                    elif "api key" in low or "sync" in low or "accounts" in low:
                        _set_phase("indexers", "done", "indexer 完成", percent=88)
                        _set_phase("sync_key", "running", line.strip()[:160], percent=92)
                    elif "完成" in line or "dashboard" in low:
                        _set_phase("sync_key", "done", "Key 已同步（若启用）", percent=96)
                        _set_phase("finalize", "running", "收尾…", percent=98)
                rc = proc.wait(timeout=3600)
                ok = rc == 0
                if ok:
                    for pid in (
                        "buy_vps",
                        "wait_ssh",
                        "install_stack",
                        "indexers",
                        "sync_key",
                    ):
                        # 未显式 done 的标为 done（跳过已 error）
                        with _PROGRESS_LOCK:
                            for p in _PROGRESS.get("phases") or []:
                                if p.get("id") == pid and p.get("status") in (
                                    "pending",
                                    "running",
                                ):
                                    p["status"] = "done"
                                    p["at"] = _utc_now()
                    _set_phase("finalize", "done", "开通+装机成功", percent=100)
                    _finish(
                        True,
                        message="开通+装机成功",
                        error=None,
                        rc=rc,
                        result={"ok": True, "action": "provision"},
                    )
                else:
                    _set_phase("finalize", "error", f"exit={rc}")
                    _finish(
                        False,
                        message=f"失败 exit={rc}",
                        error=f"exit_code={rc}",
                        rc=rc,
                        result={"ok": False, "action": "provision"},
                    )
                return

            # ── 仅 create ──────────────────────────────────
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
            _set_phase("api_create", "running", "提交 create…", percent=20)
            cmd = [sys.executable, str(LINODE_CLI), *args, "--json"]
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert proc.stdout is not None and proc.stderr is not None

            seen_running_via_list: Optional[Dict[str, Any]] = None
            list_probe_at = 0.0
            # 完整注释：汇总 stderr，finalize 无 JSON 时回填真实错误（如缺 token / SDK）
            stderr_chunks: List[str] = []

            def _drain_err() -> None:
                """流式 stderr → 日志，并推进 wait_running。"""
                for line in proc.stderr:
                    stderr_chunks.append(line)
                    _append_log(line)
                    low = line.lower()
                    if "提交 api" in low or "create:" in low and "api" in low:
                        _set_phase(
                            "api_create", "running", line.strip()[:160], percent=28
                        )
                    if "api 已返回" in low or "已返回 id=" in low:
                        _set_phase(
                            "api_create", "done", line.strip()[:160], percent=42
                        )
                        _set_phase(
                            "wait_running",
                            "running",
                            "等待实例 running…",
                            percent=55,
                        )
                    if "wait_ready" in low or "wait_for_entity_free" in low or "wait_running" in low or "pending" in low or "provision" in low:
                        _set_phase(
                            "api_create", "done", "实例已创建", percent=42
                        )
                        _set_phase(
                            "wait_running",
                            "running",
                            line.strip()[:160] or "等待 Events/status…",
                            percent=60,
                        )
                    if "已 running" in low or "status=running" in low.replace(" ", ""):
                        _set_phase(
                            "wait_running", "done", "实例 running", percent=78
                        )

            err_thread = threading.Thread(target=_drain_err, daemon=True)
            err_thread.start()

            # 心跳 + list 旁路：create HTTP 卡住但控制台已 running 时仍能收尾
            while proc.poll() is None:
                now = time.monotonic()
                _set_progress(elapsed_sec=_elapsed())
                with _PROGRESS_LOCK:
                    cur = _PROGRESS.get("phase")
                if cur == "api_create":
                    _set_progress(
                        message=(
                            f"创建中… 已等待 {_elapsed()}s"
                            f"（若 Linode 控制台已有机器，将自动用 list 确认）"
                        )
                    )
                elif cur == "wait_running":
                    _set_progress(
                        message=f"等待实例 running… 已等待 {_elapsed()}s"
                    )

                # 约每 12s 用 list 探测（list 本身可能较慢）
                if label_s and now - list_probe_at >= 12:
                    list_probe_at = now
                    try:
                        listed = list_instances()
                        row = _find_listed_instance(
                            listed.get("instances") or [], label=label_s
                        )
                    except Exception as probe_exc:  # noqa: BLE001
                        _append_log(f"[probe] list 失败: {probe_exc}")
                        row = None
                    if row:
                        st = str(row.get("status") or "").lower()
                        _append_log(
                            f"[probe] list 命中 id={row.get('id')} "
                            f"status={row.get('status')} ipv4={row.get('ipv4')}"
                        )
                        _set_phase(
                            "api_create",
                            "done",
                            f"控制台已有 id={row.get('id')}",
                            percent=45,
                        )
                        if st == "running":
                            seen_running_via_list = row
                            _set_phase(
                                "wait_running",
                                "done",
                                f"list 确认 running ipv4={row.get('ipv4')}",
                                percent=80,
                            )
                            # create 子进程若仍阻塞在 HTTP，再等一会；超时则终止并 list 收尾
                            if _elapsed() >= 45:
                                _append_log(
                                    "[probe] create 子进程仍未返回，"
                                    "终止并用 list 结果收尾"
                                )
                                try:
                                    proc.terminate()
                                except OSError:
                                    pass
                                try:
                                    proc.wait(timeout=8)
                                except Exception:  # noqa: BLE001
                                    try:
                                        proc.kill()
                                    except OSError:
                                        pass
                                break
                        else:
                            _set_phase(
                                "wait_running",
                                "running",
                                f"list status={row.get('status')}",
                                percent=58,
                            )
                time.sleep(1.5)

            stdout_data = ""
            try:
                stdout_data = proc.stdout.read() or ""
            except Exception:  # noqa: BLE001
                stdout_data = ""
            rc = proc.poll()
            if rc is None:
                try:
                    rc = proc.wait(timeout=5)
                except Exception:  # noqa: BLE001
                    rc = -1
            err_thread.join(timeout=3)

            _set_phase("finalize", "running", "解析结果…", percent=88)
            payload = _parse_json_stdout(stdout_data)
            # 完整注释：stdout 空时把 stderr 拼进 error，避免只显示「CLI 无 JSON 输出」
            if not payload.get("ok") and payload.get("error") == "CLI 无 JSON 输出":
                err_text = "".join(stderr_chunks).strip()
                if err_text:
                    payload = {
                        "ok": False,
                        "error": err_text[-800:],
                        "stderr_tail": err_text[-800:],
                    }
            ok = bool(payload.get("ok")) and rc == 0

            # create HTTP 超时/被杀，但 list 已确认 running → 视为成功
            if (not ok) and seen_running_via_list:
                _append_log(
                    "[recover] CLI 无完整 JSON，使用 list + 本地 ssh 密码合成结果"
                )
                payload = _result_from_listed(
                    seen_running_via_list, root_pass=_local_ssh_password()
                )
                ok = True
                rc = 0

            safe = _redact_payload(payload)
            if ok:
                _set_phase(
                    "api_create",
                    "done",
                    f"id={safe.get('id')} label={safe.get('label')}",
                )
                _set_phase(
                    "wait_running",
                    "done",
                    f"status={safe.get('status')}",
                    percent=92,
                )
                detail = (
                    f"ipv4={safe.get('ipv4')} region={safe.get('region')} "
                    f"type={safe.get('type')}"
                )
                if safe.get("recovered_from_list"):
                    detail += " · recovered_from_list"
                _set_phase("finalize", "done", detail, percent=100)
                _append_log(
                    f"created id={safe.get('id')} label={safe.get('label')} "
                    f"ipv4={safe.get('ipv4')} status={safe.get('status')}"
                )
                _finish(
                    True,
                    message=f"开通成功 ipv4={safe.get('ipv4')}",
                    error=None,
                    rc=rc if rc is not None else 0,
                    result=safe,
                )
            else:
                # 最后再 list 一次：纯超时但机器已在
                if label_s:
                    try:
                        listed = list_instances()
                        row = _find_listed_instance(
                            listed.get("instances") or [], label=label_s
                        )
                        if row and str(row.get("status") or "").lower() == "running":
                            payload = _result_from_listed(
                                row, root_pass=_local_ssh_password()
                            )
                            safe = _redact_payload(payload)
                            _set_phase("api_create", "done", f"id={safe.get('id')}")
                            _set_phase(
                                "wait_running",
                                "done",
                                "list 确认 running",
                                percent=95,
                            )
                            _set_phase(
                                "finalize",
                                "done",
                                f"ipv4={safe.get('ipv4')} · recovered_from_list",
                                percent=100,
                            )
                            _finish(
                                True,
                                message=f"开通成功（list 收尾）ipv4={safe.get('ipv4')}",
                                error=None,
                                rc=0,
                                result=safe,
                            )
                            return
                    except Exception as recover_exc:  # noqa: BLE001
                        _append_log(f"[recover] {recover_exc}")
                err = payload.get("error") or f"exit={rc}"
                _set_phase("finalize", "error", str(err)[:200])
                _append_log(f"create failed: {err}")
                _finish(False, message=str(err)[:200], error=str(err), rc=rc or -1, result=safe)
        except Exception as exc:  # noqa: BLE001
            _append_log(f"[error] {exc}")
            _set_phase("finalize", "error", str(exc)[:200])
            _finish(False, message=str(exc)[:200], error=str(exc), rc=rc, result=None)

    _WORKER = threading.Thread(target=_worker, name="ops-linode-create", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}
