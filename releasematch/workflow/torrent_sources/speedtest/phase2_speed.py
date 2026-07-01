# -*- coding: utf-8 -*-
"""
Phase 2：magnet 片段下载测速（S-06）。

@module workflow.torrent_sources.speedtest.phase2_speed
@description
  从已连接 peer 下载前 target_bytes（默认 1MB）数据，输出 avg_kbps / max_kbps / latency_ms。
  未安装 libtorrent 时回退 dry-run 占位。
"""

from __future__ import annotations

import shutil
import tempfile
import time
from typing import List, Optional

from workflow.torrent_sources.speedtest.magnet_utils import build_magnet_uri, normalize_infohash
from workflow.torrent_sources.speedtest.models import FragmentSpeedResult, SpeedTestTask

# 默认下载目标：1 MiB
DEFAULT_TARGET_BYTES = 1_048_576


def _test_dry_run(task: SpeedTestTask, target_bytes: int) -> FragmentSpeedResult:
    """
    dry-run 占位：仅校验 infohash，不发起网络下载。

    @param task: 测速任务（phase=2）
    @param target_bytes: 设计目标字节数（记录用）
    @returns: FragmentSpeedResult（status=dry_run）
    """
    infohash = normalize_infohash(task.infohash)
    return FragmentSpeedResult(
        infohash=infohash,
        status="dry_run",
        mode="dry_run",
        page_id=task.page_id,
        error=f"libtorrent 未安装；Phase 2 目标 {target_bytes} 字节待 T2 环境就绪",
    )


def _sample_kbps(instant_bps: int) -> float:
    """
    libtorrent download_rate（B/s）转 KiB/s。

    @param instant_bps: 瞬时字节/秒
    @returns: KiB/s
    """
    if instant_bps <= 0:
        return 0.0
    return (instant_bps / 1024.0)


