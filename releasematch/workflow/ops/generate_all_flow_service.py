# -*- coding: utf-8 -*-
"""
Ops「Generate all」后台任务：分阶段进度 + 模块热重载。

@module workflow.ops.generate_all_flow_service
@description
  同步 POST write_all_published 无 page 级反馈，且长驻进程易用旧代码 bake。
  start 后后台推进；UI 轮询 progress（phase / page_index / page_id / steps / 验收）。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT
from workflow.ops.generate_reload import reload_generate_modules
from workflow.ops.track_store import (
    load_active_batch,
    save_batch,
    summarize_batch,
    update_slot_stage,
)

# idle | running | done | error
_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "phase": "",
    "percent": 0,
    "message": "",
    "current_page_id": None,
    "page_index": 0,
    "page_total": 0,
    "ok_pages": 0,
    "fail_pages": 0,
    "steps": [],
    "recent_pages": [],
    "verify": None,
    "result_summary": None,
    "reload": None,
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
    """返回 Generate all 进度快照。"""
    with _PROGRESS_LOCK:
        return dict(_PROGRESS)


def _set_step(steps: List[Dict[str, Any]], step_id: str, status: str, detail: str = "") -> None:
    """
    更新或追加步骤行。

    @param steps: 步骤列表（原地改）
    @param step_id: reload | ensure_hubs | pages | home | hubs | sitemap | trust | static_shell | verify
    @param status: pending | running | ok | failed | skipped | warn
    @param detail: 短说明
    """
    for row in steps:
        if row.get("id") == step_id:
            row["status"] = status
            if detail:
                row["detail"] = detail[:240]
            return
    steps.append({"id": step_id, "status": status, "detail": detail[:240]})


def _push_recent(recent: List[Dict[str, Any]], page_id: str, ok: bool, detail: str = "") -> None:
    """
    追加最近完成页（最多保留 12 条，供 UI 明细）。

    @param recent: 列表（原地）
    @param page_id: 页面 ID
    @param ok: 是否成功
    @param detail: 输出路径或错误
    """
    recent.append(
        {
            "page_id": page_id,
            "ok": ok,
            "detail": (detail or "")[:160],
        }
    )
    if len(recent) > 12:
        del recent[:-12]


def _verify_magnets_updated_baked(out_root: Path, sample_relpaths: List[str]) -> Dict[str, Any]:
    """
    验收：模板已含源更新标记时，抽样 HTML 也应含 ``rm-badge--updated`` / 卡片更新行。

    @param out_root: portal/dist
    @param sample_relpaths: 相对 dist 的抽样路径
    @returns: verify 摘要
    """
    episode_tpl = (
        PROJECT_ROOT / "portal" / "generator" / "templates" / "episode.html"
    ).read_text(encoding="utf-8", errors="replace")
    home_tpl = (
        PROJECT_ROOT / "portal" / "generator" / "templates" / "home.html"
    ).read_text(encoding="utf-8", errors="replace")
    expects_badge = "rm-badge--updated" in episode_tpl
    expects_home = "rm-show-card__updated" in home_tpl or "magnets_updated_date" in home_tpl

    checked: List[Dict[str, Any]] = []
    badge_hits = 0
    home_hit = False

    for rel in sample_relpaths:
        path = out_root / rel
        if not path.is_file():
            checked.append({"path": rel, "exists": False, "has_badge": False})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        has_badge = "rm-badge--updated" in text or "page.magnets_updated" in text
        if has_badge:
            badge_hits += 1
        checked.append({"path": rel, "exists": True, "has_badge": has_badge})

    index_path = out_root / "index.html"
    if index_path.is_file():
        home_text = index_path.read_text(encoding="utf-8", errors="replace")
        home_hit = "rm-show-card__updated" in home_text or "home.card.updated" in home_text
        checked.append(
            {
                "path": "index.html",
                "exists": True,
                "has_badge": home_hit,
                "kind": "home",
            }
        )

    ok = True
    warnings: List[str] = []
    if expects_badge and badge_hits == 0 and any(c.get("exists") for c in checked if c.get("kind") != "home"):
        ok = False
        warnings.append(
            "模板含 rm-badge--updated，但抽样内容页 HTML 未写入；"
            "多为 Ops 进程未重载代码。请重启 ops serve 后重跑 Generate all。"
        )
    if expects_home and index_path.is_file() and not home_hit:
        ok = False
        warnings.append("首页未写入源更新时间字段（rm-show-card__updated / home.card.updated）。")

    return {
        "ok": ok,
        "expects_badge": expects_badge,
        "expects_home": expects_home,
        "badge_hits": badge_hits,
        "home_hit": home_hit,
        "checked": checked,
        "warnings": warnings,
    }


def start_generate_all(*, batch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    启动 Generate all 后台任务。

    @param batch_id: 可选；用于回写跟踪槽 generate 阶段
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
    bid = str(
        batch_id
        or ((batch or {}).get("meta") or {}).get("batch_id")
        or ""
    )

    steps: List[Dict[str, Any]] = []
    for sid, detail in (
        ("reload", "热重载生成模块"),
        ("reconcile_magnets", "对齐 magnet_count 与实有资源"),
        ("ensure_hubs", "补齐缺失 Hub"),
        ("pages", "烘焙 episode/movie"),
        ("home", "首页目录"),
        ("hubs", "show_hub 页"),
        ("sitemap", "sitemap"),
        ("trust", "Trust 页"),
        ("static_shell", "同步 static 壳"),
        ("verify", "抽样验收源更新时间"),
    ):
        _set_step(steps, sid, "pending", detail)

    with _PROGRESS_LOCK:
        _PROGRESS.update(
            {
                "status": "running",
                "phase": "starting",
                "percent": 1,
                "message": "Generate all 启动…",
                "current_page_id": None,
                "page_index": 0,
                "page_total": 0,
                "ok_pages": 0,
                "fail_pages": 0,
                "steps": list(steps),
                "recent_pages": [],
                "verify": None,
                "result_summary": None,
                "reload": None,
                "error": None,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_at": None,
                "ok": None,
                "batch_id": bid,
            }
        )

    def _worker() -> None:
        """后台：reload → write_all_published（分阶段进度）→ 验收。"""
        nonlocal steps
        recent: List[Dict[str, Any]] = []
        ok_pages = 0
        fail_pages = 0

        try:
            _set_step(steps, "reload", "running", "importlib.reload…")
            _set_progress(
                phase="reload",
                percent=3,
                message="热重载生成模块（避免长驻进程用旧代码）…",
                steps=list(steps),
            )
            reload_info = reload_generate_modules()
            if not reload_info.get("ok"):
                raise RuntimeError(
                    "模块热重载失败: " + "; ".join(reload_info.get("errors") or [])
                )
            _set_step(
                steps,
                "reload",
                "ok",
                f"reloaded={len(reload_info.get('reloaded') or [])}",
            )
            _set_progress(reload=reload_info, steps=list(steps))

            # 必须在 reload 之后再 import，拿到新模块绑定
            from portal.generator.generate_one import DEFAULT_OUT_ROOT, write_all_published

            def on_phase(phase: str, detail: str = "") -> None:
                """write_all_published 阶段回调。"""
                phase_pct = {
                    "reconcile_magnets": 6,
                    "ensure_hubs": 8,
                    "pages": 12,
                    "home": 82,
                    "hubs": 88,
                    "sitemap": 92,
                    "trust": 95,
                    "static_shell": 97,
                }.get(phase, 50)
                if phase in (
                    "reconcile_magnets",
                    "ensure_hubs",
                    "pages",
                    "home",
                    "hubs",
                    "sitemap",
                    "trust",
                    "static_shell",
                ):
                    _set_step(steps, phase, "running", detail or phase)
                _set_progress(
                    phase=phase,
                    percent=phase_pct,
                    message=detail or phase,
                    steps=list(steps),
                )

            def on_page(index: int, total: int, page_id: str, result: Dict[str, Any]) -> None:
                """逐页进度。"""
                nonlocal ok_pages, fail_pages
                ok = bool(result.get("ok"))
                if ok:
                    ok_pages += 1
                else:
                    fail_pages += 1
                detail = str(
                    result.get("output_file")
                    or result.get("canonical_path")
                    or result.get("error")
                    or ""
                )
                _push_recent(recent, page_id, ok, detail)
                pct = 12 + int(68 * (index / max(total, 1)))
                _set_step(
                    steps,
                    "pages",
                    "running",
                    f"{index}/{total} ok={ok_pages} fail={fail_pages}",
                )
                _set_progress(
                    phase="pages",
                    percent=min(80, pct),
                    current_page_id=page_id,
                    page_index=index,
                    page_total=total,
                    ok_pages=ok_pages,
                    fail_pages=fail_pages,
                    message=f"Generate {index}/{total} · {page_id}",
                    recent_pages=list(recent),
                    steps=list(steps),
                )

            prepare_raw = write_all_published(on_page=on_page, on_phase=on_phase)
            if isinstance(prepare_raw, dict) and prepare_raw.get("ok") is False:
                raise RuntimeError(
                    "; ".join(prepare_raw.get("errors") or [])
                    or prepare_raw.get("error")
                    or "generate all 失败"
                )

            for sid in (
                "reconcile_magnets",
                "ensure_hubs",
                "pages",
                "home",
                "hubs",
                "sitemap",
                "trust",
                "static_shell",
            ):
                if sid == "pages":
                    _set_step(
                        steps,
                        sid,
                        "ok",
                        f"generated={prepare_raw.get('generated')}/{prepare_raw.get('count')} "
                        f"fail={fail_pages}",
                    )
                elif sid == "home":
                    home = prepare_raw.get("home") or {}
                    _set_step(
                        steps,
                        sid,
                        "ok",
                        f"catalog={home.get('catalog_count')} pages={home.get('page_count')}",
                    )
                elif sid == "hubs":
                    hubs = prepare_raw.get("hubs") or {}
                    _set_step(
                        steps,
                        sid,
                        "ok",
                        f"generated={hubs.get('generated')}/{hubs.get('count')}",
                    )
                elif sid == "ensure_hubs":
                    he = prepare_raw.get("hub_ensure") or {}
                    _set_step(
                        steps,
                        sid,
                        "ok",
                        f"created={he.get('created', he.get('ensured', 0))}",
                    )
                elif sid == "reconcile_magnets":
                    rm = prepare_raw.get("reconcile_magnets") or {}
                    _set_step(
                        steps,
                        sid,
                        "ok",
                        f"fixed={rm.get('fixed', 0)} mismatches",
                    )
                else:
                    _set_step(steps, sid, "ok", "done")

            # 抽样验收：优先已知样例 + 结果中前几个 ok 页
            out_root = Path(str(prepare_raw.get("out_root") or DEFAULT_OUT_ROOT))
            sample_rels: List[str] = [
                "breaking-bad/s4e6/index.html",
                "inception-2010/index.html",
            ]
            for page in (prepare_raw.get("pages") or [])[:5]:
                if not page.get("ok"):
                    continue
                out_file = str(page.get("output_file") or "")
                if out_file and str(out_root) in out_file:
                    rel = out_file[len(str(out_root)) :].lstrip("/\\")
                    if rel and rel not in sample_rels:
                        sample_rels.append(rel)

            _set_step(steps, "verify", "running", "抽样检查源更新时间…")
            _set_progress(
                phase="verify",
                percent=98,
                message="抽样验收源更新时间标记…",
                steps=list(steps),
                current_page_id=None,
            )
            verify = _verify_magnets_updated_baked(out_root, sample_rels)
            _set_step(
                steps,
                "verify",
                "ok" if verify.get("ok") else "warn",
                (
                    "源更新时间已写入抽样页"
                    if verify.get("ok")
                    else "; ".join(verify.get("warnings") or ["验收未通过"])
                ),
            )

            summary = {
                "generated": prepare_raw.get("generated"),
                "count": prepare_raw.get("count"),
                "indexable_generated": prepare_raw.get("indexable_generated"),
                "noindex_generated": prepare_raw.get("noindex_generated"),
                "out_root": str(out_root),
                "home_catalog_count": (prepare_raw.get("home") or {}).get("catalog_count"),
                "hubs_generated": (prepare_raw.get("hubs") or {}).get("generated"),
                "errors": prepare_raw.get("errors") or [],
            }

            # 回写跟踪槽 generate 阶段（若有活跃批次）
            if batch:
                detail = (
                    f"all generated={summary.get('generated')}/{summary.get('count')}"
                )[:200]
                for row in batch.get("slots") or []:
                    pid = str(row.get("page_id") or "")
                    if pid:
                        update_slot_stage(batch, pid, "generate", status="ok", detail=detail)
                save_batch(batch)

            finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _set_progress(
                status="done" if verify.get("ok") else "done",
                phase="done",
                percent=100,
                message=(
                    f"Generate all 完成 · {summary.get('generated')}/{summary.get('count')} 页"
                    + ("" if verify.get("ok") else " · ⚠ 验收警告见 verify")
                ),
                steps=list(steps),
                verify=verify,
                result_summary=summary,
                ok=bool(prepare_raw.get("ok")) and bool(verify.get("ok")),
                finished_at=finished,
                recent_pages=list(recent),
                summary=summarize_batch(batch) if batch else None,
            )
        except Exception as exc:  # noqa: BLE001
            _set_progress(
                status="error",
                phase="error",
                percent=100,
                message=str(exc),
                error=str(exc),
                ok=False,
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                steps=list(steps),
            )
            if batch:
                for row in batch.get("slots") or []:
                    pid = str(row.get("page_id") or "")
                    if pid:
                        update_slot_stage(
                            batch, pid, "generate", status="failed", detail=str(exc)[:200]
                        )
                save_batch(batch)

    _WORKER = threading.Thread(target=_worker, name="ops-generate-all", daemon=True)
    _WORKER.start()
    return {"ok": True, "started": True, "progress": get_progress()}
