# -*- coding: utf-8 -*-
"""
Ops 第三/四段动作：生成流程与上线。

@module workflow.ops.actions
@description
  在跟踪表批次上执行 pipeline → 刷新门禁 → generate → speedtest →
  seo_c2 → deploy，并回写每槽/批次阶段状态。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT
from workflow.ops.track_store import (
    load_active_batch,
    load_batch,
    save_batch,
    summarize_batch,
    update_batch_step,
    update_slot_gate,
    update_slot_stage,
)


def _get_batch(batch_id: Optional[str] = None) -> Dict[str, Any]:
    """加载指定或活跃批次，不存在则抛错结构。"""
    batch = load_batch(batch_id) if batch_id else load_active_batch()
    if not batch:
        return {"ok": False, "error": "无活跃跟踪批次；请先在「筛选」导入"}
    return {"ok": True, "batch": batch}


def _selected_slots(batch: Dict[str, Any], page_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """取 selected 槽位，可再按 page_ids 收窄。"""
    rows = [s for s in (batch.get("slots") or []) if s.get("selected", True)]
    if page_ids:
        allow = set(page_ids)
        rows = [s for s in rows if s.get("page_id") in allow]
    return rows


def _fetch_gate_from_mysql(store: Any, page_id: str) -> Dict[str, Any]:
    """
    查询单槽 MySQL 门禁字段。

    @param store: MySQLStore
    @param page_id: 槽位 ID
    @returns: gate dict
    """
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id, magnet_count, page_status, robots_noindex, canonical_path
                FROM media_pages WHERE page_id = %s LIMIT 1
                """,
                (page_id,),
            )
            page_row = cur.fetchone()
            if not page_row:
                return {
                    "magnet_count": 0,
                    "has_recommended": False,
                    "page_status": None,
                    "robots_noindex": None,
                    "indexable": False,
                    "canonical_path": None,
                }
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM download_resources
                WHERE page_id = %s AND is_recommended = 1
                """,
                (page_id,),
            )
            rec_row = cur.fetchone() or {}
            has_rec = int(rec_row.get("cnt") or 0) > 0
    finally:
        conn.close()

    magnet_count = int(page_row.get("magnet_count") or 0)
    page_status = page_row.get("page_status")
    robots_raw = page_row.get("robots_noindex")
    robots_flag = bool(int(robots_raw)) if robots_raw is not None else None
    # indexable：magnet≥2 + published + 有 Rec + robots_noindex=0
    indexable = (
        magnet_count >= 2
        and str(page_status) == "published"
        and has_rec
        and (robots_flag is False or (robots_flag is None and has_rec))
    )
    if robots_flag is True:
        indexable = False
    return {
        "magnet_count": magnet_count,
        "has_recommended": has_rec,
        "page_status": page_status,
        "robots_noindex": robots_flag,
        "indexable": indexable,
        "canonical_path": page_row.get("canonical_path"),
    }


def refresh_gates(batch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    从 MySQL 刷新每槽门禁（magnet / Rec / page_status / indexable）。

    @param batch_id: 可选批次
    @returns: 摘要
    """
    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]

    try:
        from workflow.storage.mysql_store import MySQLStore

        store = MySQLStore()
        ping = store.ping()
        if not ping.get("ok"):
            return {"ok": False, "error": "MySQL 不可用", "detail": ping}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"MySQL 连接失败: {exc}"}

    updated = 0
    for row in _selected_slots(batch):
        page_id = str(row["page_id"])
        try:
            gate = _fetch_gate_from_mysql(store, page_id)
            update_slot_gate(batch, page_id, gate)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            update_slot_gate(
                batch,
                page_id,
                {
                    "magnet_count": None,
                    "has_recommended": None,
                    "page_status": None,
                    "indexable": False,
                },
            )
            row["error"] = str(exc)

    save_batch(batch)
    return {
        "ok": True,
        "updated": updated,
        "summary": summarize_batch(batch),
        "batch": batch,
    }


