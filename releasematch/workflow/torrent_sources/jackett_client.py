#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jackett Torznab API 客户端。

@module workflow.torrent_sources.jackett_client
@description Layer 1：聚合 indexer，解析 Torznab XML 为 ResourceItem。
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests

from workflow.torrent_sources.models import ResourceItem

_TORZNAB_NS = {"torznab": "http://torznab.com/schemas/2015/feed"}
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml, application/rss+xml, */*",
}


class JackettClient:
    """
    Jackett Torznab API 客户端。

    @param base_url: Jackett 地址，如 http://127.0.0.1:9117
    @param api_key: Jackett API Key
    @param min_interval_sec: 请求最小间隔
    @param timeout_sec: HTTP 超时
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        min_interval_sec: float = 2.0,
        timeout_sec: float = 45.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._last_call = 0.0

    def _throttle(self) -> None:
        """请求限速。"""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
        self._last_call = time.time()

    def _search(self, indexer: str, params: Dict[str, str]) -> List[ResourceItem]:
        """
        执行 Torznab 搜索并解析 XML。

        @param indexer: indexer id 或 all
        @param params: 查询参数（不含 apikey）
        @returns: ResourceItem 列表
        """
        self._throttle()
        query = dict(params)
        query["apikey"] = self._api_key
        url = (
            f"{self._base_url}/api/v2.0/indexers/{indexer}"
            f"/results/torznab/api?{urlencode(query)}"
        )
        response = requests.get(url, headers=_DEFAULT_HEADERS, timeout=self._timeout_sec)
        response.raise_for_status()
        return self._parse_torznab_xml(response.text, indexer)

    @staticmethod
    def _parse_torznab_xml(xml_text: str, indexer: str) -> List[ResourceItem]:
        """
        解析 Torznab RSS XML。

        @param xml_text: 响应正文
        @param indexer: 来源 indexer 标识
        @returns: ResourceItem 列表
        """
        root = ET.fromstring(xml_text)
        items: List[ResourceItem] = []
        for node in root.findall(".//item"):
            title = node.findtext("title") or ""
            link = node.findtext("link") or ""
            try:
                size = int(node.findtext("size") or 0)
            except ValueError:
                size = 0
            attrs = {
                a.get("name"): a.get("value")
                for a in node.findall("torznab:attr", _TORZNAB_NS)
            }
            infohash = (attrs.get("infohash") or "").lower().strip()
            if not infohash and "btih:" in link.lower():
                infohash = link.lower().split("btih:")[1].split("&")[0].strip()
            if len(infohash) != 40:
                continue
            magnet = link if link.startswith("magnet:") else f"magnet:?xt=urn:btih:{infohash}"
            try:
                seeders = int(attrs.get("seeders") or 0)
            except (TypeError, ValueError):
                seeders = 0
            try:
                peers = int(attrs.get("peers") or 0)
            except (TypeError, ValueError):
                peers = 0
            label = indexer if indexer != "all" else str(attrs.get("indexer") or "jackett")
            items.append(
                ResourceItem(
                    infohash=infohash,
                    title_raw=title,
                    magnet_uri=magnet,
                    size_bytes=size,
                    seeders=seeders,
                    peers=peers,
                    indexer=f"jackett:{label}",
                )
            )
        return items

    def search_tv(
        self,
        indexer: str,
        tvdb_id: Optional[int],
        season: int,
        episode: int,
        query_text: Optional[str] = None,
    ) -> List[ResourceItem]:
        """
        剧集单集搜索：优先 q+season+ep（作品名精确），tvdbid 仅作补充。

        @param indexer: indexer id 或 all
        @param tvdb_id: TVDB ID（可选）
        @param season: 季号
        @param episode: 集号
        @param query_text: 文本查询（如 Breaking Bad）
        @returns: ResourceItem 列表（按 infohash 去重合并）
        """
        merged: List[ResourceItem] = []
        seen: set[str] = set()

        def _merge(batch: List[ResourceItem]) -> None:
            """合并批次结果并去重 infohash。"""
            for item in batch:
                if item.infohash in seen:
                    continue
                seen.add(item.infohash)
                merged.append(item)

        # 1) 作品名 + 季集（Torznab tvsearch）— 误匹配最少，应优先
        if query_text:
            try:
                _merge(
                    self._search(
                        indexer,
                        {
                            "t": "tvsearch",
                            "q": query_text,
                            "season": str(season),
                            "ep": str(episode),
                            "cache": "false",
                        },
                    )
                )
            except requests.HTTPError:
                pass

        # 2) 自由文本 search 兜底
        if query_text:
            try:
                _merge(
                    self.search_text(
                        indexer,
                        f"{query_text} S{season:02d}E{episode:02d}",
                    )
                )
            except requests.HTTPError:
                pass

        # 3) tvdbid 补充（易混入同季集其他剧，仅在前两者无结果时使用）
        if tvdb_id and not merged:
            try:
                _merge(
                    self._search(
                        indexer,
                        {
                            "t": "tvsearch",
                            "tvdbid": str(tvdb_id),
                            "season": str(season),
                            "ep": str(episode),
                            "cache": "false",
                        },
                    )
                )
            except requests.HTTPError:
                pass

        return merged

    def search_movie(
        self,
        indexer: str,
        imdb_id: str,
        tmdb_id: Optional[int] = None,
    ) -> List[ResourceItem]:
        """
        电影搜索。

        @param indexer: indexer id 或 all
        @param imdb_id: IMDb ID
        @param tmdb_id: 可选 TMDB ID
        @returns: ResourceItem 列表
        """
        imdb_num = imdb_id.replace("tt", "").strip()
        params: Dict[str, str] = {
            "t": "movie",
            "imdbid": imdb_num,
            "cache": "false",
        }
        if tmdb_id:
            params["tmdbid"] = str(tmdb_id)
        try:
            return self._search(indexer, params)
        except requests.HTTPError:
            return []

    def search_text(self, indexer: str, query: str) -> List[ResourceItem]:
        """
        文本搜索兜底。

        @param indexer: indexer id
        @param query: 搜索词
        @returns: ResourceItem 列表
        """
        return self._search(indexer, {"t": "search", "q": query, "cache": "false"})
