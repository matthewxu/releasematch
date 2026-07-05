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

import re
from typing import Any, Dict, List, Optional, Set

from workflow.torrent_sources.models import ResourceItem

# 从标题解析 S/E（fuzzy 对齐 fallback）
_SEASON_EPISODE_RE = re.compile(r"\bS(\d+)E(\d+)\b", re.IGNORECASE)

# fuzzy 指纹档位：由严到宽（S-04）
FUZZY_FINGERPRINT_MODES = ("strict", "no_group", "slot_resolution")


def normalize_source_family(indexer: str) -> str:
    """
    将 indexer 规范为跨源统计用的「源族」键。

    Jackett 各 indexer（如 thepiratebay、1337x）单独计族，不再合并为单一 ``jackett``，
    以便 Hero badge 分母可大于 3（eztv + nyaa + tpb + …）。

    @param indexer: 如 eztv、yts、nyaa、jackett:thepiratebay
    @returns: eztv | yts | nyaa | thepiratebay | 1337x | …
    """
    raw = (indexer or "").strip().lower()
    if not raw:
        return "unknown"
    if raw.startswith("jackett:"):
        slug = raw.split(":", 1)[1].strip()
        if slug and slug != "all":
            # nyaasi（Jackett id）与直连 nyaa 统一为 nyaa 族
            if slug.startswith("nyaa"):
                return "nyaa"
            return slug
        return "jackett"
    if raw.startswith("nyaa"):
        return "nyaa"
    if raw in ("eztv", "yts", "dmhy"):
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


def _item_field(item: Any, key: str, default: Any = None) -> Any:
    """
    从 ResourceItem 或 dict 读取字段。

    @param item: ResourceItem 或 dict
    @param key: 字段名
    @param default: 缺省值
    @returns: 字段值
    """
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_release_fingerprint(
    item: Any,
    *,
    media_type: str = "tv",
    slot_season: Optional[int] = None,
    slot_episode: Optional[int] = None,
    mode: str = "strict",
) -> Optional[str]:
    """
    构造 release 软对齐指纹（S-04 fuzzy）。

    档位说明（误匹配风险递增）：
    - ``strict``：S/E + resolution + source + codec + group（需可解析 group）
    - ``no_group``：去掉 group，同集同规格不同组可跨源对齐
    - ``slot_resolution``：仅 S/E + resolution（电影为 edition + resolution）；可能合并 WEB-DL 与 HDTV

    @param item: ResourceItem 或 dict
    @param media_type: tv | movie | tv_episode
    @param slot_season: 槽位季号（剧集页上下文）
    @param slot_episode: 槽位集号
    @param mode: strict | no_group | slot_resolution
    @returns: 指纹字符串；无法安全对齐时 None
    """
    from workflow.torrent_sources.release_parser import classify_edition, parse_release_title

    fingerprint_mode = (mode or "strict").strip().lower()
    if fingerprint_mode not in FUZZY_FINGERPRINT_MODES:
        fingerprint_mode = "strict"

    title = str(_item_field(item, "title_raw") or "")
    parsed = parse_release_title(title)

    group = str(_item_field(item, "release_group") or parsed.get("release_group") or "").strip().upper()
    if fingerprint_mode == "strict" and not group:
        return None

    resolution = str(_item_field(item, "resolution") or parsed.get("resolution") or "").strip().lower()
    if not resolution:
        return None

    source = str(_item_field(item, "source") or parsed.get("source") or "").strip().lower()
    codec = str(_item_field(item, "codec") or parsed.get("codec") or "").strip().lower()
    source_key = source.replace(" ", "") if source else "any"
    codec_key = codec.replace(".", "").replace(" ", "") if codec else "any"

    kind = (media_type or "").lower()
    if kind in ("movie",):
        edition = classify_edition(title, source)
        if fingerprint_mode == "slot_resolution":
            return f"m|{edition}|{resolution}"
        if fingerprint_mode == "no_group":
            return f"m|{edition}|{resolution}|{source_key}|{codec_key}"
        return f"m|{edition}|{resolution}|{source_key}|{codec_key}|{group}"

    season = _item_field(item, "season") or slot_season
    episode = _item_field(item, "episode") or slot_episode
    if season is None or episode is None:
        match = _SEASON_EPISODE_RE.search(title)
        if match:
            season, episode = int(match.group(1)), int(match.group(2))
    if season is None or episode is None:
        return None
    se = f"S{int(season):02d}E{int(episode):02d}"
    if fingerprint_mode == "slot_resolution":
        return f"tv|{se}|{resolution}"
    if fingerprint_mode == "no_group":
        return f"tv|{se}|{resolution}|{source_key}|{codec_key}"
    return f"tv|{se}|{resolution}|{source_key}|{codec_key}|{group}"