def run_pipeline(
    *,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
    fetch: bool = True,
    skip_existing: bool = True,
    mode: str = "live",
) -> Dict[str, Any]:
    """
    对跟踪表选中槽位跑 pipeline batch/slot。

    @param batch_id: 批次
    @param page_ids: 可选子集
    @param fetch: 是否拉 Jackett
    @param skip_existing: 跳过已有 ≥2 magnet
    @param mode: live | demo
    @returns: 结果摘要 + 更新后批次
    """
    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]
    rows = _selected_slots(batch, page_ids)
    if not rows:
        return {"ok": False, "error": "无选中槽位"}

    for row in rows:
        update_slot_stage(batch, row["page_id"], "pipeline", status="running", detail="")
    save_batch(batch)

    slots_payload = []
    for row in rows:
        item: Dict[str, Any] = {
            "label": row.get("label"),
            "tmdb_id": row["tmdb_id"],
            "media_type": row["media_type"],
            "title": row.get("title"),
        }
        if row.get("season") is not None:
            item["season"] = row["season"]
        if row.get("episode") is not None:
            item["episode"] = row["episode"]
        slots_payload.append(item)

    from workflow.storage.pipeline import run_batch_slot_pipeline

    report = run_batch_slot_pipeline(
        slots_payload,
        mode=mode,
        fetch=fetch,
        skip_existing=skip_existing,
        warm_tmdb=True,
    )

    by_page = {r.get("page_id"): r for r in (report.get("results") or [])}
    for row in rows:
        page_id = row["page_id"]
        entry = by_page.get(page_id) or {}
        status = entry.get("status") or ("ok" if report.get("ok") else "failed")
        if status == "skipped_existing":
            update_slot_stage(
                batch, page_id, "pipeline", status="skipped", detail="已有 ≥2 magnet"
            )
        elif status == "ok":
            detail = ""
            write = (entry.get("result") or {}).get("write") or {}
            if write:
                detail = f"magnet={write.get('magnet_count')} status={write.get('page_status')}"
            update_slot_stage(batch, page_id, "pipeline", status="ok", detail=detail)
        else:
            err = str((entry.get("result") or {}).get("error") or entry.get("status") or "failed")
            update_slot_stage(batch, page_id, "pipeline", status="failed", detail=err)

    save_batch(batch)
    gate_result = refresh_gates(batch["meta"]["batch_id"])
    return {
        "ok": bool(report.get("ok")),
        "pipeline_report": {
            "total": report.get("total"),
            "ok_count": report.get("ok_count"),
            "skip_count": report.get("skip_count"),
            "fail_count": report.get("fail_count"),
            "sync_run_id": report.get("sync_run_id"),
        },
        "summary": summarize_batch(gate_result.get("batch") or batch),
        "batch": gate_result.get("batch") or batch,
    }


