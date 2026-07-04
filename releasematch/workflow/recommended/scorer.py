#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recommended Release 评分引擎 v1.2（规则版 · 剧集 v1.1 + 电影分化）。

@module workflow.recommended.scorer
@description
  本站规则（R1）：
    - **可下载性优先**：主分中 seeders 权重最高（50%）
    - Group tier 权重（L0 > L1 > L2 > L3 > L4），数据来自 data/groups.yaml（25%）
    - 跨源置信度 cross_source_count（25%）
    - 同分 tie-break：**分辨率** → seeders → 跨源数 → tier

  目标：对单槽 ResourceItem 列表选出 is_recommended=1 及 recommend_reason。

  **电影 vs 剧集：**
    - 剧集（默认）：seeders 50% · tier 25% · cross 25%
    - 电影：seeders 55% · tier 15% · cross 30%；有 seed≥1 时优先于 0 seed；
      tie-break 增加版本类型（WEB-DL/BluRay > CAM/TS）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from workflow.recommended.groups_registry import infer_group_tier, lookup_group

# Group tier 默认权重（映射到 0~1 后乘以 _SCORE_WEIGHT_TIER）
_GROUP_TIER_WEIGHT: Dict[str, float] = {
    "L0": 1.0,
    "L1": 0.85,
    "L2": 0.6,
    "L3": 0.3,
    "L4": 0.1,
}

# 主分三项权重（合计 100）：可下载性（seeders）最高
_SCORE_WEIGHT_SEEDERS: float = 50.0
_SCORE_WEIGHT_TIER: float = 25.0
_SCORE_WEIGHT_CROSS: float = 25.0

# seeders 归一化上限：达到此做种数视为满分
_SEEDERS_FULL_SCORE_AT: int = 50

_MEDIA_KIND_TV: str = "tv"
_MEDIA_KIND_MOVIE: str = "movie"

# 电影：可下载性与跨源权重更高，tier 降权（YTS 等 L4 高 seed 不应被 tier 压过）
_MOVIE_SCORE_WEIGHT_SEEDERS: float = 55.0
_MOVIE_SCORE_WEIGHT_TIER: float = 15.0
_MOVIE_SCORE_WEIGHT_CROSS: float = 30.0

# 电影 Recommended 门槛：存在 seed≥1 的条目时，不推 0 seed
_MIN_MOVIE_SEEDERS_FOR_REC: int = 1


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


def _edition_rank(title_raw: str) -> int:
    """
    电影版本类型排序（WEB-DL/BluRay 优于 CAM/TS）。

    @param title_raw: release 标题
    @returns: 越大越优先
    """
    text = (title_raw or "").lower()
    if re.search(r"\bcam\b|telesync|\bts\b|hdts|hdcam|telecine", text):
        return 5
    if "web-dl" in text or "webdl" in text or "web dl" in text:
        return 50
    if "bluray" in text or "blu-ray" in text or "blu ray" in text:
        return 45
    if "remux" in text:
        return 40
    if re.search(r"2160|4k|uhd", text):
        return 35
    return 25


def score_item(item: Dict[str, Any], media_kind: str = _MEDIA_KIND_TV) -> float:
    """
    对单条 ResourceItem 字典计算推荐分（可下载性优先）。

    公式：tier×W_t + seeders×W_s + cross×W_c（各项先归一化到 0~1）。

    @param item: 含 release_group、seeders、cross_source_count 等字段
    @param media_kind: tv | movie
    @returns: 0~100 分
    """
    group = str(item.get("release_group") or "")
    tier = infer_group_tier(group)
    tier_w = _GROUP_TIER_WEIGHT.get(tier, 0.1)

    seeders = int(item.get("seeders") or 0)
    seeder_w = min(seeders / float(_SEEDERS_FULL_SCORE_AT), 1.0)

    cross = int(item.get("cross_source_count") or 1)
    cross_w = min(cross / 3.0, 1.0)

    if media_kind == _MEDIA_KIND_MOVIE:
        w_t, w_s, w_c = (
            _MOVIE_SCORE_WEIGHT_TIER,
            _MOVIE_SCORE_WEIGHT_SEEDERS,
            _MOVIE_SCORE_WEIGHT_CROSS,
        )
    else:
        w_t, w_s, w_c = _SCORE_WEIGHT_TIER, _SCORE_WEIGHT_SEEDERS, _SCORE_WEIGHT_CROSS

    raw = tier_w * w_t + seeder_w * w_s + cross_w * w_c
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


def _sort_key(
    item: Dict[str, Any],
    order: Order,
    media_kind: str = _MEDIA_KIND_TV,
) -> Tuple[float, int, int, int, int, int]:
    """
    排序键：主分降序，同分按版本/分辨率 → seeders → 跨源 → tier 决胜。

    @param item: 原始 ResourceItem 字典
    @param order: 已算分的 Order
    @param media_kind: tv | movie
    @returns: 用于 sort 的元组（取负实现降序）
    """
    seeders = int(item.get("seeders") or 0)
    cross = int(item.get("cross_source_count") or 1)
    res_rank = _resolution_rank(str(item.get("resolution") or ""), str(item.get("title_raw") or ""))
    tier_w = _tier_sort_weight(order.group_tier)
    edition = _edition_rank(str(item.get("title_raw") or "")) if media_kind == _MEDIA_KIND_MOVIE else 0
    return (-order.score, -edition, -res_rank, -seeders, -cross, -tier_w)


def _mark_recommended(
    orders: List[Order],
    items_by_hash: Dict[str, Dict[str, Any]],
    media_kind: str,
) -> None:
    """
    标记唯一 Recommended：电影在有 seed≥1 时跳过 0 seed 条目。

    @param orders: 已排序 Order 列表
    @param items_by_hash: infohash → item 字典
    @param media_kind: tv | movie
    @returns: None
    """
    if not orders:
        return
    if media_kind == _MEDIA_KIND_MOVIE:
        for order in orders:
            item = items_by_hash.get(order.infohash, {})
            if int(item.get("seeders") or 0) >= _MIN_MOVIE_SEEDERS_FOR_REC:
                order.is_recommended = True
                return
    orders[0].is_recommended = True


def rank_items(
    items: List[Dict[str, Any]],
    media_kind: str = _MEDIA_KIND_TV,
) -> List[Order]:
    """
    对槽位内所有 release 排序并标记 Recommended。

    @param items: ResourceItem 字典列表
    @param media_kind: tv | movie（电影使用独立权重与 seed 门禁）
    @returns: 按 score 降序的 Order 列表
    """
    paired: List[Tuple[Dict[str, Any], Order]] = []
    for it in items:
        release_group = str(it.get("release_group") or "")
        canonical, tier = lookup_group(release_group)
        if not canonical:
            tier = infer_group_tier(release_group)
        sc = score_item(it, media_kind=media_kind)
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

    paired.sort(key=lambda pair: _sort_key(pair[0], pair[1], media_kind))
    orders = [o for _, o in paired]
    items_by_hash = {str(it.get("infohash") or ""): it for it in items}
    _mark_recommended(orders, items_by_hash, media_kind)
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
    ranked = rank_items(item_dicts, media_kind=media_type)

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
