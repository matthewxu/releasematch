# -*- coding: utf-8 -*-
"""
测速结果派生：可达性等级与速度展示格式（S-06 / S-07 / A-01）。

@module workflow.torrent_sources.speedtest.reachability
"""

from __future__ import annotations


def derive_reachability(peers_total: int, status: str = "ok") -> str:
    """
    由 Phase 1 peer 数派生可达性等级（A-01）。

    @param peers_total: 观测 peer 总数
    @param status: 测速状态；timeout/error 视为不可达
    @returns: 高 | 中 | 低 | 不可达
    """
    if status in ("timeout", "error"):
        return "不可达"
    if peers_total >= 10:
        return "高"
    if peers_total >= 3:
        return "中"
    if peers_total >= 1:
        return "低"
    return "不可达"


def format_recommended_speed(avg_kbps: float) -> str:
    """
    将平均 KB/s 格式化为页面展示文案（S-06 → slot_speed_summary.recommended_speed）。

    @param avg_kbps: 平均下载速度（KiB/s）
    @returns: 如「4.2 MB/s」或「850 KB/s」；无效时空串
    """
    if avg_kbps <= 0:
        return ""
    mb_per_sec = avg_kbps / 1024.0
    if mb_per_sec >= 1.0:
        return f"{mb_per_sec:.1f} MB/s"
    return f"{int(round(avg_kbps))} KB/s"
