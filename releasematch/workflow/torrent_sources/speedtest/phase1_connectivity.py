# -*- coding: utf-8 -*-
"""
Phase 1：magnet peer 可达性探测。

@module workflow.torrent_sources.speedtest.phase1_connectivity
@description
  优先使用 libtorrent 做 DHT/peer 探测；未安装时回退 dry-run 占位，
  仅校验 infohash 格式并返回 scaffold 结果，供 T2 后续接真实测速。
"""

from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import quote

from workflow.torrent_sources.speedtest.models import ConnectivityResult, SpeedTestTask

# infohash 格式：40 位十六进制
_INFOHASH_RE = re.compile(r"^[0-9a-f]{40}$")


def _normalize_infohash(infohash: str) -> str:
    """
    归一化 infohash 为小写 40 位。

    @param infohash: 原始 hash 字符串
    @returns: 小写 40 位 hex
    @raises ValueError: 格式非法
    """
    normalized = (infohash or "").strip().lower()
    if not _INFOHASH_RE.match(normalized):
        raise ValueError(f"非法 infohash: {infohash!r}")
    return normalized


# 公共 tracker 列表（magnet 无 tr= 时补全，提高 peer 发现率）
_DEFAULT_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
]


def _build_magnet_uri(infohash: str, magnet_uri: Optional[str] = None) -> str:
    """
    构造或补全 magnet URI。

    @param infohash: 40 位 infohash
    @param magnet_uri: 可选完整 magnet（含 tracker）
    @returns: magnet URI 字符串
    """
    if magnet_uri and magnet_uri.strip().lower().startswith("magnet:?"):
        return magnet_uri.strip()
    tr_params = "".join(f"&tr={quote(tr, safe='')}" for tr in _DEFAULT_TRACKERS)
    return f"magnet:?xt=urn:btih:{infohash}{tr_params}"


def _test_with_libtorrent(task: SpeedTestTask, magnet_uri: Optional[str] = None) -> ConnectivityResult:
    """
    使用 libtorrent 2.x 做 Phase 1 连接性测试。

    @param task: 测速任务
    @param magnet_uri: 可选完整 magnet（优先使用源站 tracker）
    @returns: ConnectivityResult
    """
    import libtorrent as lt  # type: ignore

    infohash = _normalize_infohash(task.infohash)
    magnet = _build_magnet_uri(infohash, magnet_uri)

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
    params.save_path = "/tmp/releasematch-speedtest"
    handle = session.add_torrent(params)
    handle.set_upload_limit(0)
    handle.set_download_limit(0)

    start = time.time()
    peers_total = 0
    peers_reachable = 0

    while time.time() - start < task.timeout_sec:
        status = handle.status()
        peer_list = handle.get_peer_info()
        peers_total = max(peers_total, status.num_peers, len(peer_list))
        # flags bit 0：已连接
        peers_reachable = sum(1 for p in peer_list if p.flags & 1)
        if peers_total > 0 or peers_reachable > 0:
            break
        time.sleep(1)

    elapsed_ms = int((time.time() - start) * 1000)
    session.remove_torrent(handle)

    if peers_reachable > 0 or peers_total > 0:
        status_str = "ok"
    else:
        status_str = "timeout"

    return ConnectivityResult(
        infohash=infohash,
        peers_reachable=peers_reachable,
        peers_total=peers_total,
        elapsed_ms=elapsed_ms,
        status=status_str,
        mode="libtorrent",
        page_id=task.page_id,
    )


def _test_dry_run(task: SpeedTestTask) -> ConnectivityResult:
    """
    dry-run 占位：仅校验 infohash，不发起网络探测。

    @param task: 测速任务
    @returns: ConnectivityResult（status=dry_run）
    """
    infohash = _normalize_infohash(task.infohash)
    return ConnectivityResult(
        infohash=infohash,
        peers_reachable=0,
        peers_total=0,
        elapsed_ms=0,
        status="dry_run",
        mode="dry_run",
        page_id=task.page_id,
        error="libtorrent 未安装；Phase 1 真实测速待 T2 环境就绪",
    )


def test_connectivity(
    infohash: str,
    *,
    page_id: Optional[str] = None,
    timeout_sec: int = 10,
    force_dry_run: bool = False,
    magnet_uri: Optional[str] = None,
) -> ConnectivityResult:
    """
    Phase 1 入口：探测单条 magnet 的 peer 可达性。

    @param infohash: 40 位 infohash
    @param page_id: 可选页面 ID
    @param timeout_sec: 超时秒数
    @param force_dry_run: True 时跳过 libtorrent，仅做格式校验
    @param magnet_uri: 可选完整 magnet（含 tracker，提高发现率）
    @returns: ConnectivityResult
    """
    task = SpeedTestTask(
        infohash=infohash,
        page_id=page_id,
        timeout_sec=timeout_sec,
        phase=1,
    )

    if force_dry_run:
        return _test_dry_run(task)

    try:
        import libtorrent  # noqa: F401

        return _test_with_libtorrent(task, magnet_uri=magnet_uri)
    except ImportError:
        return _test_dry_run(task)
    except Exception as exc:
        infohash_norm = _normalize_infohash(infohash)
        return ConnectivityResult(
            infohash=infohash_norm,
            status="error",
            mode="libtorrent",
            page_id=page_id,
            error=str(exc),
        )
