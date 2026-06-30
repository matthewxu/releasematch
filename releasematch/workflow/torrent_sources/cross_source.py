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

from typing import Dict, List, Set

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
    if raw in ("eztv", "yts", "nyaa"):
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