def _cap_cross_count(count: int, page_families: Set[str]) -> int:
    """
    跨源分子不得超过本页实际出现的源族数（防止宽松指纹过度计数）。

    @param count: 原始分子
    @param page_families: 本页 items 中出现的源族集合
    @returns: 钳制后的分子，至少为 1
    """
    ceiling = max(len(page_families), 1)
    return min(max(int(count), 1), ceiling)


def max_item_cross_count(items: List[Any]) -> int:
    """
    从 items 推断页面 Hero 跨源分子（取各条 cross_source_count 最大值）。

    @param items: ResourceItem 或 dict 列表
    @returns: 至少 1
    """
    best = 1
    for row in items:
        if isinstance(row, dict):
            val = int(row.get("cross_source_count") or 1)
        else:
            val = int(getattr(row, "cross_source_count", None) or 1)
        best = max(best, val)
    return best


def apply_fuzzy_cross_source(
    items: List[ResourceItem],
    total_source_families: int,
    *,
    media_type: str = "tv",
    slot_season: Optional[int] = None,
    slot_episode: Optional[int] = None,
) -> List[ResourceItem]:
    """
    在 hash 级跨源计数基础上，用多档 release 指纹提升 S-04 cross_source_count。

    依次尝试 strict → no_group → slot_resolution，取各档与 hash 级的最大源族命中数；
    最终结果钳制在本页实际源族数以内。

    @param items: merge_by_infohash 后的列表
    @param total_source_families: 跨源分母 M
    @param media_type: tv | movie | tv_episode
    @param slot_season: 剧集槽位季号
    @param slot_episode: 剧集槽位集号
    @returns: 就地更新 cross_source_count/confidence 后的同一列表
    """
    denominator = max(int(total_source_families), 1)
    page_families: Set[str] = set()
    hash_families: Dict[str, Set[str]] = {}
    fp_families: Dict[str, Set[str]] = {}
    item_fps: Dict[str, Dict[str, Optional[str]]] = {}

    for row in items:
        infohash = row.infohash.lower().strip()
        family = normalize_source_family(row.indexer)
        if family != "unknown":
            page_families.add(family)
        hash_families.setdefault(infohash, set()).add(family)
        item_fps[infohash] = {}
        for fp_mode in FUZZY_FINGERPRINT_MODES:
            fingerprint = build_release_fingerprint(
                row,
                media_type=media_type,
                slot_season=slot_season,
                slot_episode=slot_episode,
                mode=fp_mode,
            )
            item_fps[infohash][fp_mode] = fingerprint
            if fingerprint:
                fp_key = f"{fp_mode}:{fingerprint}"
                fp_families.setdefault(fp_key, set()).add(family)

    for row in items:
        infohash = row.infohash.lower().strip()
        hash_count = len(hash_families.get(infohash, set())) or 1
        fuzzy_count = hash_count
        for fp_mode in FUZZY_FINGERPRINT_MODES:
            fingerprint = item_fps.get(infohash, {}).get(fp_mode)
            if fingerprint:
                fp_key = f"{fp_mode}:{fingerprint}"
                fuzzy_count = max(fuzzy_count, len(fp_families.get(fp_key, set())))
        fuzzy_count = _cap_cross_count(fuzzy_count, page_families)
        row.cross_source_count = fuzzy_count
        row.cross_source_confidence = round(min(fuzzy_count / denominator, 1.0), 3)

    return items


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
    按媒体类型返回默认跨源分母（无 source_enabled 时的回退值）。

    @param media_type: tv | movie | tv_episode
    @returns: 剧集 4（eztv/nyaa/tpb/1337x），电影 3（yts/tpb/1337x）
    """
    kind = (media_type or "").lower()
    if kind in ("movie",):
        return 3
    return 4


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
