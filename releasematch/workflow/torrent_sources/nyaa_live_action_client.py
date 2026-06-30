#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nyaa.si Live Action RSS 客户端（日韩真人影视 Layer 2D）。

@module workflow.torrent_sources.nyaa_live_action_client
@description 使用 Nyaa 分类 c=4_0（Live Action），支持多语言标题搜索。
"""

from __future__ import annotations

from typing import List, Optional

from workflow.torrent_sources.http_fetch import ProxySettings
from workflow.torrent_sources.models import ResourceItem
from workflow.torrent_sources.nyaa_client import NyaaClient

# Nyaa Live Action - All（日韩剧/电影主分类）
_LIVE_ACTION_CATEGORY = "4_0"

# 跨源统计用 indexer 标识
INDEXER_LABEL = "nyaa_live_action"


class NyaaLiveActionClient:
    """
    Nyaa.si 真人区（Live Action）RSS 客户端。

    @param base_url: 主站 URL
    @param mirrors: 备用镜像
    @param min_interval_sec: 请求间隔
    @param timeout_sec: HTTP 超时
    @param enabled: 是否启用
    @param proxy: 直连失败时的 HTTP 代理
    @param category: Nyaa 分类，默认 4_0
    """

    def __init__(
        self,
        base_url: str = "https://nyaa.si",
        mirrors: Optional[List[str]] = None,
        min_interval_sec: float = 3.0,
        timeout_sec: float = 25.0,
        enabled: bool = True,
        proxy: Optional[ProxySettings] = None,
        category: str = _LIVE_ACTION_CATEGORY,
    ) -> None:
        self._category = category
        self._enabled = enabled
        self._client = NyaaClient(
            base_url=base_url,
            mirrors=mirrors,
            min_interval_sec=min_interval_sec,
            timeout_sec=timeout_sec,
            enabled=enabled,
            proxy=proxy,
        )

    @property
    def enabled(self) -> bool:
        """客户端是否启用。"""
        return self._enabled and self._client.enabled

    def search_rss(self, query: str, limit: int = 50) -> List[ResourceItem]:
        """
        Live Action RSS 搜索。

        @param query: 搜索词
        @param limit: 最大条数
        @returns: ResourceItem 列表（indexer=nyaa_live_action）
        """
        items = self._client.search_rss(query, category=self._category, limit=limit)
        return self._tag_items(items)

    def fetch_episode(self, title: str, season: int, episode: int) -> List[ResourceItem]:
        """
        单标题 + 季集拉取。

        @param title: 作品名（英/日/韩）
        @param season: 季号
        @param episode: 集号
        @returns: 匹配条目
        """
        items = self._client.fetch_episode(
            title,
            season,
            episode,
            category=self._category,
        )
        return self._tag_items(items)

    def fetch_episode_titles(
        self,
        titles: List[str],
        season: int,
        episode: int,
    ) -> List[ResourceItem]:
        """
        多语言标题依次搜索并去重合并。

        @param titles: 搜索词列表（英 + 日/韩本地名）
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

    @staticmethod
    def _tag_items(items: List[ResourceItem]) -> List[ResourceItem]:
        """
        统一 indexer 字段为 nyaa_live_action。

        @param items: 原始列表
        @returns: 同一列表（已更新 indexer）
        """
        for item in items:
            item.indexer = INDEXER_LABEL
        return items
