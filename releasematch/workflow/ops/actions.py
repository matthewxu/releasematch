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
import shutil
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


def _selected_slots(
    batch: Dict[str, Any],
    page_ids: Optional[List[str]] = None,
    *,
    require_selected: bool = True,
) -> List[Dict[str, Any]]:
    """
    取跟踪槽位；默认可再按 page_ids 收窄。

    @param batch: 批次 dict
    @param page_ids: 可选 page_id 白名单
    @param require_selected: True 时仅 selected；False 时可用全表再按 page_ids 滤
    @returns: 槽位行列表
    @description
      若显式传入 page_ids 但批次中无匹配行，则合成仅含 page_id 的占位行，
      便于 CLI 增量 deploy 不依赖勾选状态。
    """
    rows = list(batch.get("slots") or [])
    if require_selected:
        rows = [s for s in rows if s.get("selected", True)]
    if page_ids:
        allow = set(page_ids)
        matched = [s for s in rows if s.get("page_id") in allow]
        if matched:
            return matched
        # 完整注释：显式 page_ids 时允许脱离勾选，合成最小行供 generate
        return [{"page_id": pid, "selected": True} for pid in page_ids if pid]
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


def _prepare_dist_full() -> Dict[str, Any]:
    """
    全量准备 dist：generate all（含 home / hubs / sitemap / static 壳）。

    @returns: write_all_published 摘要
    """
    from portal.generator.generate_one import write_all_published

    return write_all_published()


