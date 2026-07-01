# -*- coding: utf-8 -*-
"""
测速结果持久化与 slot_speed_summary 聚合（S-06 / S-07）。

@module workflow.torrent_sources.speedtest.store_service
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from workflow.torrent_sources.speedtest.models import FullSpeedResult


def persist_speedtest_results(
    full: FullSpeedResult,
    *,
    page_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    将 Phase 1 / Phase 2 结果写入 MySQL，并 upsert 槽位测速摘要。

    @param full: 完整测速结果
    @param page_id: 页面 ID；缺省用 phase1/phase2 中的 page_id
    @returns: 写入摘要 JSON 字典
    @raises RuntimeError: MySQL 未配置
    """
    from workflow.config import release_mysql_configured
    from workflow.storage.mysql_store import MySQLStore

    if not release_mysql_configured():
        raise RuntimeError("MySQL 未配置；请设置 RELEASE_MYSQL_* 环境变量")

    slot_page_id = page_id or full.phase1.page_id or full.phase2.page_id
    store = MySQLStore()

    phase1_id = str(uuid.uuid4())
    phase2_id = str(uuid.uuid4())

    store.insert_speedtest_result(
        result_id=phase1_id,
        infohash=full.phase1.infohash,
        page_id=slot_page_id,
        phase=1,
        peers_reachable=full.phase1.peers_reachable,
        peers_total=full.phase1.peers_total,
        avg_kbps=0.0,
        max_kbps=0.0,
        latency_ms=0,
        status=full.phase1.status,
    )

    store.insert_speedtest_result(
        result_id=phase2_id,
        infohash=full.phase2.infohash,
        page_id=slot_page_id,
        phase=2,
        peers_reachable=full.phase2.peers_reachable,
        peers_total=full.phase2.peers_total,
        avg_kbps=full.phase2.avg_kbps,
        max_kbps=full.phase2.max_kbps,
        latency_ms=full.phase2.latency_ms,
        status=full.phase2.status,
    )

    summary_written = False
    if slot_page_id:
        store.upsert_slot_speed_summary(
            page_id=slot_page_id,
            recommended_infohash=full.phase2.infohash,
            recommended_speed=full.recommended_speed or "",
            reachability=full.reachability,
        )
        summary_written = True

    return {
        "page_id": slot_page_id,
        "phase1_result_id": phase1_id,
        "phase2_result_id": phase2_id,
        "recommended_speed": full.recommended_speed,
        "reachability": full.reachability,
        "slot_speed_summary_written": summary_written,
    }


def speedtest_recommended_slot(
    page_id: str,
    *,
    phase1_timeout_sec: int = 20,
    phase2_timeout_sec: int = 30,
    target_bytes: int = 1_048_576,
    force_dry_run: bool = False,
    write_mysql: bool = False,
) -> Dict[str, Any]:
    """
    对 MySQL 槽位中 is_recommended=1 的 magnet 执行完整测速。

    @param page_id: 如 tv:1396:s04e06
    @param phase1_timeout_sec: Phase 1 超时
    @param phase2_timeout_sec: Phase 2 超时
    @param target_bytes: Phase 2 目标字节
    @param force_dry_run: 跳过 libtorrent
    @param write_mysql: True 时写入 speedtest_results 与 slot_speed_summary
    @returns: 含 full 结果与可选 write 摘要的字典
    @raises RuntimeError: 页面无 Recommended 或 MySQL 未配置
    """
    from workflow.config import release_mysql_configured
    from workflow.storage.mysql_store import MySQLStore
    from workflow.torrent_sources.speedtest.full_speed import run_full_speedtest

    if not release_mysql_configured():
        raise RuntimeError("MySQL 未配置；slot 命令需要 RELEASE_MYSQL_*")

    store = MySQLStore()
    recommended = store.get_recommended_resource(page_id)
    if not recommended:
        raise RuntimeError(f"页面 {page_id!r} 无 Recommended release")

    full = run_full_speedtest(
        recommended.infohash,
        page_id=page_id,
        phase1_timeout_sec=phase1_timeout_sec,
        phase2_timeout_sec=phase2_timeout_sec,
        target_bytes=target_bytes,
        force_dry_run=force_dry_run,
        magnet_uri=recommended.magnet_uri or None,
    )

    payload: Dict[str, Any] = {
        "page_id": page_id,
        "recommended": {
            "infohash": recommended.infohash,
            "title_raw": recommended.title_raw,
        },
        "speedtest": full.to_dict(),
    }

    if write_mysql:
        payload["write"] = persist_speedtest_results(full, page_id=page_id)

    return payload
