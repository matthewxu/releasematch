# -*- coding: utf-8 -*-
"""
Ops 第二段：筛选。

@module workflow.ops.filter_service
@description
  对工作区清单按 media_type / source_tier / popularity / 关键词 /
  是否已 published / 是否在失败登记册 过滤，产出可导入跟踪表的子集。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from workflow.config import PROJECT_ROOT
from workflow.storage.failed_slots_store import DEFAULT_REGISTRY_PATH, build_slot_key


def _load_failed_keys(registry_path: Path = DEFAULT_REGISTRY_PATH) -> Set[str]:
    """读取失败登记册 active slot_key。"""
    if not registry_path.is_file():
        mirror = PROJECT_ROOT / "worklogs" / "failed-slots-registry.json"
        registry_path = mirror if mirror.is_file() else registry_path
    if not registry_path.is_file():
        return set()
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    active = data.get("active") or data.get("slots") or []
    keys: Set[str] = set()
    if isinstance(active, dict):
        keys.update(active.keys())
    elif isinstance(active, list):
        for row in active:
            if isinstance(row, dict):
                key = row.get("slot_key") or row.get("page_id")
                if key:
                    keys.add(str(key))
                elif row.get("tmdb_id"):
                    keys.add(
                        build_slot_key(
                            int(row["tmdb_id"]),
                            str(row.get("media_type") or "tv"),
                            season=row.get("season"),
                            episode=row.get("episode"),
                        )
                    )
    return keys


def _published_page_ids() -> Set[str]:
    """查询 MySQL 已 published 且 magnet≥2 的 page_id；失败则返回空集。"""
    try:
        from workflow.storage.mysql_store import MySQLStore

        store = MySQLStore()
        ping = store.ping()
        if not ping.get("ok"):
            return set()
        return set(store.list_published_page_ids())
    except Exception:  # noqa: BLE001 — UI 筛选降级
        return set()


def apply_filters(
    slots: List[Dict[str, Any]],
    *,
    media_types: Optional[List[str]] = None,
    tiers: Optional[List[str]] = None,
    q: Optional[str] = None,
    pop_min: Optional[float] = None,
    pop_max: Optional[float] = None,
    exclude_published: bool = False,
    exclude_failed: bool = False,
    only_failed: bool = False,
    selected_page_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    筛选清单。

    @param slots: 已标注 page_id / source_tier 的槽位
    @param media_types: 允许的 media_type（movie/tv）
    @param tiers: 允许的 source_tier
    @param q: 标题/label 关键词（子串，不分大小写）
    @param pop_min: 最低 popularity（无 popularity 字段的条目保留）
    @param pop_max: 最高 popularity
    @param exclude_published: 排除已有 ≥2 magnet 的 published 页
    @param exclude_failed: 排除失败登记册 active
    @param only_failed: 仅保留失败登记册 active
    @param selected_page_ids: 若给定，仅保留勾选的 page_id
    @returns: { ok, slots, count_before, count_after, filter }
    """
    count_before = len(slots)
    published = _published_page_ids() if exclude_published else set()
    failed = _load_failed_keys() if (exclude_failed or only_failed) else set()
    media_set = {m.lower() for m in media_types} if media_types else None
    tier_set = {t.lower() for t in tiers} if tiers else None
    q_norm = (q or "").strip().lower()
    selected_set = set(selected_page_ids) if selected_page_ids is not None else None

    out: List[Dict[str, Any]] = []
    for slot in slots:
        page_id = str(slot.get("page_id") or "")
        media = str(slot.get("media_type") or "tv").lower()
        tier = str(slot.get("source_tier") or "unknown").lower()

        if selected_set is not None and page_id not in selected_set:
            continue
        if media_set is not None and media not in media_set:
            continue
        if tier_set is not None and tier not in tier_set:
            continue
        if q_norm:
            hay = f"{slot.get('label') or ''} {slot.get('title') or ''} {page_id}".lower()
            if q_norm not in hay:
                continue
        pop = slot.get("popularity")
        if pop is not None:
            try:
                pop_f = float(pop)
            except (TypeError, ValueError):
                pop_f = None
            if pop_f is not None:
                if pop_min is not None and pop_f < pop_min:
                    continue
                if pop_max is not None and pop_f > pop_max:
                    continue
        if exclude_published and page_id in published:
            continue
        if exclude_failed and page_id in failed:
            continue
        if only_failed and page_id not in failed:
            continue
        out.append(slot)

    filter_meta = {
        "media_types": media_types,
        "tiers": tiers,
        "q": q,
        "pop_min": pop_min,
        "pop_max": pop_max,
        "exclude_published": exclude_published,
        "exclude_failed": exclude_failed,
        "only_failed": only_failed,
        "selected_count": len(selected_set) if selected_set is not None else None,
        "count_before": count_before,
        "count_after": len(out),
    }
    return {
        "ok": True,
        "slots": out,
        "count_before": count_before,
        "count_after": len(out),
        "filter": filter_meta,
    }
