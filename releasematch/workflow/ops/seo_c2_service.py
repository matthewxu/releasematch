# -*- coding: utf-8 -*-
"""
Ops ④「跑 seo_c2_checklist」后台任务：按检查项推进并供 UI 轮询。

@module workflow.ops.seo_c2_service
@description
  start 后后台线程调用 ``scripts.seo_c2_checklist.run_checks``，每完成一项
  更新 progress.checks（check_id / title / status / detail / section），
  避免长同步 POST 无明细、二次点击挂起。
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT, SITE_ORIGIN
from workflow.ops.track_store import load_active_batch, save_batch, update_batch_step

# 进度：idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "phase": "",
    "percent": 0,
    "message": "",
    "current_check_id": None,
    "current_index": 0,
    "total_estimate": 20,
    "checks": [],
    "error": None,
    "started_at": None,
    "finished_at": None,
    "ok": None,
    "summary": None,
    "report": None,
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None

# 经验项数（用于百分比；实际可能略多/略少）
_ESTIMATED_CHECKS: int = 22


def _set_progress(**kwargs: Any) -> None:
    """
    合并更新进度。

    @param kwargs: 覆盖字段
    """
    with _PROGRESS_LOCK:
        _PROGRESS.update(kwargs)


def get_progress() -> Dict[str, Any]:
    """
    返回 seo_c2 进度快照。

    @returns: status / checks / percent / …
    """
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _item_row(item: Any) -> Dict[str, Any]:
    """
    CheckItem → 前端行。

    @param item: CheckItem 或 dict
    @returns: 行字典
    """
    if hasattr(item, "check_id"):
        data = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item)
    else:
        data = dict(item)
    return {
        "section": str(data.get("section") or ""),
        "check_id": str(data.get("check_id") or ""),
        "title": str(data.get("title") or ""),
        "status": str(data.get("status") or "pending"),
        "detail": str(data.get("detail") or "")[:200],
    }


def start_seo_c2(*, batch_id: Optional[str] = None, use_db: bool = True) -> Dict[str, Any]:
    """
    启动 seo_c2 后台检查。

    @param batch_id: 可选批次（有则回写 batch_steps.seo_c2）
    @param use_db: 是否 MySQL 交叉验证
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

    batch = load_active_batch()
    if batch_id and batch:
        active_id = str((batch.get("meta") or {}).get("batch_id") or "")
        if active_id and active_id != str(batch_id):
            # 请求指定了其它批次：仍回写活跃批（Ops UI 只操作活跃批）
            pass

    if batch:
        update_batch_step(batch, "seo_c2", status="running", detail="")
        save_batch(batch)

    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": "6.1",
                "percent": 1,
                "message": "准备 seo_c2_checklist…",
                "current_check_id": None,
                "current_index": 0,
                "total_estimate": _ESTIMATED_CHECKS,
                "checks": [],
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "summary": None,
                "report": None,
                "batch_id": str((batch or {}).get("meta", {}).get("batch_id") or "")
                if batch
                else None,
            }
        )

    def _worker() -> None:
        """后台：run_checks + 逐项 progress。"""
        import importlib.util
        import io
        import sys
        from contextlib import redirect_stdout

        checks_acc: List[Dict[str, Any]] = []

        def on_item(item: Any) -> None:
            """单项完成时刷新进度。"""
            row = _item_row(item)
            checks_acc.append(row)
            n = len(checks_acc)
            section = row.get("section") or ""
            pct = int(min(99, max(2, round(100 * n / _ESTIMATED_CHECKS))))
            _set_progress(
                phase=section or "check",
                current_check_id=row.get("check_id"),
                current_index=n,
                percent=pct,
                message=f"§{section} · {row.get('check_id')} · {row.get('status')}",
                checks=list(checks_acc),
            )

        try:
            checklist_path = PROJECT_ROOT / "scripts" / "seo_c2_checklist.py"
            if not checklist_path.is_file():
                raise FileNotFoundError(f"找不到 {checklist_path}")
            spec = importlib.util.spec_from_file_location("seo_c2_checklist", checklist_path)
            if spec is None or spec.loader is None:
                raise ImportError("无法加载 seo_c2_checklist")
            mod = importlib.util.module_from_spec(spec)
            # 完整注释：dataclass 需要模块已登记在 sys.modules
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)

            dist_root = Path(mod.DEFAULT_DIST)
            _set_progress(message=f"检查 dist={dist_root}", percent=2)
            report = mod.run_checks(
                dist_root,
                SITE_ORIGIN,
                use_db=use_db,
                on_item=on_item,
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                mod.print_report(report)
            text_detail = buf.getvalue()[-800:]

            ok = report.fail_count == 0
            summary = {
                "pass": report.pass_count,
                "fail": report.fail_count,
                "warn": report.warn_count,
                "skip": sum(1 for i in report.items if i.status == "skip"),
            }
            _set_progress(
                status="done",
                phase="done",
                percent=100,
                current_check_id=None,
                message=(
                    f"seo_c2 完成：pass={summary['pass']} fail={summary['fail']} "
                    f"warn={summary['warn']} skip={summary['skip']}"
                ),
                checks=list(checks_acc),
                summary=summary,
                report=report.to_dict(),
                ok=ok,
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            if batch:
                update_batch_step(
                    batch,
                    "seo_c2",
                    status="ok" if ok else "failed",
                    detail=text_detail[-500:],
                )
                save_batch(batch)
        except Exception as exc:  # noqa: BLE001
            _set_progress(
                status="error",
                percent=100,
                message=str(exc)[:200],
                error=str(exc),
                ok=False,
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                checks=list(checks_acc),
            )
            if batch:
                update_batch_step(batch, "seo_c2", status="failed", detail=str(exc)[:500])
                save_batch(batch)

    _WORKER = threading.Thread(target=_worker, name="ops-seo-c2", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}


def run_seo_c2_blocking(
    *,
    batch_id: Optional[str] = None,
    use_db: bool = True,
    timeout_sec: float = 600.0,
) -> Dict[str, Any]:
    """
    同步等待后台 seo_c2 结束（兼容旧 POST /api/actions/seo）。

    @param batch_id: 批次
    @param use_db: MySQL 交叉验证
    @param timeout_sec: 超时秒数
    @returns: 与旧 run_seo_c2 相近的结果字典
    """
    start = start_seo_c2(batch_id=batch_id, use_db=use_db)
    if start.get("already_running"):
        # 附着等待已有任务
        pass
    elif not start.get("ok"):
        return start

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        prog = get_progress()
        if prog.get("status") in ("done", "error"):
            batch = load_active_batch()
            return {
                "ok": bool(prog.get("ok")),
                "detail": prog.get("message"),
                "summary_counts": prog.get("summary"),
                "progress": prog,
                "batch": batch,
                "returncode": 0 if prog.get("ok") else 1,
            }
        time.sleep(0.4)
    return {"ok": False, "error": "seo_c2 超时", "progress": get_progress()}


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
                "current_check_id": None,
                "current_index": 0,
                "total_estimate": _ESTIMATED_CHECKS,
                "checks": [],
                "error": None,
                "started_at": None,
                "finished_at": None,
                "ok": None,
                "summary": None,
                "report": None,
            }
        )
        _WORKER = None
