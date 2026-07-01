# -*- coding: utf-8 -*-
"""
Magnet / infohash 工具函数（Phase 1 / Phase 2 共用）。

@module workflow.torrent_sources.speedtest.magnet_utils
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import quote

# infohash 格式：40 位十六进制
INFOHASH_RE = re.compile(r"^[0-9a-f]{40}$")

# 公共 tracker 列表（magnet 无 tr= 时补全，提高 peer 发现率）
DEFAULT_TRACKERS: List[str] = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
]


def normalize_infohash(infohash: str) -> str:
    """
    归一化 infohash 为小写 40 位。

    @param infohash: 原始 hash 字符串
    @returns: 小写 40 位 hex
    @raises ValueError: 格式非法
    """
    normalized = (infohash or "").strip().lower()
    if not INFOHASH_RE.match(normalized):
        raise ValueError(f"非法 infohash: {infohash!r}")
    return normalized


def build_magnet_uri(infohash: str, magnet_uri: Optional[str] = None) -> str:
    """
    构造或补全 magnet URI。

    @param infohash: 40 位 infohash
    @param magnet_uri: 可选完整 magnet（含 tracker）
    @returns: magnet URI 字符串
    """
    if magnet_uri and magnet_uri.strip().lower().startswith("magnet:?"):
        return magnet_uri.strip()
    tr_params = "".join(f"&tr={quote(tr, safe='')}" for tr in DEFAULT_TRACKERS)
    return f"magnet:?xt=urn:btih:{infohash}{tr_params}"
