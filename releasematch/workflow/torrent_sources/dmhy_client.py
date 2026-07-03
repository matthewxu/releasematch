#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动漫花园（DMHy）RSS 直连客户端 — 中文影视第一手源 Layer 2F。

@module workflow.torrent_sources.dmhy_client
@description
  share.dmhy.org 提供 keyword RSS，覆盖中文动漫、部分剧集/电影 magnet。
  接口规格：https://share.dmhy.org/topics/rss/rss.xml?keyword={词}&sort_id=0&team_id=0
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.parse import urlencode

from workflow.torrent_sources.http_fetch import ProxySettings, http_get
from workflow.torrent_sources.models import ResourceItem
from workflow.torrent_sources.slot_filter import matches_season_episode

# 默认请求头（DMHy 对空 UA 可能限流）
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# RSS 路径（相对 base_url）
_RSS_PATH = "/topics/rss/rss.xml"

# 跨源统计用 indexer 标识
INDEXER_LABEL = "dmhy"

# magnet 中 infohash 提取
_BTih_RE = re.compile(r"btih:([0-9a-fA-F]{40})", re.IGNORECASE)


def _extract_infohash(magnet_uri: str) -> str:
    """
    从 magnet URI 提取 40 位 infohash。

    @param magnet_uri: magnet 链接
    @returns: 小写 infohash 或空串
    """
    match = _BTih_RE.search(magnet_uri or "")
    if match:
        return match.group(1).lower()
    return ""


