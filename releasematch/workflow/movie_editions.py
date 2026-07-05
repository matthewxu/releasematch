#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电影页多版本分组与展示辅助（渲染期，不重拉 torrent）。

@module workflow.movie_editions
@description
  将 download_resources 按 edition_type 分组，并选出每组 seed 最高条目供模板高亮。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from workflow.torrent_sources.release_parser import classify_edition, edition_label

# 电影页分组展示顺序（高 → 低）
_EDITION_ORDER: List[str] = [
    "web-dl",
    "remux",
    "bluray",
    "hdtv",
    "other",
    "cam",
]


def annotate_source_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    为单条 source 模板字典补充 edition_type / edition_label。

    @param item: DownloadResource.to_template_dict() 结果
    @returns: 同一字典（就地补充字段）
    """
    title = str(item.get("title_raw") or "")
    source = str(item.get("source") or "")
    edition = classify_edition(title, source)
    item["edition_type"] = edition
    item["edition_label"] = edition_label(edition)
    return item


def pick_edition_best(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    组内 seed 最高且 seed≥1 的条目；否则返回 seed 最高者。

    @param items: 同 edition 的 source 字典列表
    @returns: 最佳条目或 None
    """
    if not items:
        return None
    with_seed = [i for i in items if int(i.get("seeders") or 0) >= 1]
    pool = with_seed if with_seed else items
    return max(pool, key=lambda x: (int(x.get("seeders") or 0), int(x.get("size_bytes") or 0)))


def group_movie_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按版本类型分组，组内按 seeders 降序。

    @param sources: 已 annotate 的 source 字典列表
    @returns: [{"edition_type", "edition_label", "rows", "best", "count"}, ...]
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _EDITION_ORDER}
    for item in sources:
        edition = str(item.get("edition_type") or "other")
        if edition not in buckets:
            buckets[edition] = []
        buckets[edition].append(item)

    groups: List[Dict[str, Any]] = []
    for edition in _EDITION_ORDER:
        items = buckets.get(edition) or []
        if not items:
            continue
        items.sort(
            key=lambda x: (
                -int(x.get("seeders") or 0),
                -int(x.get("size_bytes") or 0),
            )
        )
        best = pick_edition_best(items)
        groups.append(
            {
                "edition_type": edition,
                "edition_label": edition_label(edition),
                "rows": items,
                "best": best,
                "count": len(items),
            }
        )
    return groups
