# -*- coding: utf-8 -*-
"""
Ops ③「一键跑生成流程」与单阶段（Pipeline / Generate / Speedtest）后台任务。

@module workflow.ops.generation_flow_service
@description
  start 后后台线程按槽执行所选阶段，UI 轮询 progress 获取 page_id 级状态
  （pipeline / magnet / Rec / status / indexable / generate / speedtest），
  避免长请求卡住与二次点击挂起。
  ``stages`` 可只跑其中一段，供单独按钮复用同一套详细进度。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Sequence

from workflow.ops import actions
from workflow.ops.track_store import load_active_batch, summarize_batch

# 合法阶段名（顺序固定）
_VALID_STAGES: tuple[str, ...] = ("pipeline", "generate", "speedtest")

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
    "stages": list(_VALID_STAGES),
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


def _normalize_stages(stages: Optional[Sequence[str]]) -> List[str]:
    """
    规范化阶段列表；非法名忽略；空则回退全阶段。

    @param stages: 调用方传入的阶段名序列
    @returns: 有序去重后的阶段列表
    """
    if not stages:
        return list(_VALID_STAGES)
    seen: set[str] = set()
    out: List[str] = []
    for raw in stages:
        name = str(raw or "").strip().lower()
        if name in _VALID_STAGES and name not in seen:
            seen.add(name)
            out.append(name)
    return out or list(_VALID_STAGES)


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
        if current_page_id and pid == current_page_id and current_phase in _VALID_STAGES:
            item[current_phase] = "running"
            if not item.get("detail"):
                item["detail"] = f"{current_phase}…"
        out.append(item)
    return out


def _phase_percent(phase_index: int, slot_index: int, total: int, phase_total: int) -> int:
    """
    将 M 阶段 × N 槽映射到 0–100。

    @param phase_index: 当前阶段序号（1-based）
    @param slot_index: 当前槽进度（刚完成第 i 个时传 i+1；开始前传 i）
    @param total: 槽位数
    @param phase_total: 阶段总数
    @returns: 百分比
    """
    if total <= 0 or phase_total <= 0:
        return 0
    # 完整注释：每阶段约占 1/M；阶段内按槽线性
    base = (phase_index - 1) * (100 / phase_total)
    within = (slot_index / total) * (100 / phase_total)
    return int(min(99, max(1, round(base + within))))


def _stage_title(stages: Sequence[str]) -> str:
    """
    人类可读的流程标题。

    @param stages: 阶段列表
    @returns: 标题字符串
    """
    if list(stages) == list(_VALID_STAGES):
        return "一键跑生成流程"
    labels = {
        "pipeline": "Pipeline",
        "generate": "Generate",
        "speedtest": "Speedtest",
    }
    return " → ".join(labels.get(s, s) for s in stages)


def start_generation_flow(
    *,
    fetch: bool = True,
    skip_existing: bool = True,
    mode: str = "live",
    page_ids: Optional[List[str]] = None,
    stages: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    启动生成流程后台任务（可全阶段或单阶段）。

    @param fetch: pipeline 是否拉 Jackett
    @param skip_existing: 跳过已有 ≥2 magnet
    @param mode: live | demo
    @param page_ids: 可选子集；默认活跃批次全部选中槽
    @param stages: 要跑的阶段；默认 pipeline+generate+speedtest
    @returns: { ok, started, already_running?, progress }
    """
    global _WORKER

    stage_list = _normalize_stages(stages)
    title = _stage_title(stage_list)
    phase_total = len(stage_list)

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
    first_phase = stage_list[0]
    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": first_phase,
                "percent": 1,
                "message": f"准备 {title}：共 {len(ids)} 槽 · {phase_total} 阶段",
                "current_page_id": None,
                "current_index": 0,
                "total": len(ids),
                "phase_index": 1,
                "phase_total": phase_total,
                "stages": list(stage_list),
                "slots": initial_slots,
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "summary": summarize_batch(batch),
                "batch_id": batch_id,
                "title": title,
            }
        )

    def _worker() -> None:
        """
        后台：按 stages 顺序逐槽执行，并刷新 progress.slots。
        """
        last_batch: Optional[Dict[str, Any]] = batch
        try:
            for phase_i, phase_name in enumerate(stage_list, start=1):
                for i, pid in enumerate(ids):
                    _set_progress(
                        phase=phase_name,
                        phase_index=phase_i,
                        current_page_id=pid,
                        current_index=i + 1,
                        percent=_phase_percent(phase_i, i, len(ids), phase_total),
                        message=f"{phase_name} {i + 1}/{len(ids)} · {pid}",
                        slots=_sync_slots_from_batch(
                            last_batch,
                            ids,
                            current_page_id=pid,
                            current_phase=phase_name,
                        ),
                    )
                    if phase_name == "pipeline":
                        result = actions.run_pipeline(
                            batch_id=batch_id,
                            page_ids=[pid],
                            fetch=fetch,
                            skip_existing=skip_existing,
                            mode=mode,
                        )
                    elif phase_name == "generate":
                        result = actions.run_generate(
                            batch_id=batch_id,
                            page_ids=[pid],
                            generate_all=False,
                        )
                    else:
                        result = actions.run_speedtest(
                            batch_id=batch_id,
                            page_ids=[pid],
                        )
                    # 完整注释：单槽失败不整批中止，继续后续槽
                    if not result.get("ok") and result.get("error"):
                        pass
                    last_batch = result.get("batch") or last_batch
                    _set_progress(
                        percent=_phase_percent(phase_i, i + 1, len(ids), phase_total),
                        slots=_sync_slots_from_batch(last_batch, ids),
                        summary=result.get("summary")
                        or summarize_batch(last_batch or {}),
                        message=f"{phase_name} 完成 {i + 1}/{len(ids)} · {pid}",
                    )

            _set_progress(
                status="done",
                phase="done",
                phase_index=phase_total,
                percent=100,
                current_page_id=None,
                message=f"{title}完成：共 {len(ids)} 槽",
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

    thread_name = "ops-generation-flow-" + "-".join(stage_list)
    _WORKER = threading.Thread(target=_worker, name=thread_name, daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}


def start_pipeline_flow(
    *,
    fetch: bool = True,
    skip_existing: bool = True,
    mode: str = "live",
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    仅跑 Pipeline 阶段（详细分槽进度）。

    @param fetch: 是否拉 Jackett
    @param skip_existing: 跳过已有 ≥2 magnet
    @param mode: live | demo
    @param page_ids: 可选子集
    @returns: start_generation_flow 结果
    """
    return start_generation_flow(
        fetch=fetch,
        skip_existing=skip_existing,
        mode=mode,
        page_ids=page_ids,
        stages=["pipeline"],
    )


def start_generate_flow(
    *,
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    仅跑 Generate 选中页（详细分槽进度）。

    @param page_ids: 可选子集
    @returns: start_generation_flow 结果
    """
    return start_generation_flow(page_ids=page_ids, stages=["generate"])


def start_speedtest_flow(
    *,
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    仅跑 Speedtest（详细分槽进度）。

    @param page_ids: 可选子集
    @returns: start_generation_flow 结果
    """
    return start_generation_flow(page_ids=page_ids, stages=["speedtest"])


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
                "stages": list(_VALID_STAGES),
                "slots": [],
                "error": None,
                "started_at": None,
                "finished_at": None,
                "ok": None,
                "summary": None,
            }
        )
        _WORKER = None
