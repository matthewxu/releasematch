#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源拉取编排层。

@module workflow.torrent_sources.fetch_service
@description 缓存、EZTV/YTS/Jackett 串行拉取、infohash 去重、release 解析。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from workflow.metadata.external_ids import resolve_external_ids
from workflow.torrent_sources.cache_index import CacheIndex
from workflow.torrent_sources.config import (
    is_jackett_api_key_configured,
    load_accounts_config,
)
from workflow.torrent_sources.eztv_client import EztvClient
from workflow.torrent_sources.jackett_client import JackettClient
from workflow.torrent_sources.models import FetchRequest, FetchResult, MediaType, ResourceItem
from workflow.torrent_sources.release_parser import parse_release_title
from workflow.torrent_sources.yts_client import YtsClient


def _item_from_dict(row: Dict[str, Any]) -> ResourceItem:
    """
    从缓存 JSON 行还原 ResourceItem。

    @param row: to_dict() 产物
    @returns: ResourceItem
    """
    return ResourceItem(
        infohash=str(row.get("infohash") or ""),
        title_raw=str(row.get("title_raw") or ""),
        release_group=str(row.get("release_group") or ""),
        source=str(row.get("source") or ""),
        resolution=str(row.get("resolution") or ""),
        codec=str(row.get("codec") or ""),
        size_bytes=int(row.get("size_bytes") or 0),
        seeders=int(row.get("seeders") or 0),
        peers=int(row.get("peers") or 0),
        magnet_uri=str(row.get("magnet_uri") or ""),
        indexer=str(row.get("indexer") or ""),
        cross_source_count=int(row.get("cross_source_count") or 1),
    )


def _utc_expires_iso(hours: float) -> str:
    """
    生成 UTC 过期时间 ISO 字符串。

    @param hours: 有效小时数
    @returns: ISO8601 字符串
    """
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    return expires.strftime("%Y-%m-%dT%H:%M:%SZ")


def _apply_parser(item: ResourceItem) -> ResourceItem:
    """
    用 release_parser 填充 item 空字段。

    @param item: ResourceItem
    @returns: 同一对象（已更新）
    """
    parsed = parse_release_title(item.title_raw)
    if not item.release_group:
        item.release_group = parsed["release_group"]
    if not item.resolution:
        item.resolution = parsed["resolution"]
    if not item.codec:
        item.codec = parsed["codec"]
    if not item.source:
        item.source = parsed["source"]
    return item


def dedupe_by_infohash(items: List[ResourceItem]) -> List[ResourceItem]:
    """
    按 infohash 去重，保留 seeders 较高者。

    @param items: 原始列表
    @returns: 去重后列表
    """
    best: Dict[str, ResourceItem] = {}
    for item in items:
        h = item.infohash.lower()
        if len(h) != 40:
            continue
        existing = best.get(h)
        if existing is None or item.seeders > existing.seeders:
            best[h] = item
    return list(best.values())


