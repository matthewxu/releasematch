#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YTS API v2 客户端（电影）。

@module workflow.torrent_sources.yts_client
@description Layer 2B：movie_details.json → magnet 元数据。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List
from urllib.parse import quote, urlencode

import requests

from workflow.torrent_sources.models import ResourceItem

_YTS_MIRRORS = (
    "https://yts.lt",
    "https://yts.rs",
    "https://yts.mx",
    "https://yts.gg",
)

_TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:80/announce",
)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def yts_hash_to_magnet(info_hash: str, title: str, size: int) -> str:
    """
    将 YTS torrent hash 构造为 magnet URI。

    @param info_hash: 40 位 hex
    @param title: 显示名
    @param size: 字节数（xl 参数）
    @returns: magnet URI
    """
    params = {
        "xt": f"urn:btih:{info_hash.lower()}",
        "dn": title,
        "xl": str(size),
        "tr": list(_TRACKERS),
    }
    return "magnet:?" + urlencode(params, doseq=True, safe=":")


class YtsClient:
    """
    YTS API 客户端（支持镜像回退）。

    @param base_url: 首选镜像；失败时尝试内置列表
    @param min_interval_sec: 请求间隔
    @param timeout_sec: HTTP 超时
    """

    def __init__(
        self,
        base_url: str = "https://yts.lt",
        min_interval_sec: float = 1.0,
        timeout_sec: float = 30.0,
    ) -> None:
        self._preferred = base_url.rstrip("/")
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._last_call = 0.0

    def _mirror_urls(self) -> List[str]:
        """首选镜像 + 内置回退列表（去重保序）。"""
        ordered: List[str] = []
        seen: set[str] = set()
        for base in (self._preferred, *_YTS_MIRRORS):
            if base not in seen:
                seen.add(base)
                ordered.append(base)
        return ordered

    def _throttle(self) -> None:
        """请求限速。"""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
        self._last_call = time.time()

    def fetch_movie(self, imdb_id: str) -> List[ResourceItem]:
        """
        按 IMDb ID 拉取电影所有 quality 的 torrent。

        @param imdb_id: 如 tt0133093（可不含 tt）
        @returns: ResourceItem 列表
        """
        imdb_param = imdb_id if imdb_id.startswith("tt") else f"tt{imdb_id}"
        errors: List[str] = []
        for base in self._mirror_urls():
            url = f"{base}/api/v2/movie_details.json"
            try:
                self._throttle()
                response = requests.get(
                    url,
                    params={"imdb_id": imdb_param},
                    headers=_DEFAULT_HEADERS,
                    timeout=self._timeout_sec,
                )
                response.raise_for_status()
                data: Dict[str, Any] = response.json()
                movie = (data.get("data") or {}).get("movie") or {}
                return self._movie_to_items(movie)
            except Exception as exc:  # noqa: BLE001 — 镜像回退
                errors.append(f"{base}: {exc}")
        raise RuntimeError("YTS all mirrors failed: " + " | ".join(errors))

    def _movie_to_items(self, movie: Dict[str, Any]) -> List[ResourceItem]:
        """
        YTS movie 对象转 ResourceItem 列表。

        @param movie: data.movie JSON
        @returns: 各 quality 一条 ResourceItem
        """
        title_base = str(movie.get("title") or movie.get("title_english") or "Unknown")
        items: List[ResourceItem] = []
        for tor in movie.get("torrents") or []:
            if not isinstance(tor, dict):
                continue
            infohash = str(tor.get("hash") or "").lower().strip()
            if len(infohash) != 40:
                continue
            quality = str(tor.get("quality") or "")
            src_type = str(tor.get("type") or "")
            try:
                size = int(tor.get("size_bytes") or 0)
            except (TypeError, ValueError):
                size = 0
            try:
                seeders = int(tor.get("seeds") or 0)
            except (TypeError, ValueError):
                seeders = 0
            try:
                peers = int(tor.get("peers") or 0)
            except (TypeError, ValueError):
                peers = 0
            display = f"{title_base}.{quality}.{src_type}-YTS"
            items.append(
                ResourceItem(
                    infohash=infohash,
                    title_raw=display,
                    magnet_uri=yts_hash_to_magnet(infohash, display, size),
                    size_bytes=size,
                    seeders=seeders,
                    peers=peers,
                    resolution=quality.lower() if quality else "",
                    source=src_type.upper() if src_type else "",
                    indexer="yts",
                    release_group="YTS",
                )
            )
        return items
