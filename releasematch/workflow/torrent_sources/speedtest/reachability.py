# -*- coding: utf-8 -*-
"""
测速结果派生：可达性等级与速度展示格式（S-06 / S-07 / A-01）。

@module workflow.torrent_sources.speedtest.reachability
"""

from __future__ import annotations

from typing import Dict


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


def reachability_threshold_text(peers_total: int, status: str = "ok") -> str:
    """
    返回当前 peers 对应的等级阈值说明（A-01 派生规则）。

    @param peers_total: 观测 peer 总数
    @param status: 测速状态
    @returns: 如「≥10 → 高；本次 30」
    """
    if status in ("timeout", "error"):
        return "timeout/error → 不可达"
    if peers_total >= 10:
        return f"≥10 → 高；本次 {peers_total}"
    if peers_total >= 3:
        return f"3–9 → 中；本次 {peers_total}"
    if peers_total >= 1:
        return f"1–2 → 低；本次 {peers_total}"
    return "0 peers → 不可达"


def format_peers_summary_display(peers_total: int, peers_reachable: int) -> Dict[str, str]:
    """
    格式化 peer 观测与连接率展示（A-02）。

    @param peers_total: 观测 peer 总数
    @param peers_reachable: 已连接 peer 数
    @returns: peers_total_display、peers_reachable_display、connect_rate_pct、peers_pair_display、connect_rate_display
    """
    if peers_total > 0 and peers_reachable >= 0:
        rate_pct = int(round(peers_reachable * 100.0 / peers_total))
        connect_rate_pct = f"{rate_pct}%"
        connect_rate_display = f"{connect_rate_pct}（{peers_reachable}/{peers_total}）"
        peers_pair_display = f"{peers_reachable} / {peers_total}"
    else:
        connect_rate_pct = "—"
        connect_rate_display = "—"
        peers_pair_display = "—"

    return {
        "peers_total_display": str(peers_total) if peers_total >= 0 else "—",
        "peers_reachable_display": str(peers_reachable) if peers_reachable >= 0 else "—",
        "connect_rate_pct": connect_rate_pct,
        "peers_pair_display": peers_pair_display,
        "connect_rate_display": connect_rate_display,
    }


def format_reachability_display(
    reachability: str,
    *,
    peers_total: int,
    peers_reachable: int,
    status: str = "ok",
) -> Dict[str, str]:
    """
    将 A-01 等级扩展为含具体 peer 数值的展示文案。

    @param reachability: 高/中/低/不可达
    @param peers_total: 观测 peer 总数（A-02）
    @param peers_reachable: 已连接 peer 数
    @param status: 测速状态
    @returns: reachability_display、reachability_detail、reachability_rule、connect_rate_display
    """
    if peers_total > 0 and peers_reachable >= 0:
        peers_summary = format_peers_summary_display(peers_total, peers_reachable)
        connect_rate_display = peers_summary["connect_rate_display"]
        rate_pct = peers_summary["connect_rate_pct"]
    else:
        connect_rate_display = "—"
        rate_pct = "—"

    if status in ("timeout", "error"):
        display = f"{reachability}（{status}，0 peers 可用）"
        detail = f"测速状态 {status}；Phase 1/2 未获得有效 peer 连接。"
    elif peers_total <= 0:
        display = f"{reachability}（观测 0 peers）"
        detail = "libtorrent 未观测到可用 peer；等级派生为不可达。"
    else:
        display = (
            f"{reachability} · 观测 {peers_total} peers · 已连 {peers_reachable} · 连接率 {rate_pct}"
        )
        detail = (
            f"A-01 由 peers_total 派生：{reachability_threshold_text(peers_total, status)}；"
            f"A-02 peers_reachable={peers_reachable} / peers_total={peers_total}。"
        )

    return {
        "reachability_display": display,
        "reachability_detail": detail,
        "reachability_rule": "规则：≥10 高 · 3–9 中 · 1–2 低 · 0/error 不可达",
        "connect_rate_display": connect_rate_display,
    }


def format_speed_pair_display(avg_kbps: float, max_kbps: float) -> Dict[str, str]:
    """
    格式化均速与峰值双值展示（S-06）。

    @param avg_kbps: 平均 KiB/s
    @param max_kbps: 峰值 KiB/s
    @returns: avg_speed、max_speed、speed_pair_display、speed_spread_display
    """
    avg_text = format_recommended_speed(avg_kbps)
    max_text = format_recommended_speed(max_kbps)
    pair = f"均速 {avg_text} · 峰值 {max_text}"
    spread = ""
    if avg_kbps > 0 and max_kbps > 0:
        ratio = max_kbps / avg_kbps
        spread = f"峰值/均速 ×{ratio:.1f}"
    return {
        "avg_speed": avg_text,
        "max_speed": max_text,
        "speed_pair_display": pair,
        "speed_spread_display": spread,
    }


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
