# -*- coding: utf-8 -*-
"""
Ops 页面台账 — 以 ``media_pages`` 为统管真源。

@module workflow.ops.pages_service
@description
  浏览 / 搜索 / 统计 / 下线已入库页面；与 ``ops_track_*`` 批次工单分离。
  下线：改统管状态 → 删 dist → 重 bake home/sitemap → 可选 wrangler 对账上传。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from portal.generator.generate_one import write_home_page
from portal.generator.render import _canonical_to_output_relpath
from portal.generator.sitemap import write_sitemap
from workflow.config import PROJECT_ROOT, SITE_ORIGIN
from workflow.ops import actions
from workflow.ops.track_store import (
    append_slots_to_active_batch,
    create_batch,
    load_active_batch,
    make_track_row,
)
from workflow.storage.failed_slots_store import parse_page_id
from workflow.storage.mysql_store import MySQLStore

# 默认静态输出根（与 generate_one.DEFAULT_OUT_ROOT 对齐）
DEFAULT_DIST_ROOT: Path = PROJECT_ROOT / "portal" / "dist"


def inventory_stats() -> Dict[str, Any]:
    """
    返回 ``media_pages`` 状态统计。

    @returns: {ok, ...stats}
    """
    store = MySQLStore()
    stats = store.page_inventory_stats()
    return {"ok": True, **stats}


def list_inventory(
    *,
    q: Optional[str] = None,
    status: Optional[str] = None,
    page_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    台账列表（统管表 + 最近工单快照）。

    @param q: 搜索关键词
    @param status: draft|thin|published
    @param page_type: episode|movie|show_hub
    @param limit: 分页大小
    @param offset: 偏移
    @returns: store.list_pages_inventory 结果
    """
    store = MySQLStore()
    return store.list_pages_inventory(
        q=q,
        status=status,
        page_type=page_type,
        limit=limit,
        offset=offset,
    )


def _dist_dir_for_canonical(canonical_path: str, dist_root: Path) -> Optional[Path]:
    """
    canonical_path → dist 下页面目录（含 index.html 的父目录）。

    @param canonical_path: 如 /breaking-bad/s4e6/
    @param dist_root: portal/dist
    @returns: 目录 Path；首页根路径返回 None（不下线删整站 index）
    """
    rel = _canonical_to_output_relpath(canonical_path or "")
    if rel == "index.html":
        return None
    # breaking-bad/s4e6/index.html → breaking-bad/s4e6
    page_file = dist_root / rel
    return page_file.parent


def _remove_dist_pages(
    canonical_paths: Dict[str, str],
    *,
    dist_root: Path,
) -> Dict[str, Any]:
    """
    从 dist 删除已下线页面目录。

    @param canonical_paths: page_id → canonical_path
    @param dist_root: 输出根
    @returns: removed / missing / skipped 摘要
    """
    removed: List[str] = []
    missing: List[str] = []
    skipped: List[str] = []
    for page_id, canonical in canonical_paths.items():
        target = _dist_dir_for_canonical(str(canonical or ""), dist_root)
        if target is None:
            skipped.append(page_id)
            continue
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            removed.append(page_id)
        else:
            missing.append(page_id)
    return {"removed": removed, "missing_dist": missing, "skipped": skipped}


