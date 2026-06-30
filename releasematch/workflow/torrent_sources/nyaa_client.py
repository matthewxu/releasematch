#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nyaa.si RSS 直连客户端。

@module workflow.torrent_sources.nyaa_client
@description Layer 2C：动漫 / 部分剧集 RSS 搜索，多镜像回退。
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from workflow.torrent_sources.models import ResourceItem
from workflow.torrent_sources.slot_filter import matches_season_episode

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Nyaa RSS 命名空间
_NYAA_NS = {"nyaa": "https://nyaa.si/xml/schemas/nyaa#"}

# 默认镜像（与 poc_lib 一致）
_DEFAULT_MIRRORS: Tuple[str, ...] = (
    "https://nyaa.si",
    "https://nyaa.iss.ink",
)

# 季集匹配见 slot_filter.matches_season_episode


def _parse_size_bytes(size_text: str) -> int:
    """
    解析 Nyaa 人类可读大小为字节数。

    @param size_text: 如 1.2 GiB
    @returns: 字节数，失败为 0
    """
    text = (size_text or "").strip()
    if not text:
        return 0
    match = re.match(r"^([\d.]+)\s*([KMGT]?i?B)$", text, re.IGNORECASE)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {
        "B": 1,
        "KB": 1000,
        "KIB": 1024,
        "MB": 1000**2,
        "MIB": 1024**2,
        "GB": 1000**3,
        "GIB": 1024**3,
        "TB": 1000**4,
        "TIB": 1024**4,
    }
    return int(value * multipliers.get(unit, 1))


def _extract_infohash(magnet_uri: str, nyaa_hash: str) -> str:
    """
    从 magnet 或 Nyaa 字段提取 40 位 infohash。

    @param magnet_uri: magnet 链接
    @param nyaa_hash: RSS nyaa:infoHash
    @returns: 小写 infohash 或空串
    """
    if nyaa_hash and len(nyaa_hash.strip()) == 40:
        return nyaa_hash.strip().lower()
    match = re.search(r"btih:([0-9a-fA-F]{40})", magnet_uri or "", re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return ""


class NyaaClient:
    """
    Nyaa.si RSS 客户端。

    @param base_url: 主站 URL
    @param mirrors: 备用镜像列表
    @param min_interval_sec: 请求最小间隔
    @param timeout_sec: HTTP 超时
    @param enabled: 是否启用（配置可关闭）
    """

    def __init__(
        self,
        base_url: str = "https://nyaa.si",
        mirrors: Optional[List[str]] = None,
        min_interval_sec: float = 3.0,
        timeout_sec: float = 25.0,
        enabled: bool = True,
    ) -> None:
        primary = base_url.rstrip("/")
        extra = [m.rstrip("/") for m in (mirrors or []) if m]
        seen = {primary}
        ordered: List[str] = [primary]
        for mirror in list(_DEFAULT_MIRRORS) + extra:
            if mirror not in seen:
                seen.add(mirror)
                ordered.append(mirror)
        self._mirrors = ordered
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._enabled = enabled
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

    def search_rss(
        self,
        query: str,
        category: str = "1_0",
        limit: int = 50,
    ) -> List[ResourceItem]:
        """
        Nyaa RSS 搜索。

        @param query: 搜索词
        @param category: Nyaa 分类，如 1_0（Anime）
        @param limit: 最大条数
        @returns: ResourceItem 列表
        """
        if not self._enabled or not query.strip():
            return []

        encoded_query = quote(query.strip())
        path = f"/?page=rss&q={encoded_query}&c={category}&s=seeders&o=desc"
        last_error: Optional[Exception] = None

        for mirror in self._mirrors:
            url = f"{mirror}{path}"
            try:
                self._throttle()
                response = requests.get(
                    url,
                    headers=_DEFAULT_HEADERS,
                    timeout=self._timeout_sec,
                )
                response.raise_for_status()
                return self._parse_rss(response.content, limit=limit)
            except Exception as exc:  # noqa: BLE001 — 尝试下一镜像
                last_error = exc
                continue

        if last_error:
            raise last_error
        return []

    def fetch_episode(
        self,
        title: str,
        season: int,
        episode: int,
        category: str = "1_0",
    ) -> List[ResourceItem]:
        """
        按作品名 + 季集拉取（过滤 RSS 结果）。

        @param title: 作品英文名
        @param season: 季号
        @param episode: 集号
        @param category: Nyaa 分类
        @returns: 匹配季集的 ResourceItem 列表
        """
        query = f"{title} S{season:02d}E{episode:02d}"
        items = self.search_rss(query, category=category, limit=100)
        filtered: List[ResourceItem] = []
        for item in items:
            if matches_season_episode(item.title_raw, season, episode):
                filtered.append(item)
        if filtered:
            return filtered
        # 回退：宽松查询仅作品名，再本地过滤
        broad = self.search_rss(title, category=category, limit=100)
        for item in broad:
            if matches_season_episode(item.title_raw, season, episode):
                filtered.append(item)
        return filtered

    def _parse_rss(self, content: bytes, limit: int = 50) -> List[ResourceItem]:
        """
        解析 Nyaa RSS XML。

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
        RSS item 转 ResourceItem。

        @param entry: XML item 元素
        @returns: ResourceItem 或 None
        """
        title = (entry.findtext("title") or "").strip()
        magnet = (entry.findtext("link") or "").strip()
        nyaa_hash = entry.findtext("nyaa:infoHash", namespaces=_NYAA_NS) or ""
        seeders_text = entry.findtext("nyaa:seeders", namespaces=_NYAA_NS) or "0"
        size_text = entry.findtext("nyaa:size", namespaces=_NYAA_NS) or ""

        infohash = _extract_infohash(magnet, nyaa_hash)
        if len(infohash) != 40:
            return None

        try:
            seeders = int(seeders_text)
        except (TypeError, ValueError):
            seeders = 0

        if not magnet:
            magnet = f"magnet:?xt=urn:btih:{infohash}"

        return ResourceItem(
            infohash=infohash,
            title_raw=title,
            magnet_uri=magnet,
            size_bytes=_parse_size_bytes(size_text),
            seeders=seeders,
            peers=0,
            indexer="nyaa",
        )
