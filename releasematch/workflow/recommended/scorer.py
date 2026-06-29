#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recommended Release 评分引擎 v1（规则版）。

@module workflow.recommended.scorer
@description
  原规划通过 subtitle_primary_release 与字幕 Primary 对齐评分。
  独立 Release 导航站改为本站规则：
    - Group tier 权重（L0 > L1 > L2 > L3）
    - seeders 权重
    - 跨源置信度 cross_source_count
    - 编码/来源规格（编码分析 Phase 1 接入后增强）

  R1 目标：对单槽 ResourceItem 列表选出 is_recommended=1 及 recommend_reason。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Group tier 默认权重（完整库见 R1 groups.yaml）
_GROUP_TIER_WEIGHT: Dict[str, float] = {
    "L0": 1.0,
    "L1": 0.85,
    "L2": 0.6,
    "L3": 0.3,
    "L4": 0.1,
}

# 已知优质组 Demo 子集（R1 扩展为 YAML 100+ 组）
_KNOWN_GROUPS: Dict[str, str] = {
    "NTb": "L0",
    "CtrlHD": "L0",
    "HiFi": "L1",
    "YIFY": "L3",
    "YTS": "L3",
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


def infer_group_tier(release_group: str) -> str:
    """
    推断压制组信誉档位。

    @param release_group: 组名
    @returns: L0~L4 或 L4（未知）
    """
    if not release_group:
        return "L4"
    key = release_group.strip()
    for name, tier in _KNOWN_GROUPS.items():
        if name.lower() == key.lower():
            return tier
    return "L4"


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
    seeder_w = min(seeders / 50.0, 1.0)  # 50 seeders 封顶

    cross = int(item.get("cross_source_count") or 1)
    cross_w = min(cross / 3.0, 1.0)  # 3 源交叉封顶

    # 权重：Group 50% + seeders 30% + 跨源 20%
    raw = tier_w * 50.0 + seeder_w * 30.0 + cross_w * 20.0
    return round(raw, 2)


def build_recommend_reason(item: Dict[str, Any], tier: str) -> str:
    """
    生成推荐理由文本（嵌入页面 HTML，供 IG）。

    @param item: ResourceItem 字典
    @param tier: Group 档位
    @returns: 一行或多行说明
    """
    parts: List[str] = []
    group = item.get("release_group") or "Unknown"
    if tier in ("L0", "L1"):
        parts.append(f"Verified Group {group}（{tier} 档信誉）")
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


def rank_items(items: List[Dict[str, Any]]) -> List[Order]:
    """
    对槽位内所有 release 排序并标记 Recommended。

    @param items: ResourceItem 字典列表
    @returns: 按 score 降序的 Order 列表
    """
    orders: List[Order] = []
    for it in items:
        tier = infer_group_tier(str(it.get("release_group") or ""))
        sc = score_item(it)
        orders.append(
            Order(
                infohash=str(it.get("infohash") or ""),
                title_raw=str(it.get("title_raw") or ""),
                score=sc,
                is_recommended=False,
                recommend_reason=build_recommend_reason(it, tier),
                group_tier=tier,
            )
        )

    orders.sort(key=lambda o: o.score, reverse=True)
    if orders:
        orders[0].is_recommended = True
    return orders


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
            "seeders": 24,
            "cross_source_count": 3,
        },
        {
            "infohash": "bbb" * 13 + "b",
            "title_raw": "Breaking.Bad.S04E06.720p.YIFY",
            "release_group": "YIFY",
            "source": "WEB-DL",
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
            }
            for o in ranked
        ],
        "note": "Demo 数据；接入 torrent_sources 后使用真实 items",
    }