class FetchService:
    """
    槽位 magnet 拉取服务。

    @param accounts_path: 可选 accounts 配置路径
    @param cache: 可选 CacheIndex 实例
    """

    def __init__(
        self,
        accounts_path: Optional[str] = None,
        cache: Optional[CacheIndex] = None,
    ) -> None:
        from pathlib import Path

        path = Path(accounts_path) if accounts_path else None
        self._cfg = load_accounts_config(path)
        self._cache = cache or CacheIndex()
        rate = float(self._cfg.get("rate_limit", {}).get("min_interval_sec", 2.0))
        ttl_h = float(self._cfg.get("cache", {}).get("seeders_ttl_hours", 6))
        self._cache_ttl_hours = ttl_h
        self._rate = rate

        eztv_cfg = self._cfg.get("eztv", {})
        yts_cfg = self._cfg.get("yts", {})
        self._eztv = EztvClient(
            base_url=str(eztv_cfg.get("base_url") or "https://eztvx.to"),
            min_interval_sec=rate,
        )
        self._yts = YtsClient(
            base_url=str(yts_cfg.get("base_url") or "https://yts.lt"),
            min_interval_sec=rate,
        )
        jackett_cfg = self._cfg.get("jackett", {})
        api_key = str(jackett_cfg.get("api_key") or "")
        self._jackett: Optional[JackettClient] = None
        if is_jackett_api_key_configured(api_key):
            self._jackett = JackettClient(
                base_url=str(jackett_cfg.get("base_url") or "http://127.0.0.1:9117"),
                api_key=api_key,
                min_interval_sec=rate,
            )
        self._jackett_tv_indexers: List[str] = list(
            jackett_cfg.get("indexers", {}).get("tv") or ["all"]
        )
        self._jackett_movie_indexers: List[str] = list(
            jackett_cfg.get("indexers", {}).get("movie") or ["all"]
        )

    def fetch_slot(self, request: FetchRequest) -> FetchResult:
        """
        拉取单槽位 magnet 清单（带缓存）。

        @param request: FetchRequest
        @returns: FetchResult
        """
        cache_key = request.cache_key()
        if not request.force:
            cached = self._cache.get(cache_key)
            if cached and cached.get("payload_json"):
                try:
                    payload = json.loads(cached["payload_json"])
                    items = [_item_from_dict(row) for row in payload]
                    return FetchResult(request=request, items=items, cached=True)
                except (json.JSONDecodeError, TypeError):
                    pass

        try:
            raw_items = self._fetch_from_sources(request)
        except Exception as exc:  # noqa: BLE001 — 汇总到 FetchResult.error
            return FetchResult(request=request, items=[], error=str(exc))

        merged = dedupe_by_infohash([_apply_parser(i) for i in raw_items])
        expires = _utc_expires_iso(self._cache_ttl_hours)
        self._cache.upsert(
            cache_key=cache_key,
            tmdb_id=request.tmdb_id,
            media_type=request.media_type.value,
            payload=[i.to_dict() for i in merged],
            expires_at=expires,
            season=request.season,
            episode=request.episode,
        )
        return FetchResult(request=request, items=merged, cached=False)

    def _fetch_from_sources(self, request: FetchRequest) -> List[ResourceItem]:
        """
        按媒体类型调用各 client。

        @param request: FetchRequest
        @returns: 未去重的 ResourceItem 列表
        """
        if request.media_type == MediaType.TV:
            return self._fetch_tv(request)
        return self._fetch_movie(request)

    def _fetch_tv(self, request: FetchRequest) -> List[ResourceItem]:
        """剧集：EZTV 直连 + Jackett 聚合。"""
        items: List[ResourceItem] = []
        if request.imdb_id and request.season is not None and request.episode is not None:
            try:
                items.extend(
                    self._eztv.fetch_episode(
                        request.imdb_id,
                        request.season,
                        request.episode,
                    )
                )
            except Exception:
                pass
        query_title: Optional[str] = None
        if request.tmdb_id:
            ext = resolve_external_ids(request.tmdb_id, "tv")
            query_title = ext.get("title") if isinstance(ext.get("title"), str) else None
        if self._jackett and request.season is not None and request.episode is not None:
            for indexer in self._jackett_tv_indexers:
                try:
                    items.extend(
                        self._jackett.search_tv(
                            indexer=indexer,
                            tvdb_id=request.tvdb_id,
                            season=request.season,
                            episode=request.episode,
                            query_text=query_title,
                        )
                    )
                except Exception:
                    continue
        return items

    def _fetch_movie(self, request: FetchRequest) -> List[ResourceItem]:
        """电影：YTS 直连 + Jackett。"""
        items: List[ResourceItem] = []
        if request.imdb_id:
            try:
                items.extend(self._yts.fetch_movie(request.imdb_id))
            except Exception:
                pass
        if self._jackett and request.imdb_id:
            for indexer in self._jackett_movie_indexers:
                try:
                    items.extend(
                        self._jackett.search_movie(
                            indexer=indexer,
                            imdb_id=request.imdb_id,
                            tmdb_id=request.tmdb_id,
                        )
                    )
                except Exception:
                    continue
        return items


def fetch_slot(request: FetchRequest, accounts_path: Optional[str] = None) -> FetchResult:
    """
    模块级便捷函数。

    @param request: FetchRequest
    @param accounts_path: 可选配置路径
    @returns: FetchResult
    """
    return FetchService(accounts_path=accounts_path).fetch_slot(request)
