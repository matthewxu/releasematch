#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EZTV 直连 JSON API 客户端（剧集）。

@module workflow.torrent_sources.eztv_client
@description Layer 2A：按 IMDb + 季集拉取 magnet 元数据。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from workflow.torrent_sources.models import ResourceItem

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def normalize_imdb_numeric(imdb_id: str) -> str:
    """
    将 IMDb ID 转为 EZTV API 使用的数字串（保留 7 位前导零）。

    @param imdb_id: 如 tt0903747
    @returns: 如 0903747
    """
    raw = imdb_id.strip().lower()
    if raw.startswith("tt"):
        raw = raw[2:]
    if raw.isdigit():
        return raw.zfill(7)
    return raw


class EztvClient:
    """
    EZTV JSON API 客户端。

    @param base_url: API 根 URL，如 https://eztvx.to
    @param min_interval_sec: 请求最小间隔
    @param timeout_sec: HTTP 超时
    """

    def __init__(
        self,
        base_url: str = "https://eztvx.to",
        min_interval_sec: float = 1.0,
        timeout_sec: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._last_call = 0.0

    def _throttle(self) -> None:
        """请求限速。"""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
        self._last_call = time.time()

    def fetch_episode(
        self,
        imdb_id: str,
        season: int,
        episode: int,
        limit: int = 100,
    ) -> List[ResourceItem]:
        """
        拉取指定季集 torrent 列表。

        @param imdb_id: IMDb ID（可含 tt 前缀）
        @param season: 季号
        @param episode: 集号
        @param limit: 单页条数上限
        @returns: ResourceItem 列表
        """
        imdb_num = normalize_imdb_numeric(imdb_id)
        url = f"{self._base_url}/api/get-torrents"
        params = {"imdb_id": imdb_num, "limit": limit, "page": 1}
        self._throttle()
        response = requests.get(
            url,
            params=params,
            headers=_DEFAULT_HEADERS,
            timeout=self._timeout_sec,
        )
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
        items: List[ResourceItem] = []
        for row in data.get("torrents") or []:
            if not isinstance(row, dict):
                continue
            try:
                s = int(row.get("season") or 0)
                e = int(row.get("episode") or 0)
            except (TypeError, ValueError):
                continue
            if s != season or e != episode:
                continue
            item = self._row_to_item(row)
            if item:
                items.append(item)
        return items

    @staticmethod
    def _row_to_item(row: Dict[str, Any]) -> Optional[ResourceItem]:
        """
        EZTV JSON 行转 ResourceItem。

        @param row: torrents[] 单条
        @returns: ResourceItem 或 None（无 hash）
        """
        infohash = str(row.get("hash") or "").lower().strip()
        if len(infohash) != 40:
            return None
        title = str(row.get("title") or row.get("filename") or "")
        magnet = str(row.get("magnet_url") or "")
        if not magnet:
            magnet = f"magnet:?xt=urn:btih:{infohash}"
        try:
            size = int(row.get("size_bytes") or 0)
        except (TypeError, ValueError):
            size = 0
        try:
            seeders = int(row.get("seeds") or 0)
        except (TypeError, ValueError):
            seeders = 0
        try:
            peers = int(row.get("peers") or 0)
        except (TypeError, ValueError):
            peers = 0
        return ResourceItem(
            infohash=infohash,
            title_raw=title,
            magnet_uri=magnet,
            size_bytes=size,
            seeders=seeders,
            peers=peers,
            indexer="eztv",
        )