def _prepare_dist_incremental(
    *,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    增量准备 dist：仅 bake 跟踪表选中（或指定）槽，并刷新 home / sitemap / 静态壳。

    @param batch_id: 批次 ID
    @param page_ids: 可选 page_id 子集
    @returns: 含 generate / home / sitemap / static_shell 的摘要
    @description
      wrangler 上传本身按 hash 增量；此处避免全站重 bake。
      Hub 由 run_generate 同步；删除场景须另行从 dist 去掉路径（本函数不删文件）。
    """
    from portal.generator.generate_one import DEFAULT_OUT_ROOT, write_home_page
    from portal.generator.sitemap import write_sitemap
    from portal.generator.static_shell import sync_static_shell

    gen = run_generate(
        batch_id=batch_id,
        page_ids=page_ids,
        generate_all=False,
    )
    if not gen.get("ok"):
        return {
            "ok": False,
            "error": gen.get("error") or "增量 generate 失败",
            "generate": gen,
        }

    home_result = write_home_page()
    sitemap_result = write_sitemap(DEFAULT_OUT_ROOT)
    shell_result = sync_static_shell()
    return {
        "ok": True,
        "generate": {
            "ok_count": gen.get("ok_count"),
            "fail_count": gen.get("fail_count"),
            "hubs_generated": gen.get("hubs_generated"),
        },
        "home": home_result,
        "sitemap": sitemap_result,
        "static_shell": shell_result,
        "batch": gen.get("batch"),
    }


def _run_wrangler_upload() -> Dict[str, Any]:
    """
    仅执行 wrangler deploy（上传当前 portal/dist，CF 侧按 hash 增量）。

    @returns: returncode / detail / ok
    """
    if not shutil.which("wrangler"):
        return {"ok": False, "error": "未找到 wrangler，请 npm i -g wrangler"}

    proc = subprocess.run(
        ["wrangler", "deploy"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    detail = (proc.stdout or "")[-800:] + (("\n" + proc.stderr) if proc.stderr else "")
    detail = detail[-1200:]
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "detail": detail.strip(),
    }


def run_deploy(
    *,
    batch_id: Optional[str] = None,
    page_ids: Optional[List[str]] = None,
    scope: str = "full",
    upload: Optional[bool] = None,
    prepare_only: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Ops 部署：支持全量 / 增量 prepare，以及可选正式 wrangler 上传。

    @param batch_id: 跟踪批次
    @param page_ids: 增量模式下的 page_id 子集（默认选中槽）
    @param scope: ``full`` | ``incremental`` | ``upload_only``
    @param upload: True=执行 wrangler deploy；False=仅准备 dist
    @param prepare_only: 兼容旧 API；若提供则 ``upload = not prepare_only``
    @returns: 结果摘要（含 scope / upload / prepare / wrangler）
    @description
      - full：generate all + 壳同步（与历史 deploy_cf_pages.sh 一致）
      - incremental：只 bake 选中槽 + home/sitemap/壳；上传仍由 wrangler 对账增量
      - upload_only：假定 dist 已就绪，只 wrangler
    """
    # 完整注释：兼容旧客户端只传 prepare_only
    if upload is None:
        if prepare_only is not None:
            upload = not bool(prepare_only)
        else:
            upload = False

    scope_norm = str(scope or "full").strip().lower()
    if scope_norm in ("selected", "pages", "incr"):
        scope_norm = "incremental"
    if scope_norm not in ("full", "incremental", "upload_only"):
        return {"ok": False, "error": f"未知 scope={scope!r}，应为 full|incremental|upload_only"}

    loaded = _get_batch(batch_id)
    if not loaded.get("ok"):
        return loaded
    batch = loaded["batch"]

    if scope_norm == "incremental":
        rows = _selected_slots(batch, page_ids)
        if not rows:
            return {
                "ok": False,
                "error": "增量 deploy 需要跟踪表中至少 1 个选中槽",
                "batch": batch,
            }

    update_batch_step(
        batch,
        "deploy",
        status="running",
        detail=f"scope={scope_norm} upload={upload}",
    )
    save_batch(batch)

    prepare_result: Dict[str, Any] = {"skipped": True}
    wrangler_result: Dict[str, Any] = {"skipped": True}

    try:
        if scope_norm == "full":
            prepare_result = _prepare_dist_full()
            if isinstance(prepare_result, dict) and prepare_result.get("ok") is False:
                raise RuntimeError(prepare_result.get("error") or "全量 prepare 失败")
            # write_all_published 成功时通常无 ok=false；错误抛异常
            prepare_result = {"ok": True, "mode": "full", "result": prepare_result}
        elif scope_norm == "incremental":
            prepare_result = _prepare_dist_incremental(
                batch_id=batch.get("meta", {}).get("batch_id") or batch_id,
                page_ids=page_ids,
            )
            if not prepare_result.get("ok"):
                raise RuntimeError(prepare_result.get("error") or "增量 prepare 失败")
            # run_generate 已 save_batch；重新加载以免覆盖
            reloaded = _get_batch(batch_id)
            if reloaded.get("ok"):
                batch = reloaded["batch"]
        # upload_only：跳过 prepare

        if upload:
            wrangler_result = _run_wrangler_upload()
            if not wrangler_result.get("ok"):
                raise RuntimeError(
                    wrangler_result.get("error")
                    or wrangler_result.get("detail")
                    or "wrangler deploy 失败"
                )

        detail_parts = [f"scope={scope_norm}", f"upload={upload}"]
        if prepare_result.get("skipped"):
            detail_parts.append("prepare=skip")
        elif scope_norm == "incremental":
            g = prepare_result.get("generate") or {}
            detail_parts.append(
                f"prepare=incr ok={g.get('ok_count')} fail={g.get('fail_count')}"
            )
        else:
            detail_parts.append("prepare=full")
        if upload:
            detail_parts.append("wrangler=ok")
        detail = " | ".join(detail_parts)
        if upload and wrangler_result.get("detail"):
            detail = (detail + "\n" + str(wrangler_result.get("detail")))[-500:]

        update_batch_step(batch, "deploy", status="ok", detail=detail)
        save_batch(batch)
        return {
            "ok": True,
            "scope": scope_norm,
            "upload": upload,
            "prepare_only": not upload,
            "prepare": prepare_result,
            "wrangler": wrangler_result,
            "summary": summarize_batch(batch),
            "batch": batch,
        }
    except Exception as exc:  # noqa: BLE001
        update_batch_step(batch, "deploy", status="failed", detail=str(exc)[:500])
        save_batch(batch)
        return {
            "ok": False,
            "error": str(exc),
            "scope": scope_norm,
            "upload": upload,
            "prepare": prepare_result,
            "wrangler": wrangler_result,
            "batch": batch,
        }