def _test_with_libtorrent(
    task: SpeedTestTask,
    target_bytes: int,
    magnet_uri: Optional[str] = None,
) -> FragmentSpeedResult:
    """
    使用 libtorrent 2.x 做 Phase 2 片段下载测速。

    @param task: 测速任务
    @param target_bytes: 目标下载字节数
    @param magnet_uri: 可选完整 magnet
    @returns: FragmentSpeedResult
    """
    import libtorrent as lt  # type: ignore

    infohash = normalize_infohash(task.infohash)
    magnet = build_magnet_uri(infohash, magnet_uri)
    save_dir = tempfile.mkdtemp(prefix="releasematch-speedtest-p2-")

    session = lt.session(
        {
            "listen_interfaces": "0.0.0.0:6881",
            "enable_dht": True,
            "enable_lsd": True,
            "enable_upnp": True,
            "enable_natpmp": True,
        }
    )

    params = lt.parse_magnet_uri(magnet)
    params.save_path = save_dir
    handle = session.add_torrent(params)
    handle.set_upload_limit(0)

    start = time.time()
    deadline = start + task.timeout_sec
    metadata_ready_at: Optional[float] = None
    first_byte_at: Optional[float] = None
    peak_kbps = 0.0
    rate_samples: List[float] = []
    last_download = 0
    last_sample_at = start

    try:
        while time.time() < deadline:
            status = handle.status()
            peer_list = handle.get_peer_info()
            peers_total = max(status.num_peers, len(peer_list))
            peers_reachable = sum(1 for p in peer_list if p.flags & 1)

            if status.has_metadata and metadata_ready_at is None:
                metadata_ready_at = time.time()

            downloaded = int(status.total_download or 0)
            if downloaded > 0 and first_byte_at is None:
                first_byte_at = time.time()

            instant_kbps = _sample_kbps(int(status.download_rate or 0))
            if instant_kbps > 0:
                peak_kbps = max(peak_kbps, instant_kbps)
                rate_samples.append(instant_kbps)

            now = time.time()
            if now - last_sample_at >= 0.5 and downloaded > last_download:
                delta_bytes = downloaded - last_download
                delta_sec = now - last_sample_at
                if delta_sec > 0:
                    sampled = (delta_bytes / 1024.0) / delta_sec
                    rate_samples.append(sampled)
                    peak_kbps = max(peak_kbps, sampled)
                last_download = downloaded
                last_sample_at = now

            if downloaded >= target_bytes:
                elapsed_ms = int((now - start) * 1000)
                download_window = (now - (first_byte_at or start))
                avg_kbps = (
                    (downloaded / 1024.0) / download_window if download_window > 0 else 0.0
                )
                if rate_samples:
                    avg_kbps = sum(rate_samples) / len(rate_samples)
                    peak_kbps = max(peak_kbps, max(rate_samples))
                latency_ms = 0
                if first_byte_at is not None:
                    latency_ms = int((first_byte_at - start) * 1000)
                session.remove_torrent(handle)
                return FragmentSpeedResult(
                    infohash=infohash,
                    avg_kbps=round(avg_kbps, 2),
                    max_kbps=round(peak_kbps, 2),
                    latency_ms=latency_ms,
                    bytes_downloaded=downloaded,
                    peers_reachable=peers_reachable,
                    peers_total=peers_total,
                    elapsed_ms=elapsed_ms,
                    status="ok",
                    mode="libtorrent",
                    page_id=task.page_id,
                )

            time.sleep(0.25)

        elapsed_ms = int((time.time() - start) * 1000)
        status = handle.status()
        peer_list = handle.get_peer_info()
        peers_total = max(status.num_peers, len(peer_list))
        peers_reachable = sum(1 for p in peer_list if p.flags & 1)
        downloaded = int(status.total_download or 0)

        if downloaded > 0:
            download_window = time.time() - (first_byte_at or start)
            avg_kbps = (
                (downloaded / 1024.0) / download_window if download_window > 0 else 0.0
            )
            if rate_samples:
                avg_kbps = sum(rate_samples) / len(rate_samples)
            latency_ms = int(((first_byte_at or start) - start) * 1000)
            result_status = "ok"
        else:
            avg_kbps = 0.0
            peak_kbps = 0.0
            latency_ms = 0
            if not status.has_metadata:
                result_status = "timeout"
            else:
                result_status = "timeout"

        session.remove_torrent(handle)
        return FragmentSpeedResult(
            infohash=infohash,
            avg_kbps=round(avg_kbps, 2),
            max_kbps=round(peak_kbps, 2),
            latency_ms=latency_ms,
            bytes_downloaded=downloaded,
            peers_reachable=peers_reachable,
            peers_total=peers_total,
            elapsed_ms=elapsed_ms,
            status=result_status,
            mode="libtorrent",
            page_id=task.page_id,
            error=None if result_status == "ok" else f"未在 {task.timeout_sec}s 内完成 {target_bytes} 字节下载",
        )
    finally:
        shutil.rmtree(save_dir, ignore_errors=True)


def test_fragment_speed(
    infohash: str,
    *,
    page_id: Optional[str] = None,
    timeout_sec: int = 30,
    target_bytes: int = DEFAULT_TARGET_BYTES,
    force_dry_run: bool = False,
    magnet_uri: Optional[str] = None,
) -> FragmentSpeedResult:
    """
    Phase 2 入口：下载片段并测速。

    @param infohash: 40 位 infohash
    @param page_id: 可选页面 ID
    @param timeout_sec: 超时秒数
    @param target_bytes: 目标下载字节数（默认 1MB）
    @param force_dry_run: True 时跳过 libtorrent
    @param magnet_uri: 可选完整 magnet
    @returns: FragmentSpeedResult
    """
    task = SpeedTestTask(
        infohash=infohash,
        page_id=page_id,
        timeout_sec=timeout_sec,
        phase=2,
    )

    if force_dry_run:
        return _test_dry_run(task, target_bytes)

    try:
        import libtorrent  # noqa: F401

        return _test_with_libtorrent(task, target_bytes, magnet_uri=magnet_uri)
    except ImportError:
        return _test_dry_run(task, target_bytes)
    except Exception as exc:
        infohash_norm = normalize_infohash(infohash)
        return FragmentSpeedResult(
            infohash=infohash_norm,
            status="error",
            mode="libtorrent",
            page_id=page_id,
            error=str(exc),
        )
