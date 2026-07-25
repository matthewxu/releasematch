# -*- coding: utf-8 -*-
"""
Ops ③「一键跑生成流程」后台任务：按槽推进 pipeline → generate → speedtest。

@module workflow.ops.generation_flow_service
@description
  与 Jackett 一键部署类似：start 后后台线程逐槽执行，UI 轮询 progress
  获取 page_id 级状态（pipeline / magnet / Rec / status / indexable /
  generate / speedtest），避免长请求卡住与二次点击挂起。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from workflow.ops import actions
from workflow.ops.track_store import load_active_batch, summarize_batch

# 进度状态：idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "phase": "",
    "percent": 0,
    "message": "",
    "current_page_id": None,
    "current_index": 0,
    "total": 0,
    "phase_index": 0,
    "phase_total": 3,
    "slots": [],
    "error": None,
    "started_at": None,
    "finished_at": None,
    "ok": None,
    "summary": None,
}
_PROGRESS_LOCK = threading.Lock()
_WORKER: Optional[threading.Thread] = None


def _set_progress(**kwargs: Any) -> None:
    """
    合并更新进度字典。

    @param kwargs: 要覆盖的字段
    """
    with _PROGRESS_LOCK:
        _PROGRESS.update(kwargs)


def get_progress() -> Dict[str, Any]:
    """
    返回当前生成流程进度快照。

    @returns: status / phase / slots / percent / …
    """
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _slot_row_from_track(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    把跟踪表槽位压成 progress.slots 行。

    @param row: track slot
    @returns: 前端明细行
    """
    gate = row.get("gate") or {}
    stages = row.get("stages") or {}
    pipe = stages.get("pipeline") or {}
    gen = stages.get("generate") or {}
    speed = stages.get("speedtest") or {}

    # 完整注释：detail 优先最新已推进阶段，避免旧 pipeline 错误盖住 generate/speedtest 成功
    def _stage_detail(stage: Dict[str, Any]) -> str:
        st = str(stage.get("status") or "pending")
        if st in ("pending", ""):
            return ""
        return str(stage.get("detail") or st)

    detail = (
        _stage_detail(speed)
        or _stage_detail(gen)
        or _stage_detail(pipe)
        or str(row.get("error") or "")
    )
    return {
        "page_id": str(row.get("page_id") or ""),
        "label": str(row.get("label") or row.get("title") or ""),
        "pipeline": str(pipe.get("status") or "pending"),
        "magnet_count": gate.get("magnet_count"),
        "has_recommended": gate.get("has_recommended"),
        "page_status": gate.get("page_status"),
        "indexable": gate.get("indexable"),
        "generate": str(gen.get("status") or "pending"),
        "speedtest": str(speed.get("status") or "pending"),
        "detail": detail[:120],
    }


