# -*- coding: utf-8 -*-
"""
Phase 1 + Phase 2 组合测速编排。

@module workflow.torrent_sources.speedtest.full_speed
"""

from __future__ import annotations

from typing import Optional

from workflow.torrent_sources.speedtest.models import FullSpeedResult
from workflow.torrent_sources.speedtest.phase1_connectivity import test_connectivity
from workflow.torrent_sources.speedtest.phase2_speed import DEFAULT_TARGET_BYTES, test_fragment_speed
from workflow.torrent_sources.speedtest.reachability import derive_reachability, format_recommended_speed


def run_full_speedtest(
    infohash: str,
    *,
    page_id: Optional[str] = None,
    phase1_timeout_sec: int = 20,
    phase2_timeout_sec: int = 30,
    target_bytes: int = DEFAULT_TARGET_BYTES,
    force_dry_run: bool = False,
    magnet_uri: Optional[str] = None,
    skip_phase2: bool = False,
) -> FullSpeedResult:
    """
    依次执行 Phase 1 连接性与 Phase 2 片段测速，并派生 S-06 / A-01 展示字段。

    @param infohash: 40 位 infohash
    @param page_id: 可选页面 ID
    @param phase1_timeout_sec: Phase 1 超时
    @param phase2_timeout_sec: Phase 2 超时
    @param target_bytes: Phase 2 目标下载字节
    @param force_dry_run: 跳过 libtorrent
    @param magnet_uri: 可选完整 magnet
    @param skip_phase2: True 时仅跑 Phase 1
    @returns: FullSpeedResult
    """
    phase1 = test_connectivity(
        infohash,
        page_id=page_id,
        timeout_sec=phase1_timeout_sec,
        force_dry_run=force_dry_run,
        magnet_uri=magnet_uri,
    )

    if skip_phase2:
        from workflow.torrent_sources.speedtest.models import FragmentSpeedResult

        phase2 = FragmentSpeedResult(
            infohash=phase1.infohash,
            page_id=page_id,
            status="skipped",
            mode=phase1.mode,
        )
    else:
        phase2 = test_fragment_speed(
            infohash,
            page_id=page_id,
            timeout_sec=phase2_timeout_sec,
            target_bytes=target_bytes,
            force_dry_run=force_dry_run,
            magnet_uri=magnet_uri,
        )

    peers_for_reach = max(phase1.peers_total, phase2.peers_total)
    if phase2.status == "ok" and peers_for_reach > 0:
        reach_status = "ok"
    elif phase1.status == "ok" and peers_for_reach > 0:
        reach_status = "ok"
    else:
        reach_status = phase1.status if phase1.status not in ("ok",) else phase2.status
    reachability = derive_reachability(peers_for_reach, reach_status)
    recommended_speed = format_recommended_speed(phase2.avg_kbps)

    return FullSpeedResult(
        phase1=phase1,
        phase2=phase2,
        recommended_speed=recommended_speed,
        reachability=reachability,
    )