def unpublish_pages(
    page_ids: List[str],
    *,
    upload: bool = False,
    target_status: str = "draft",
    refresh_home_sitemap: bool = True,
    dist_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    下线统管页：改库 → 删 dist → 可选重 bake home/sitemap → 可选 wrangler。

    @param page_ids: 目标 page_id
    @param upload: True 时执行 wrangler deploy 对账（公网移除缺失路径）
    @param target_status: draft|thin
    @param refresh_home_sitemap: 下线后重写首页与 sitemap，避免残留链接
    @param dist_root: 覆盖默认 portal/dist
    @returns: 操作摘要
    """
    store = MySQLStore()
    db_result = store.unpublish_pages(page_ids, target_status=target_status)
    if not db_result.get("ok"):
        return db_result

    root = dist_root or DEFAULT_DIST_ROOT
    paths: Dict[str, str] = dict(db_result.get("canonical_paths") or {})
    # 仅对成功更新的 page 删 dist
    updated_ids = set(db_result.get("page_ids") or [])
    paths = {k: v for k, v in paths.items() if k in updated_ids}
    dist_result = _remove_dist_pages(paths, dist_root=root)

    home_result: Dict[str, Any] = {"skipped": True}
    sitemap_result: Dict[str, Any] = {"skipped": True}
    if refresh_home_sitemap and updated_ids:
        try:
            home_result = write_home_page(out_root=root, site_origin=SITE_ORIGIN)
        except Exception as exc:  # noqa: BLE001
            home_result = {"ok": False, "error": str(exc)}
        try:
            sitemap_result = write_sitemap(out_root=root, site_origin=SITE_ORIGIN)
        except Exception as exc:  # noqa: BLE001
            sitemap_result = {"ok": False, "error": str(exc)}

    wrangler_result: Dict[str, Any] = {"skipped": True}
    if upload:
        wrangler_result = actions._run_wrangler_upload()

    ok = True
    if upload and not wrangler_result.get("ok"):
        ok = False
    if home_result.get("ok") is False or sitemap_result.get("ok") is False:
        # home/sitemap 失败不阻断下线，但标记部分成功
        pass

    return {
        "ok": ok and bool(db_result.get("ok")),
        "db": db_result,
        "dist": dist_result,
        "home": home_result,
        "sitemap": sitemap_result,
        "upload": upload,
        "wrangler": wrangler_result,
    }


def _inventory_item_to_slot(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    台账行 → 可导入跟踪表的 slot dict。

    @param item: list_pages_inventory 单行
    @returns: slot（含 tmdb_id / media_type / season / episode）
    """
    page_id = str(item.get("page_id") or "")
    parsed = parse_page_id(page_id) or {}
    media_type = str(
        parsed.get("media_type")
        or item.get("media_kind")
        or ("movie" if str(item.get("page_type")) == "movie" else "tv")
    )
    return {
        "page_id": page_id,
        "tmdb_id": int(parsed.get("tmdb_id") or item.get("tmdb_id") or 0),
        "media_type": media_type,
        "media_kind": media_type,
        "season": parsed.get("season", item.get("season")),
        "episode": parsed.get("episode", item.get("episode")),
        "title": item.get("title") or page_id,
        "label": f"{item.get('title') or page_id} · {page_id}",
        "source_tier": "inventory",
        "page_type": item.get("page_type") or parsed.get("page_type"),
    }


def add_inventory_to_track(
    page_ids: List[str],
    *,
    create_new_batch: bool = False,
) -> Dict[str, Any]:
    """
    将台账勾选页加入活跃跟踪批（或新建批次），便于 ③④ 重跑。

    @param page_ids: 统管 page_id 列表
    @param create_new_batch: True 时始终新建批次；False 时追加到活跃批（无则新建）
    @returns: {ok, batch, added, skipped_existing, published_overlap}
    """
    ids = [str(p).strip() for p in (page_ids or []) if str(p).strip()]
    if not ids:
        return {"ok": False, "error": "缺少 page_ids"}

    store = MySQLStore()
    rows = store.get_inventory_rows_by_ids(ids)
    by_id = {str(it["page_id"]): it for it in rows}
    not_found = [pid for pid in ids if pid not in by_id]
    slots_raw = [_inventory_item_to_slot(by_id[pid]) for pid in ids if pid in by_id]
    if not slots_raw:
        return {
            "ok": False,
            "error": "page_ids 均不在 media_pages 统管表中",
            "missing": not_found,
        }

    published_overlap = [
        s["page_id"]
        for s in slots_raw
        if str(by_id.get(s["page_id"], {}).get("page_status")) == "published"
    ]

    track_rows = []
    for s in slots_raw:
        # Hub：make_track_row 会误生成 s00e00，改为保留真实 page_id
        if str(by_id.get(s["page_id"], {}).get("page_type")) == "show_hub" or str(
            s.get("page_id", "")
        ).endswith(":hub"):
            row = make_track_row(s, source_tier="inventory")
            row["page_id"] = s["page_id"]
            row["slot_key"] = s["page_id"]
            row["season"] = None
            row["episode"] = None
            track_rows.append(row)
        else:
            track_rows.append(make_track_row(s, source_tier="inventory"))

    active = None if create_new_batch else load_active_batch()
    if active and not create_new_batch:
        result = append_slots_to_active_batch(track_rows)
        result["published_overlap"] = published_overlap
        result["missing"] = not_found
        return result

    batch = create_batch(
        track_rows,
        source_meta={"kind": "inventory", "page_ids": ids},
        filter_meta={"from": "pages_inventory"},
    )
    return {
        "ok": True,
        "batch": batch,
        "added": len(track_rows),
        "skipped_existing": [],
        "published_overlap": published_overlap,
        "missing": not_found,
        "created_new_batch": True,
    }