def _sync_slots_from_batch(
    batch: Optional[Dict[str, Any]],
    page_ids: List[str],
    *,
    current_page_id: Optional[str] = None,
    current_phase: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    按 page_ids 顺序从批次提取 progress 行。

    @param batch: 跟踪批次
    @param page_ids: 选中顺序
    @param current_page_id: 正在处理的 page_id（该行对应阶段标为 running）
    @param current_phase: pipeline | generate | speedtest
    @returns: slots 列表
    """
    by_id = {}
    if batch:
        for row in batch.get("slots") or []:
            by_id[str(row.get("page_id"))] = row
    out: List[Dict[str, Any]] = []
    for pid in page_ids:
        row = by_id.get(pid)
        if row:
            item = _slot_row_from_track(row)
        else:
            item = {
                "page_id": pid,
                "label": "",
                "pipeline": "pending",
                "magnet_count": None,
                "has_recommended": None,
                "page_status": None,
                "indexable": None,
                "generate": "pending",
                "speedtest": "pending",
                "detail": "",
            }
        # 当前槽对应阶段显示 running，便于 UI 高亮
        if current_page_id and pid == current_page_id and current_phase in (
            "pipeline",
            "generate",
            "speedtest",
        ):
            item[current_phase] = "running"
            if not item.get("detail"):
                item["detail"] = f"{current_phase}…"
        out.append(item)
    return out


def _phase_percent(phase_index: int, slot_index: int, total: int) -> int:
    """
    将 3 阶段 × N 槽映射到 0–100。

    @param phase_index: 1=pipeline 2=generate 3=speedtest
    @param slot_index: 当前槽 0-based（刚完成第 i 个时传 i+1）
    @param total: 槽位数
    @returns: 百分比
    """
    if total <= 0:
        return 0
    # 每阶段约占 1/3；阶段内按槽线性
    base = (phase_index - 1) * (100 / 3)
    within = (slot_index / total) * (100 / 3)
    return int(min(99, max(1, round(base + within))))


def start_generation_flow(
    *,
    fetch: bool = True,
    skip_existing: bool = True,
    mode: str = "live",
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    启动一键生成流程后台任务。

    @param fetch: pipeline 是否拉 Jackett
    @param skip_existing: 跳过已有 ≥2 magnet
    @param mode: live | demo
    @param page_ids: 可选子集；默认活跃批次全部选中槽
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
    if not batch:
        return {"ok": False, "error": "无活跃跟踪批次；请先在「筛选」导入"}

    rows = actions._selected_slots(batch, page_ids)  # noqa: SLF001 — 同包复用选中逻辑
    if not rows:
        return {"ok": False, "error": "无选中槽位"}

    ids = [str(r["page_id"]) for r in rows]
    batch_id = str((batch.get("meta") or {}).get("batch_id") or "")

    initial_slots = _sync_slots_from_batch(batch, ids)
    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": "pipeline",
                "percent": 1,
                "message": f"准备 Pipeline：共 {len(ids)} 槽",
                "current_page_id": None,
                "current_index": 0,
                "total": len(ids),
                "phase_index": 1,
                "phase_total": 3,
                "slots": initial_slots,
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "summary": summarize_batch(batch),
                "batch_id": batch_id,
            }
        )

    def _worker() -> None:
        """后台：逐槽 pipeline → generate → speedtest，并刷新 progress.slots。"""
        last_batch: Optional[Dict[str, Any]] = batch
        try:
            # ── 1/3 Pipeline ─────────────────────────────────
            for i, pid in enumerate(ids):
                _set_progress(
                    phase="pipeline",
                    phase_index=1,
                    current_page_id=pid,
                    current_index=i + 1,
                    percent=_phase_percent(1, i, len(ids)),
                    message=f"Pipeline {i + 1}/{len(ids)} · {pid}",
                    slots=_sync_slots_from_batch(
                        last_batch, ids, current_page_id=pid, current_phase="pipeline"
                    ),
                )
                result = actions.run_pipeline(
                    batch_id=batch_id,
                    page_ids=[pid],
                    fetch=fetch,
                    skip_existing=skip_existing,
                    mode=mode,
                )
                if not result.get("ok") and result.get("error"):
                    # 单槽失败不整批中止，继续后续槽
                    pass
                last_batch = result.get("batch") or last_batch
                _set_progress(
                    percent=_phase_percent(1, i + 1, len(ids)),
                    slots=_sync_slots_from_batch(last_batch, ids),
                    summary=result.get("summary") or summarize_batch(last_batch or {}),
                    message=f"Pipeline 完成 {i + 1}/{len(ids)} · {pid}",
                )

            # ── 2/3 Generate ─────────────────────────────────
            for i, pid in enumerate(ids):
                _set_progress(
                    phase="generate",
                    phase_index=2,
                    current_page_id=pid,
                    current_index=i + 1,
                    percent=_phase_percent(2, i, len(ids)),
                    message=f"Generate {i + 1}/{len(ids)} · {pid}",
                    slots=_sync_slots_from_batch(
                        last_batch, ids, current_page_id=pid, current_phase="generate"
                    ),
                )
                result = actions.run_generate(
                    batch_id=batch_id,
                    page_ids=[pid],
                    generate_all=False,
                )
                last_batch = result.get("batch") or last_batch
                _set_progress(
                    percent=_phase_percent(2, i + 1, len(ids)),
                    slots=_sync_slots_from_batch(last_batch, ids),
                    summary=result.get("summary") or summarize_batch(last_batch or {}),
                    message=f"Generate 完成 {i + 1}/{len(ids)} · {pid}",
                )

            # ── 3/3 Speedtest ────────────────────────────────
            for i, pid in enumerate(ids):
                _set_progress(
                    phase="speedtest",
                    phase_index=3,
                    current_page_id=pid,
                    current_index=i + 1,
                    percent=_phase_percent(3, i, len(ids)),
                    message=f"Speedtest {i + 1}/{len(ids)} · {pid}",
                    slots=_sync_slots_from_batch(
                        last_batch, ids, current_page_id=pid, current_phase="speedtest"
                    ),
                )
                result = actions.run_speedtest(batch_id=batch_id, page_ids=[pid])
                last_batch = result.get("batch") or last_batch
                _set_progress(
                    percent=_phase_percent(3, i + 1, len(ids)),
                    slots=_sync_slots_from_batch(last_batch, ids),
                    summary=result.get("summary") or summarize_batch(last_batch or {}),
                    message=f"Speedtest 完成 {i + 1}/{len(ids)} · {pid}",
                )

            _set_progress(
                status="done",
                phase="done",
                phase_index=3,
                percent=100,
                current_page_id=None,
                message=f"一键流程完成：共 {len(ids)} 槽",
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ok=True,
                slots=_sync_slots_from_batch(last_batch, ids),
                summary=summarize_batch(last_batch or {}),
            )
        except Exception as exc:  # noqa: BLE001
            _set_progress(
                status="error",
                percent=100,
                message=str(exc)[:200],
                error=str(exc),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ok=False,
                slots=_sync_slots_from_batch(last_batch, ids),
            )

    _WORKER = threading.Thread(target=_worker, name="ops-generation-flow", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}


def _reset_for_tests() -> None:
    """
    测试用：清空进度与 worker 引用（勿在生产路径调用）。
    """
    global _WORKER
    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "idle",
                "phase": "",
                "percent": 0,
                "message": "",
                "current_page_id": None,
                "current_index": 0,
                "total": 0,
                "phase_index": 0,
                "phase_total": 3,
                "slots": [],
                "error": None,
                "started_at": None,
                "finished_at": None,
                "ok": None,
                "summary": None,
            }
        )
        _WORKER = None
