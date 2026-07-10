# -*- coding: utf-8 -*-
"""
ReleaseMatch Grab 指数 — 本站实测综合评分（0–100）。

@module workflow.torrent_sources.speedtest.grab_index
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional


# 指数对外名称（页面优先展示）
GRAB_INDEX_NAME = "RM Grab 指数"
GRAB_INDEX_TAGLINE = "ReleaseMatch 实测综合分"


def _score_speed(avg_kbps: float, max_kbps: float = 0.0) -> int:
    """
    速度维度得分（S-06）：均速为主，峰值微调。

    @param avg_kbps: 片段均速 KiB/s
    @param max_kbps: 片段峰值 KiB/s
    @returns: 0–100 整数分
    """
    if avg_kbps <= 0:
        return 0
    # 对数曲线：1 KB/s≈15，10≈35，50≈55，200≈75，1024≈90，5120≈100
    base = min(100.0, 15.0 * math.log10(max(avg_kbps, 0.5) + 1.0))
    if max_kbps > avg_kbps * 2:
        base = min(100.0, base + 5.0)
    return int(round(base))


def _score_reachability(reachability: str, status: str = "ok") -> int:
    """
    可达性维度得分（A-01）。

    @param reachability: 高/中/低/不可达
    @param status: 测速状态
    @returns: 0–100 整数分
    """
    if status in ("timeout", "error"):
        return 0
    mapping = {"高": 100, "中": 65, "低": 35, "不可达": 0}
    return mapping.get(reachability, 0)


def _score_connect_rate(peers_total: int, peers_reachable: int) -> int:
    """
    连接率维度得分（A-02）。

    @param peers_total: 观测 peer 总数
    @param peers_reachable: 已连接 peer 数
    @returns: 0–100 整数分
    """
    if peers_total <= 0 or peers_reachable < 0:
        return 0
    return int(round(min(100.0, peers_reachable * 100.0 / peers_total)))


def _score_freshness(freshness_class: str, validity_level: str = "") -> int:
    """
    测速时效维度得分（A-03）。

    @param freshness_class: fresh/valid/stale/aged/unknown
    @param validity_level: 高/中/低/待确认
    @returns: 0–100 整数分
    """
    base_map = {
        "fresh": 100,
        "valid": 78,
        "stale": 42,
        "aged": 12,
        "unknown": 0,
    }
    base = base_map.get(freshness_class, 0)
    if validity_level in ("低", "待确认"):
        base = max(0, base - 15)
    elif validity_level == "中":
        base = max(0, base - 5)
    return base


def _tier_from_score(score: int) -> Dict[str, str]:
    """
    由总分映射等级文案与 CSS 类名。

    @param score: 0–100 综合分
    @returns: tier、tier_label、tier_class
    """
    if score >= 90:
        return {"tier": "excellent", "tier_label": "极佳", "tier_class": "excellent"}
    if score >= 75:
        return {"tier": "great", "tier_label": "优秀", "tier_class": "great"}
    if score >= 60:
        return {"tier": "good", "tier_label": "良好", "tier_class": "good"}
    if score >= 40:
        return {"tier": "fair", "tier_label": "一般", "tier_class": "fair"}
    if score >= 20:
        return {"tier": "weak", "tier_label": "偏弱", "tier_class": "weak"}
    return {"tier": "poor", "tier_label": "较差", "tier_class": "poor"}


def compute_grab_index(
    *,
    avg_kbps: float,
    max_kbps: float = 0.0,
    reachability: str = "",
    peers_total: int = 0,
    peers_reachable: int = 0,
    status: str = "ok",
    freshness_class: str = "unknown",
    validity_level: str = "",
) -> Dict[str, Any]:
    """
    计算 RM Grab 指数及分项 breakdown。

    权重：速度 35% · 可达性 25% · 连接率 20% · 时效 20%

    @param avg_kbps: 片段均速 KiB/s
    @param max_kbps: 片段峰值 KiB/s
    @param reachability: A-01 等级
    @param peers_total: 观测 peers
    @param peers_reachable: 已连 peers
    @param status: 测速状态
    @param freshness_class: A-03 新鲜度类
    @param validity_level: A-03 效力等级
    @returns: score、tier_label、breakdown、summary 等展示字段
    """
    speed_pts = _score_speed(avg_kbps, max_kbps)
    reach_pts = _score_reachability(reachability, status)
    connect_pts = _score_connect_rate(peers_total, peers_reachable)
    fresh_pts = _score_freshness(freshness_class, validity_level)

    score = int(round(
        speed_pts * 0.35
        + reach_pts * 0.25
        + connect_pts * 0.20
        + fresh_pts * 0.20
    ))
    score = max(0, min(100, score))
    tier = _tier_from_score(score)

    breakdown = [
        {"key": "speed", "label": "速度", "score": speed_pts, "weight_pct": 35},
        {"key": "reachability", "label": "可达性", "score": reach_pts, "weight_pct": 25},
        {"key": "connect", "label": "连接率", "score": connect_pts, "weight_pct": 20},
        {"key": "freshness", "label": "时效", "score": fresh_pts, "weight_pct": 20},
    ]

    summary_parts = []
    if speed_pts >= 60:
        summary_parts.append("速度尚可")
    elif speed_pts > 0:
        summary_parts.append("速度偏低")
    if reach_pts >= 65:
        summary_parts.append(f"可达性{reachability or '—'}")
    elif reach_pts > 0:
        summary_parts.append("可达性一般")
    if connect_pts >= 50:
        summary_parts.append(f"连接率 {connect_pts}%")
    elif peers_total > 0:
        summary_parts.append("连接率偏低")
    if fresh_pts >= 78:
        summary_parts.append("数据新鲜")
    elif fresh_pts >= 42:
        summary_parts.append("数据有效")
    elif fresh_pts > 0:
        if freshness_class in ("aged", "expired"):
            summary_parts.append("数据较久")
        else:
            summary_parts.append("数据陈旧")

    return {
        "grab_index_name": GRAB_INDEX_NAME,
        "grab_index_tagline": GRAB_INDEX_TAGLINE,
        "grab_index_score": score,
        "grab_index_display": str(score),
        "grab_index_tier": tier["tier"],
        "grab_index_tier_label": tier["tier_label"],
        "grab_index_tier_class": tier["tier_class"],
        "grab_index_summary": " · ".join(summary_parts) if summary_parts else "尚无足够实测数据",
        "grab_index_breakdown": breakdown,
        "grab_index_has_data": avg_kbps > 0 or peers_total > 0,
    }


def format_grab_index_display(grab: Dict[str, Any]) -> str:
    """
    单行 Grab 指数展示文案。

    @param grab: compute_grab_index 返回值
    @returns: 如「RM Grab 指数 72（良好）· 速度尚可 · …」
    """
    if not grab.get("grab_index_has_data"):
        return f"{grab.get('grab_index_name', GRAB_INDEX_NAME)} — 待测速"
    return (
        f"{grab.get('grab_index_name')} {grab.get('grab_index_score')}（{grab.get('grab_index_tier_label')}）"
        f" · {grab.get('grab_index_summary')}"
    )
