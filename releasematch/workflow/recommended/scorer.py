#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recommended Release 评分引擎 v1（规则版）。

@module workflow.recommended.scorer
@description
  本站规则：
    - Group tier 权重（L0 > L1 > L2 > L3 > L4），数据来自 data/groups.yaml
    - seeders 权重
    - 跨源置信度 cross_source_count
    - 同分 tie-break：seeders → 分辨率（1080p 优先）→ 跨源数 → tier

  R1 目标：对单槽 ResourceItem 列表选出 is_recommended=1 及 recommend_reason。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from workflow.recommended.groups_registry import infer_group_tier, lookup_group

# Group tier 默认权重
_GROUP_TIER_WEIGHT: Dict[str, float] = {
    "L0": 1.0,
    "L1": 0.85,
    "L2": 0.6,
    "L3": 0.3,
    "L4": 0.1,
}


@dataclass
class Order:
    """单条 release 评分结果。"""

    infohash: str
    title_raw: str
    score: float
    is_recommended: bool
    recommend_reason: str
    group_tier: str
    canonical_group: str = ""


def _resolution_rank(resolution: str, title_raw: str = "") -> int:
    """
    分辨率排序权重（1080p 为通用推荐甜点）。

    @param resolution: 如 1080p
    @param title_raw: 标题回退解析
    @returns: 越大越优先
    """
    text = f"{resolution} {title_raw}".lower()
    if re.search(r"1080|1920", text):
        return 50
    if re.search(r"2160|4k|uhd", text):
        return 40
    if re.search(r"720", text):
        return 30
    if re.search(r"480|sd\b", text):
        return 20
    return 10


def _tier_sort_weight(tier: str) -> int:
    """
    tier 转排序整数（L0 最高）。

    @param tier: L0~L4
    @returns: 排序权重
    """
    return {"L0": 5, "L1": 4, "L2": 3, "L3": 2, "L4": 1}.get(tier, 0)


def score_item(item: Dict[str, Any]) -> float:
    """
    对单条 ResourceItem 字典计算推荐分。

    @param item: 含 release_group、seeders、cross_source_count 等字段
    @returns: 0~100 分
    """
    group = str(item.get("release_group") or "")
    tier = infer_group_tier(group)
    tier_w = _GROUP_TIER_WEIGHT.get(tier, 0.1)

    seeders = int(item.get("seeders") or 0)
    seeder_w = min(seeders / 50.0, 1.0)

    cross = int(item.get("cross_source_count") or 1)
    cross_w = min(cross / 3.0, 1.0)

    raw = tier_w * 50.0 + seeder_w * 30.0 + cross_w * 20.0
    return round(raw, 2)


def build_recommend_reason(item: Dict[str, Any], tier: str, canonical_group: str = "") -> str:
    """
    生成推荐理由文本（嵌入页面 HTML，供 IG）。

    @param item: ResourceItem 字典
    @param tier: Group 档位
    @param canonical_group: YAML 中的规范组名
    @returns: 一行或多行说明
    """
    parts: List[str] = []
    group = canonical_group or item.get("release_group") or "Unknown"
    if tier in ("L0", "L1"):
        parts.append(f"Verified Group {group}（{tier} 档信誉）")
    elif tier == "L2":
        parts.append(f"Community Group {group}（{tier} 档）")
    resolution = item.get("resolution")
    if resolution:
        parts.append(f"{resolution} 画质")
    source = item.get("source")
    if source:
        parts.append(f"来源 {source}")
    seeders = item.get("seeders")
    if seeders is not None:
        parts.append(f"当前 {seeders} seeders")
    cross = item.get("cross_source_count")
    if cross and cross > 1:
        parts.append(f"跨 {cross} 个数据源交叉验证")
    return "；".join(parts) if parts else "综合评分最高"


def _sort_key(item: Dict[str, Any], order: Order) -> Tuple[float, int, int, int, int]:
    """
    排序键：主分降序，同分按 seeders / 分辨率 / 跨源 / tier 依次决胜。

    @param item: 原始 ResourceItem 字典
    @param order: 已算分的 Order
    @returns: 用于 sort 的元组（取负实现降序）
    """
    seeders = int(item.get("seeders") or 0)
    cross = int(item.get("cross_source_count") or 1)
    res_rank = _resolution_rank(str(item.get("resolution") or ""), str(item.get("title_raw") or ""))
    tier_w = _tier_sort_weight(order.group_tier)
    return (-order.score, -seeders, -res_rank, -cross, -tier_w)


