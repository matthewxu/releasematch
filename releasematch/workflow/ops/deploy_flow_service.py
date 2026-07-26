# -*- coding: utf-8 -*-
"""
Ops ④「执行 Deploy」后台任务：prepare + 可选 wrangler，分阶段进度轮询。

@module workflow.ops.deploy_flow_service
@description
  全量 generate all + wrangler 可能数十分钟；同步 POST 无明细、易像挂起。
  start 后后台推进，UI 轮询 progress（phase / steps / 当前 page_id / 日志尾）。
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT
from workflow.ops.track_store import (
    load_active_batch,
    save_batch,
    summarize_batch,
    update_batch_step,
)

# idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "phase": "",
    "percent": 0,
    "message": "",
    "scope": None,
    "upload": None,
    "current_page_id": None,
    "page_index": 0,
    "page_total": 0,
    "steps": [],
    "log_tail": "",
    "error": None,
    "started_at": None,
    "finished_at": None,
    "ok": None,
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None


def _set_progress(**kwargs: Any) -> None:
    """合并更新进度字典。"""
    with _PROGRESS_LOCK:
        _PROGRESS.update(kwargs)


def get_progress() -> Dict[str, Any]:
    """返回 Deploy 进度快照。"""
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _set_step(steps: List[Dict[str, Any]], step_id: str, status: str, detail: str = "") -> None:
    """
    更新或追加步骤行。

    @param steps: 步骤列表（原地改）
    @param step_id: prepare_full | prepare_incr | wrangler | …
    @param status: pending | running | ok | failed | skipped
    @param detail: 短说明
    """
    for row in steps:
        if row.get("id") == step_id:
            row["status"] = status
            if detail:
                row["detail"] = detail[:200]
            return
    steps.append({"id": step_id, "status": status, "detail": detail[:200]})


def start_deploy(
    *,
    scope: str = "full",
    upload: bool = False,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    启动 Deploy 后台任务。

    @param scope: full | incremental | upload_only
    @param upload: 是否 wrangler 上传公网
    @param batch_id: 批次（可选）
    @param page_ids: 增量子集
    @returns: { ok, started, already_running?, progress }
    """
    global _WORKER

    with _PROGRESS_LOCK:
        if _PROGRESS.get("status") == "running" and _WORKER and _WORKER.is_alive():
            return {
                "ok": True,
                "started": False,
                "already_running": True,
                "progress": dict(_PROGRESS),
            }

    scope_norm = str(scope or "full").strip().lower()
    if scope_norm in ("selected", "pages", "incr"):
        scope_norm = "incremental"
    if scope_norm not in ("full", "incremental", "upload_only"):
        return {"ok": False, "error": f"未知 scope={scope!r}"}

    batch = load_active_batch()
    if not batch:
        return {"ok": False, "error": "无活跃跟踪批次；请先在「筛选」导入"}

    from workflow.ops import actions

    if scope_norm == "incremental":
        rows = actions._selected_slots(batch, page_ids)  # noqa: SLF001
        if not rows:
            return {"ok": False, "error": "增量 deploy 需要至少 1 个选中槽"}

    steps: List[Dict[str, Any]] = []
    if scope_norm == "full":
        _set_step(steps, "prepare_full", "pending", "generate all")
    elif scope_norm == "incremental":
        _set_step(steps, "prepare_incr", "pending", "选中槽 + home/sitemap")
    else:
        _set_step(steps, "prepare", "skipped", "upload_only")
    if upload:
        _set_step(steps, "wrangler", "pending", "wrangler deploy 公网")
    else:
        _set_step(steps, "wrangler", "skipped", "未勾选正式上传")

    update_batch_step(
        batch,
        "deploy",
        status="running",
        detail=f"scope={scope_norm} upload={upload}",
    )
    save_batch(batch)

    bid = str((batch.get("meta") or {}).get("batch_id") or batch_id or "")

    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": "starting",
                "percent": 1,
                "message": f"Deploy 启动 · scope={scope_norm} upload={upload}",
                "scope": scope_norm,
                "upload": upload,
                "current_page_id": None,
                "page_index": 0,
                "page_total": 0,
                "steps": list(steps),
                "log_tail": "",
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "batch_id": bid,
            }
        )

    def _worker() -> None:
        """后台：prepare → wrangler。"""
        nonlocal steps
        prepare_result: Dict[str, Any] = {"skipped": True}
        wrangler_result: Dict[str, Any] = {"skipped": True}
        active = batch

        try:
            if scope_norm == "full":
                _set_step(steps, "prepare_full", "running", "generate all…")
                _set_progress(
                    phase="prepare_full",
                    percent=5,
                    message="全量 generate all…",
                    steps=list(steps),
                )

                from workflow.ops.generate_reload import reload_generate_modules

                reload_info = reload_generate_modules()
                if not reload_info.get("ok"):
                    raise RuntimeError(
                        "模块热重载失败: " + "; ".join(reload_info.get("errors") or [])
                    )
                # reload 后再 import，拿到新 generate_one 绑定
                from portal.generator.generate_one import write_all_published

                def on_page(index: int, total: int, page_id: str, result: Dict[str, Any]) -> None:
                    """逐页进度。"""
                    # prepare 占 5–75%
                    pct = 5 + int(70 * (index / max(total, 1)))
                    _set_progress(
                        phase="prepare_full",
                        percent=min(75, pct),
                        current_page_id=page_id,
                        page_index=index,
                        page_total=total,
                        message=f"Generate {index}/{total} · {page_id}",
                        steps=list(steps),
                    )

                prepare_raw = write_all_published(on_page=on_page)
                if isinstance(prepare_raw, dict) and prepare_raw.get("ok") is False:
                    raise RuntimeError(
                        "; ".join(prepare_raw.get("errors") or [])
                        or prepare_raw.get("error")
                        or "全量 prepare 失败"
                    )
                prepare_result = {"ok": True, "mode": "full", "result": prepare_raw}
                gen_n = (prepare_raw or {}).get("generated")
                _set_step(
                    steps,
                    "prepare_full",
                    "ok",
                    f"generated={gen_n} / {(prepare_raw or {}).get('count')}",
                )
                _set_progress(
                    percent=78,
                    message="全量 prepare 完成（home/hub/sitemap 已写入）",
                    current_page_id=None,
                    steps=list(steps),
                )

            elif scope_norm == "incremental":
                _set_step(steps, "prepare_incr", "running", "增量 bake…")
                _set_progress(
                    phase="prepare_incr",
                    percent=10,
                    message="增量 prepare（选中槽）…",
                    steps=list(steps),
                )
                prepare_result = actions._prepare_dist_incremental(  # noqa: SLF001
                    batch_id=bid,
                    page_ids=page_ids,
                )
                if not prepare_result.get("ok"):
                    raise RuntimeError(prepare_result.get("error") or "增量 prepare 失败")
                g = prepare_result.get("generate") or {}
                _set_step(
                    steps,
                    "prepare_incr",
                    "ok",
                    f"ok={g.get('ok_count')} fail={g.get('fail_count')}",
                )
                reloaded = actions._get_batch(bid)  # noqa: SLF001
                if reloaded.get("ok"):
                    active = reloaded["batch"]
                _set_progress(percent=78, message="增量 prepare 完成", steps=list(steps))

            if upload:
                _set_step(steps, "wrangler", "running", "wrangler deploy…")
                _set_progress(
                    phase="wrangler",
                    percent=80,
                    message="wrangler deploy（公网上传）…",
                    steps=list(steps),
                    log_tail="",
                )
                wrangler_result = _run_wrangler_streaming(steps)
                if not wrangler_result.get("ok"):
                    raise RuntimeError(
                        wrangler_result.get("error")
                        or wrangler_result.get("detail")
                        or "wrangler deploy 失败"
                    )
                _set_step(steps, "wrangler", "ok", "upload ok")
            else:
                _set_step(steps, "wrangler", "skipped", "未勾选正式上传（仅本地 dist）")

            detail_parts = [f"scope={scope_norm}", f"upload={upload}"]
            if scope_norm == "full":
                detail_parts.append("prepare=full")
            elif scope_norm == "incremental":
                g = prepare_result.get("generate") or {}
                detail_parts.append(
                    f"prepare=incr ok={g.get('ok_count')} fail={g.get('fail_count')}"
                )
            else:
                detail_parts.append("prepare=skip")
            if upload:
                detail_parts.append("wrangler=ok")
            detail = " | ".join(detail_parts)
            if upload and wrangler_result.get("detail"):
                detail = (detail + "\n" + str(wrangler_result.get("detail")))[-500:]

            update_batch_step(active, "deploy", status="ok", detail=detail)
            save_batch(active)
            _set_progress(
                status="done",
                phase="done",
                percent=100,
                message=detail.split("\n")[0],
                steps=list(steps),
                ok=True,
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                log_tail=(wrangler_result.get("detail") or "")[-800:],
                summary=summarize_batch(active),
            )
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            for row in steps:
                if row.get("status") == "running":
                    row["status"] = "failed"
                    row["detail"] = err[:200]
            update_batch_step(active, "deploy", status="failed", detail=err[:500])
            save_batch(active)
            _set_progress(
                status="error",
                percent=100,
                message=err[:200],
                error=err,
                ok=False,
                steps=list(steps),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

    def _run_wrangler_streaming(steps_ref: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        流式跑 wrangler，刷新 log_tail。

        @param steps_ref: 步骤表
        @returns: ok / detail / returncode
        """
        if not shutil.which("wrangler"):
            return {"ok": False, "error": "未找到 wrangler，请 npm i -g wrangler"}

        proc = subprocess.Popen(
            ["wrangler", "deploy"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        lines: List[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip())
            tail = "\n".join(lines[-40:])
            _set_progress(
                phase="wrangler",
                percent=min(98, 80 + min(18, len(lines) // 2)),
                message=line.strip()[:120] or "wrangler…",
                log_tail=tail[-1200:],
                steps=list(steps_ref),
            )
        code = proc.wait(timeout=1800)
        detail = "\n".join(lines)[-1200:]
        return {"ok": code == 0, "returncode": code, "detail": detail}

    _WORKER = threading.Thread(target=_worker, name="ops-deploy-flow", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}


def run_deploy_blocking(
    *,
    scope: str = "full",
    upload: bool = False,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
    timeout_sec: float = 3600.0,
) -> Dict[str, Any]:
    """
    同步等待 Deploy（兼容旧 POST /api/actions/deploy）。

    @returns: 与 actions.run_deploy 相近的结果
    """
    start = start_deploy(
        scope=scope, upload=upload, batch_id=batch_id, page_ids=page_ids
    )
    if not start.get("ok") and not start.get("already_running"):
        return start
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        prog = get_progress()
        if prog.get("status") in ("done", "error"):
            batch = load_active_batch()
            return {
                "ok": bool(prog.get("ok")),
                "error": prog.get("error"),
                "scope": prog.get("scope"),
                "upload": prog.get("upload"),
                "prepare_only": not bool(prog.get("upload")),
                "progress": prog,
                "summary": prog.get("summary") or (summarize_batch(batch) if batch else None),
                "batch": batch,
            }
        time.sleep(0.5)
    return {"ok": False, "error": "deploy 超时", "progress": get_progress()}


def _reset_for_tests() -> None:
    """测试用复位。"""
    global _WORKER
    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "idle",
                "phase": "",
                "percent": 0,
                "message": "",
                "scope": None,
                "upload": None,
                "current_page_id": None,
                "page_index": 0,
                "page_total": 0,
                "steps": [],
                "log_tail": "",
                "error": None,
                "started_at": None,
                "finished_at": None,
                "ok": None,
            }
        )
        _WORKER = None