def run_generate(
    *,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
    generate_all: bool = False,
) -> Dict[str, Any]:
    """
    生成静态页：默认同源跟踪槽；可选 generate all。

    @param batch_id: 批次
    @param page_ids: 子集
    @param generate_all: 全站 bake
    @returns: 结果
    """
    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]
    rows = _selected_slots(batch, page_ids)

    from portal.generator.generate_one import write_all_published, write_page_html

    if generate_all:
        for row in rows:
            update_slot_stage(batch, row["page_id"], "generate", status="running")
        save_batch(batch)
        try:
            result = write_all_published()
            detail = json.dumps(result, ensure_ascii=False)[:500] if isinstance(result, dict) else str(result)
            for row in rows:
                update_slot_stage(
                    batch, row["page_id"], "generate", status="ok", detail=detail[:200]
                )
            save_batch(batch)
            return {"ok": True, "mode": "all", "result": result, "summary": summarize_batch(batch), "batch": batch}
        except Exception as exc:  # noqa: BLE001
            for row in rows:
                update_slot_stage(batch, row["page_id"], "generate", status="failed", detail=str(exc))
            save_batch(batch)
            return {"ok": False, "error": str(exc), "batch": batch}

    ok_n = 0
    fail_n = 0
    hub_ids: List[str] = []
    for row in rows:
        page_id = row["page_id"]
        update_slot_stage(batch, page_id, "generate", status="running")
        save_batch(batch)
        try:
            out = write_page_html(page_id=page_id)
            path = ""
            if isinstance(out, dict):
                path = str(out.get("path") or out.get("out") or "")
                ok = bool(out.get("ok", True))
            else:
                path = str(out)
                ok = True
            if ok:
                update_slot_stage(batch, page_id, "generate", status="ok", detail=path)
                ok_n += 1
                # 剧集单页 generate 后同步 Hub，避免 /{slug}/ 404
                if str(page_id).startswith("tv:") and ":s" in str(page_id):
                    parts = str(page_id).split(":")
                    if len(parts) >= 2 and parts[1].isdigit():
                        hub_id = f"tv:{parts[1]}:hub"
                        if hub_id not in hub_ids:
                            hub_ids.append(hub_id)
            else:
                update_slot_stage(
                    batch, page_id, "generate", status="failed", detail=str(out)
                )
                fail_n += 1
        except Exception as exc:  # noqa: BLE001
            update_slot_stage(batch, page_id, "generate", status="failed", detail=str(exc))
            fail_n += 1
        save_batch(batch)

    hubs_generated: List[str] = []
    for hub_id in hub_ids:
        try:
            from workflow.storage.mysql_store import MySQLStore

            store = MySQLStore()
            # 从 page_id 解析 tmdb，确保 hub 行存在
            tmdb_id = int(hub_id.split(":")[1])
            store.ensure_show_hub_page(tmdb_id)
            hout = write_page_html(page_id=hub_id)
            if isinstance(hout, dict) and hout.get("ok", True):
                hubs_generated.append(hub_id)
        except Exception:  # noqa: BLE001 — Hub 失败不阻断 episode 结果
            pass

    return {
        "ok": fail_n == 0,
        "mode": "pages",
        "ok_count": ok_n,
        "fail_count": fail_n,
        "hubs_generated": hubs_generated,
        "summary": summarize_batch(batch),
        "batch": batch,
    }