def rank_items(items: List[Dict[str, Any]]) -> List[Order]:
    """
    对槽位内所有 release 排序并标记 Recommended。

    @param items: ResourceItem 字典列表
    @returns: 按 score 降序的 Order 列表
    """
    paired: List[Tuple[Dict[str, Any], Order]] = []
    for it in items:
        release_group = str(it.get("release_group") or "")
        canonical, tier = lookup_group(release_group)
        if not canonical:
            tier = infer_group_tier(release_group)
        sc = score_item(it)
        order = Order(
            infohash=str(it.get("infohash") or ""),
            title_raw=str(it.get("title_raw") or ""),
            score=sc,
            is_recommended=False,
            recommend_reason=build_recommend_reason(it, tier, canonical),
            group_tier=tier,
            canonical_group=canonical,
        )
        paired.append((it, order))

    paired.sort(key=lambda pair: _sort_key(pair[0], pair[1]))
    orders = [o for _, o in paired]
    if orders:
        orders[0].is_recommended = True
    return orders


def score_slot(
    tmdb_id: int,
    media_type: str = "tv",
    season: Optional[int] = None,
    episode: Optional[int] = None,
    force: bool = False,
    accounts_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    对真实槽位拉取 ResourceItem 并排序标记 Recommended。

    @param tmdb_id: TMDB 作品 ID
    @param media_type: tv | movie
    @param season: 季号（剧集必填）
    @param episode: 集号（剧集必填）
    @param force: 是否忽略 torrent 缓存
    @param accounts_path: 可选 accounts.local.json 路径
    @returns: 含 fetch 摘要与 ranked 列表的 JSON 字典
    """
    from workflow.metadata.external_ids import resolve_external_ids
    from workflow.torrent_sources.fetch_service import FetchService
    from workflow.torrent_sources.models import FetchMode, FetchRequest, MediaType

    mt = MediaType.MOVIE if media_type == "movie" else MediaType.TV
    ext = resolve_external_ids(tmdb_id=tmdb_id, media_type=media_type)

    request = FetchRequest(
        tmdb_id=tmdb_id,
        media_type=mt,
        season=season,
        episode=episode,
        imdb_id=ext.get("imdb_id"),
        tvdb_id=ext.get("tvdb_id"),
        mode=FetchMode.ON_DEMAND,
        force=force,
    )

    service = FetchService(accounts_path=accounts_path)
    fetch_result = service.fetch_slot(request)

    item_dicts = [i.to_dict() for i in fetch_result.items]
    ranked = rank_items(item_dicts)

    return {
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "season": season,
        "episode": episode,
        "external_ids": ext,
        "fetch": {
            "count": len(fetch_result.items),
            "cached": fetch_result.cached,
            "error": fetch_result.error,
            "cache_key": request.cache_key(),
        },
        "ranked": [
            {
                "infohash": o.infohash,
                "title_raw": o.title_raw,
                "score": o.score,
                "is_recommended": o.is_recommended,
                "recommend_reason": o.recommend_reason,
                "group_tier": o.group_tier,
                "canonical_group": o.canonical_group or None,
            }
            for o in ranked
        ],
    }


def score_slot_demo(
    tmdb_id: int,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Demo：无真实 torrent 数据时展示评分逻辑示例。

    @param tmdb_id: TMDB ID
    @param season: 季号
    @param episode: 集号
    @returns: 评分结果 JSON
    """
    demo_items = [
        {
            "infohash": "aaa" * 13 + "a",
            "title_raw": "Breaking.Bad.S04E06.1080p.WEB-DL.DDP5.1.H.264-NTb",
            "release_group": "NTb",
            "source": "WEB-DL",
            "resolution": "1080p",
            "seeders": 24,
            "cross_source_count": 3,
        },
        {
            "infohash": "bbb" * 13 + "b",
            "title_raw": "Breaking.Bad.S04E06.720p.YIFY",
            "release_group": "YIFY",
            "source": "WEB-DL",
            "resolution": "720p",
            "seeders": 120,
            "cross_source_count": 1,
        },
    ]
    ranked = rank_items(demo_items)
    return {
        "tmdb_id": tmdb_id,
        "season": season,
        "episode": episode,
        "ranked": [
            {
                "title_raw": o.title_raw,
                "score": o.score,
                "is_recommended": o.is_recommended,
                "recommend_reason": o.recommend_reason,
                "group_tier": o.group_tier,
                "canonical_group": o.canonical_group or None,
            }
            for o in ranked
        ],
        "note": "Demo 数据；接入 torrent_sources 后使用真实 items",
    }