class DmhyClient:
    """
    动漫花园（DMHy）RSS 客户端。

    @param base_url: 主站根 URL，默认 https://share.dmhy.org
    @param mirrors: 备用镜像根 URL 列表
    @param min_interval_sec: 请求最小间隔（防封 IP）
    @param timeout_sec: HTTP 超时秒数
    @param enabled: 是否启用
    @param proxy: 直连失败时的 HTTP/SOCKS 代理
    @param sort_id: RSS sort_id 参数（0=全部）
    @param team_id: RSS team_id 参数（0=全部字幕组）
    @param order: RSS 排序，默认 date-desc
    """

    def __init__(
        self,
        base_url: str = "https://share.dmhy.org",
        mirrors: Optional[List[str]] = None,
        min_interval_sec: float = 3.0,
        timeout_sec: float = 30.0,
        enabled: bool = True,
        proxy: Optional[ProxySettings] = None,
        sort_id: int = 0,
        team_id: int = 0,
        order: str = "date-desc",
    ) -> None:
        primary = base_url.rstrip("/")
        extra = [m.rstrip("/") for m in (mirrors or []) if m]
        seen = {primary}
        ordered: List[str] = [primary]
        for mirror in extra:
            if mirror not in seen:
                seen.add(mirror)
                ordered.append(mirror)
        self._bases = ordered
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._enabled = enabled
        self._proxy = proxy
        self._sort_id = sort_id
        self._team_id = team_id
        self._order = order
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        """客户端是否启用。"""
        return self._enabled

    def _throttle(self) -> None:
        """请求限速。"""
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
        self._last_call = time.time()

    def _build_rss_url(self, base: str, keyword: str) -> str:
        """
        构造 DMHy keyword RSS URL（UTF-8 编码中文关键词）。

        @param base: 站点根 URL
        @param keyword: 搜索词
        @returns: 完整 RSS URL
        """
        params = urlencode(
            {
                "keyword": keyword.strip(),
                "sort_id": self._sort_id,
                "team_id": self._team_id,
                "order": self._order,
            },
            encoding="utf-8",
        )
        return f"{base.rstrip('/')}{_RSS_PATH}?{params}"

    def search_rss(self, query: str, limit: int = 50) -> List[ResourceItem]:
        """
        DMHy keyword RSS 搜索。

        @param query: 搜索词（中文/英文）
        @param limit: 最大条数
        @returns: ResourceItem 列表（indexer=dmhy）
        """
        if not self._enabled or not query.strip():
            return []

        last_error: Optional[Exception] = None
        for base in self._bases:
            url = self._build_rss_url(base, query)
            try:
                self._throttle()
                response = http_get(
                    url,
                    headers=_DEFAULT_HEADERS,
                    timeout_sec=self._timeout_sec,
                    proxy=self._proxy,
                )
                return self._parse_rss(response.content, limit=limit)
            except Exception as exc:  # noqa: BLE001 — 尝试下一镜像
                last_error = exc
                continue

        if last_error:
            raise last_error
        return []

    def fetch_episode(self, title: str, season: int, episode: int) -> List[ResourceItem]:
        """
        单标题 + 季集拉取（本地过滤 RSS 结果）。

        @param title: 作品名（优先中文）
        @param season: 季号
        @param episode: 集号
        @returns: 匹配季集的 ResourceItem 列表
        """
        queries = [
            f"{title} S{season:02d}E{episode:02d}",
            f"{title} {season}x{episode:02d}",
            f"{title} 第{episode}集",
            title,
        ]
        merged: List[ResourceItem] = []
        seen: set[str] = set()
        for query in queries:
            try:
                batch = self.search_rss(query, limit=80)
            except Exception:
                continue
            for item in batch:
                if not matches_season_episode(item.title_raw, season, episode):
                    continue
                ih = item.infohash.lower()
                if ih in seen:
                    continue
                seen.add(ih)
                merged.append(item)
            if merged:
                break
        return merged

    def fetch_episode_titles(
        self,
        titles: List[str],
        season: int,
        episode: int,
    ) -> List[ResourceItem]:
        """
        多语言标题依次搜索并去重合并。

        @param titles: 搜索词列表（中文优先 + 英文）
        @param season: 季号
        @param episode: 集号
        @returns: 去重后的 ResourceItem 列表
        """
        merged: List[ResourceItem] = []
        seen: set[str] = set()
        for title in titles:
            if not title or not str(title).strip():
                continue
            try:
                batch = self.fetch_episode(str(title).strip(), season, episode)
            except Exception:
                continue
            for item in batch:
                ih = item.infohash.lower()
                if ih in seen:
                    continue
                seen.add(ih)
                merged.append(item)
        return merged

    def fetch_movie_titles(self, titles: List[str], limit: int = 30) -> List[ResourceItem]:
        """
        多语言电影标题搜索并去重。

        @param titles: 搜索词列表
        @param limit: 每个查询的最大条数
        @returns: ResourceItem 列表
        """
        merged: List[ResourceItem] = []
        seen: set[str] = set()
        for title in titles:
            if not title or not str(title).strip():
                continue
            try:
                batch = self.search_rss(str(title).strip(), limit=limit)
            except Exception:
                continue
            for item in batch:
                ih = item.infohash.lower()
                if ih in seen:
                    continue
                seen.add(ih)
                merged.append(item)
        return merged

    def _parse_rss(self, content: bytes, limit: int = 50) -> List[ResourceItem]:
        """
        解析 DMHy RSS XML。

        @param content: 响应体
        @param limit: 条数上限
        @returns: ResourceItem 列表
        """
        root = ET.fromstring(content)
        channel = root.find("channel")
        if channel is None:
            return []

        items: List[ResourceItem] = []
        for entry in channel.findall("item"):
            item = self._entry_to_item(entry)
            if item:
                items.append(item)
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _entry_to_item(entry: ET.Element) -> Optional[ResourceItem]:
        """
        RSS item 转 ResourceItem（magnet 取自 enclosure）。

        @param entry: XML item 元素
        @returns: ResourceItem 或 None
        """
        title = (entry.findtext("title") or "").strip()
        magnet = ""
        enclosure = entry.find("enclosure")
        if enclosure is not None:
            enc_type = (enclosure.get("type") or "").lower()
            if "bittorrent" in enc_type or enc_type == "application/x-bittorrent":
                magnet = (enclosure.get("url") or "").strip()
        if not magnet:
            magnet = (entry.findtext("link") or "").strip()

        infohash = _extract_infohash(magnet)
        if len(infohash) != 40:
            return None

        if not magnet:
            magnet = f"magnet:?xt=urn:btih:{infohash}"

        return ResourceItem(
            infohash=infohash,
            title_raw=title,
            magnet_uri=magnet,
            size_bytes=0,
            seeders=0,
            peers=0,
            indexer=INDEXER_LABEL,
        )
