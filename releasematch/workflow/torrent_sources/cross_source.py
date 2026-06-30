#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨源交叉验证：infohash 去重与 cross_source_count 聚合。

@module workflow.torrent_sources.cross_source
@description
  同一 infohash 出现在多个数据源（eztv / yts / nyaa / jackett）时累加命中数，
  供 scorer 与页面 Hero badge 使用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from workflow.torrent_sources.models import ResourceItem


def normalize_source_family(indexer: str) -> str:
    """
    将 indexer 规范为跨源统计用的「源族」键。

    @param indexer: 如 eztv、yts、nyaa、jackett:all
    @returns: eztv | yts | nyaa | jackett | 其他前缀
    """
    raw = (indexer or "").strip().lower()
    if not raw:
        return "unknown"
    if raw.startswith("jackett"):
        return "jackett"
    if raw.startswith("nyaa"):
        return "nyaa"
    if raw in ("eztv", "yts"):
        return raw
    return raw.split(":", 1)[0]


def merge_by_infohash(
    items: List[ResourceItem],
    total_source_families: int,
) -> List[ResourceItem]:
    """
    按 infohash 合并：保留 seeders 最高条目，写入跨源计数与置信度。

    @param items: 各 client 原始列表（可含重复 hash）
    @param total_source_families: 本槽位参与拉取的源族总数（分母）
    @returns: 去重后的 ResourceItem 列表
    """
    denominator = max(int(total_source_families), 1)
    buckets: Dict[str, List[ResourceItem]] = {}

    for item in items:
        infohash = item.infohash.lower().strip()
        if len(infohash) != 40:
            continue
        buckets.setdefault(infohash, []).append(item)

    merged: List[ResourceItem] = []
    for group in buckets.values():
        families: Set[str] = set()
        for row in group:
            families.add(normalize_source_family(row.indexer))

        best = max(group, key=lambda row: (row.seeders, row.size_bytes))
        cross_count = len(families)
        best.cross_source_count = cross_count
        best.cross_source_confidence = round(min(cross_count / denominator, 1.0), 3)
        merged.append(best)

    return merged


def count_attempted_families(enabled: Dict[str, bool]) -> int:
    """
    统计本槽位启用的源族数量（跨源分母）。

    @param enabled: 键为源族名，值为是否参与拉取
    @returns: 启用源族数，至少为 1
    """
    total = sum(1 for active in enabled.values() if active)
    return max(total, 1)


def default_source_total(media_type: str) -> int:
    """
    按媒体类型返回默认跨源分母。

    @param media_type: tv | movie | tv_episode
    @returns: 剧集 3（eztv/nyaa/jackett），电影 2（yts/jackett）
    """
    kind = (media_type or "").lower()
    if kind in ("movie",):
        return 2
    return 3


def count_families_in_items(items: List[Any]) -> int:
    """
    统计 items 中出现的不同源族数量。

    @param items: ResourceItem 或 dict 列表
    @returns: 源族个数
    """
    families: Set[str] = set()
    for row in items:
        if isinstance(row, dict):
            indexer = str(row.get("indexer") or "")
        else:
            indexer = str(getattr(row, "indexer", "") or "")
        family = normalize_source_family(indexer)
        if family != "unknown":
            families.add(family)
    return len(families)


def compute_page_cross_source(
    items: List[Any],
    source_enabled: Optional[Dict[str, bool]] = None,
    media_type: str = "tv",
) -> tuple[int, int]:
    """
    计算页面级 Hero 跨源 badge：分子 / 分母。

    @param items: 拉取结果（合并前 raw 或合并后均可）
    @param source_enabled: 各源族是否参与拉取；无则按 items 推断分子、默认分母
    @param media_type: tv | movie
    @returns: (cross_source_count, cross_source_total)
    """
    if source_enabled:
        total = count_attempted_families(source_enabled)
        hit: Set[str] = set()
        for row in items:
            if isinstance(row, dict):
                indexer = str(row.get("indexer") or "")
            else:
                indexer = str(getattr(row, "indexer", "") or "")
            family = normalize_source_family(indexer)
            if family != "unknown" and source_enabled.get(family):
                hit.add(family)
        return len(hit), total

    count = count_families_in_items(items)
    total = default_source_total(media_type)
    return count, max(total, count, 1)