def run_speedtest(
    *,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    对选中槽位调用 speedtest CLI（子进程，写入 MySQL）。

    @param batch_id: 批次
    @param page_ids: 子集
    @returns: 结果
    """
    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]
    rows = _selected_slots(batch, page_ids)
    if not rows:
        return {"ok": False, "error": "无选中槽位"}

    ids = [str(r["page_id"]) for r in rows]
    for row in rows:
        update_slot_stage(batch, row["page_id"], "speedtest", status="running")
    save_batch(batch)

    report_dir = PROJECT_ROOT / "worklogs" / "ops"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"speedtest-{batch['meta']['batch_id']}.json"
    cmd = [
        sys.executable,
        "-m",
        "workflow.torrent_sources.speedtest.run",
        "batch",
        "--page-ids",
        ",".join(ids),
        "--write",
        "--report",
        str(report_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        ok = proc.returncode == 0
        detail = (proc.stdout or proc.stderr or "")[-400:]
        for row in rows:
            update_slot_stage(
                batch,
                row["page_id"],
                "speedtest",
                status="ok" if ok else "failed",
                detail=detail[:200],
            )
        save_batch(batch)
        # 测速写入后 bake 静态页，否则线上仍无 Grab/测速面板
        regen: Dict[str, Any] = {}
        if ok:
            regen = run_generate(batch_id=batch["meta"]["batch_id"], page_ids=ids)
        return {
            "ok": ok and bool(regen.get("ok", True)),
            "returncode": proc.returncode,
            "report": str(report_path.relative_to(PROJECT_ROOT)),
            "regenerate": regen,
            "summary": summarize_batch(batch),
            "batch": batch,
        }
    except FileNotFoundError:
        # 模块路径可能不同，尝试 scripts/speedtest_batch_worker.py
        cmd2 = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "speedtest_batch_worker.py"),
            "--page-ids",
            ",".join(ids),
            "--write",
            "--report",
            str(report_path),
        ]
        try:
            proc = subprocess.run(
                cmd2,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=3600,
                check=False,
            )
            ok = proc.returncode == 0
            for row in rows:
                update_slot_stage(
                    batch,
                    row["page_id"],
                    "speedtest",
                    status="ok" if ok else "failed",
                    detail=(proc.stdout or proc.stderr or "")[-200:],
                )
            save_batch(batch)
            return {
                "ok": ok,
                "returncode": proc.returncode,
                "report": str(report_path.relative_to(PROJECT_ROOT)),
                "summary": summarize_batch(batch),
                "batch": batch,
            }
        except Exception as exc:  # noqa: BLE001
            for row in rows:
                update_slot_stage(batch, row["page_id"], "speedtest", status="failed", detail=str(exc))
            save_batch(batch)
            return {"ok": False, "error": str(exc), "batch": batch}
    except Exception as exc:  # noqa: BLE001
        for row in rows:
            update_slot_stage(batch, row["page_id"], "speedtest", status="failed", detail=str(exc))
        save_batch(batch)
        return {"ok": False, "error": str(exc), "batch": batch}


def run_seo_c2(*, batch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    跑本地 seo_c2_checklist（批次级步骤）。

    @param batch_id: 批次
    @returns: 结果
    """
    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]
    update_batch_step(batch, "seo_c2", status="running", detail="")
    save_batch(batch)

    script = PROJECT_ROOT / "scripts" / "seo_c2_checklist.sh"
    if not script.is_file():
        # 尝试 python 等价
        py = PROJECT_ROOT / "scripts" / "seo_c2_checklist.py"
        if py.is_file():
            cmd = [sys.executable, str(py)]
        else:
            update_batch_step(batch, "seo_c2", status="failed", detail="找不到 seo_c2_checklist")
            save_batch(batch)
            return {"ok": False, "error": "找不到 seo_c2_checklist 脚本", "batch": batch}
    else:
        cmd = ["bash", str(script)]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        ok = proc.returncode == 0
        detail = (proc.stdout or proc.stderr or "")[-500:]
        update_batch_step(
            batch, "seo_c2", status="ok" if ok else "failed", detail=detail
        )
        save_batch(batch)
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "detail": detail,
            "summary": summarize_batch(batch),
            "batch": batch,
        }
    except Exception as exc:  # noqa: BLE001
        update_batch_step(batch, "seo_c2", status="failed", detail=str(exc))
        save_batch(batch)
        return {"ok": False, "error": str(exc), "batch": batch}


def run_deploy(
    *,
    batch_id: Optional[str] = None,
    prepare_only: bool = True,
) -> Dict[str, Any]:
    """
    执行 deploy_cf_pages.sh。默认仅 --prepare-only；正式 deploy 需显式关闭。

    @param batch_id: 批次
    @param prepare_only: True=只准备 dist；False=真正 wrangler deploy
    @returns: 结果
    """
    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]
    update_batch_step(batch, "deploy", status="running", detail="")
    save_batch(batch)

    script = PROJECT_ROOT / "scripts" / "deploy_cf_pages.sh"
    if not script.is_file():
        update_batch_step(batch, "deploy", status="failed", detail="找不到 deploy_cf_pages.sh")
        save_batch(batch)
        return {"ok": False, "error": "找不到 deploy_cf_pages.sh", "batch": batch}

    cmd = ["bash", str(script)]
    if prepare_only:
        cmd.append("--prepare-only")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        ok = proc.returncode == 0
        detail = (proc.stdout or proc.stderr or "")[-500:]
        mode = "prepare-only" if prepare_only else "deploy"
        update_batch_step(
            batch,
            "deploy",
            status="ok" if ok else "failed",
            detail=f"[{mode}] {detail}",
        )
        save_batch(batch)
        return {
            "ok": ok,
            "prepare_only": prepare_only,
            "returncode": proc.returncode,
            "detail": detail,
            "summary": summarize_batch(batch),
            "batch": batch,
        }
    except Exception as exc:  # noqa: BLE001
        update_batch_step(batch, "deploy", status="failed", detail=str(exc))
        save_batch(batch)
        return {"ok": False, "error": str(exc), "batch": batch}
