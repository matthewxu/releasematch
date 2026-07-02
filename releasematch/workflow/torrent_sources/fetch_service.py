#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源拉取编排层。

@module workflow.torrent_sources.fetch_service
@description 缓存、EZTV/YTS/Nyaa/Jackett 串行拉取、跨源聚合、release 解析。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from workflow.metadata.external_ids import resolve_external_ids
from workflow.torrent_sources.asia_region import (
    build_search_titles,
    detect_content_region,
)
from workflow.torrent_sources.cache_index import CacheIndex
from workflow.torrent_sources.config import (
    is_jackett_api_key_configured,
    load_accounts_config,
)
from workflow.torrent_sources.cross_source import (
    compute_page_cross_source,
    count_attempted_families,
    merge_by_infohash,
)
from workflow.torrent_sources.eztv_client import EztvClient
from workflow.torrent_sources.http_fetch import proxy_settings_from_config
from workflow.torrent_sources.jackett_client import JackettClient
from workflow.torrent_sources.models import FetchRequest, FetchResult, MediaType, ResourceItem
from workflow.torrent_sources.nyaa_client import NyaaClient
from workflow.torrent_sources.nyaa_live_action_client import NyaaLiveActionClient
from workflow.torrent_sources.release_parser import parse_release_title
from workflow.torrent_sources.slot_filter import filter_tv_slot_items
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
        cross_source_confidence=float(row.get("cross_source_confidence") or 0.0),
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
    兼容旧调用：按 infohash 去重（无跨源分母时默认分母为 1）。

    @param items: 原始列表
    @returns: 去重后列表
    """
    return merge_by_infohash(items, total_source_families=1)


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
        nyaa_cfg = self._cfg.get("nyaa", {})
        nyaa_la_cfg = self._cfg.get("nyaa_live_action", {})
        self._proxy = proxy_settings_from_config(self._cfg.get("proxy"))
        self._eztv = EztvClient(
            base_url=str(eztv_cfg.get("base_url") or "https://eztvx.to"),
            min_interval_sec=rate,
        )
        self._yts = YtsClient(
            base_url=str(yts_cfg.get("base_url") or "https://yts.lt"),
            min_interval_sec=rate,
        )
        self._nyaa = NyaaClient(
            base_url=str(nyaa_cfg.get("base_url") or "https://nyaa.si"),
            mirrors=list(nyaa_cfg.get("mirrors") or []),
            min_interval_sec=max(rate, 3.0),
            enabled=bool(nyaa_cfg.get("enabled", True)),
            proxy=self._proxy,
        )
        la_base = str(nyaa_la_cfg.get("base_url") or nyaa_cfg.get("base_url") or "https://nyaa.si")
        la_mirrors = list(nyaa_la_cfg.get("mirrors") or nyaa_cfg.get("mirrors") or [])
        self._nyaa_la = NyaaLiveActionClient(
            base_url=la_base,
            mirrors=la_mirrors,
            min_interval_sec=max(rate, 3.0),
            enabled=bool(nyaa_la_cfg.get("enabled", True)),
            proxy=self._proxy,
            category=str(nyaa_la_cfg.get("category") or "4_0"),
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
        idx = jackett_cfg.get("indexers", {})
        self._jackett_indexers: Dict[str, List[str]] = {
            "tv": list(idx.get("tv") or ["all"]),
            "movie": list(idx.get("movie") or ["all"]),
            "jp_tv": list(idx.get("jp_tv") or idx.get("tv") or []),
            "kr_tv": list(idx.get("kr_tv") or idx.get("tv") or []),
            "jp_movie": list(idx.get("jp_movie") or idx.get("movie") or []),
            "kr_movie": list(idx.get("kr_movie") or idx.get("movie") or []),
        }

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
                    if not payload:
                        pass
                    else:
                        items = [_item_from_dict(row) for row in payload]
                        page_count, page_total = compute_page_cross_source(
                            items,
                            media_type=request.media_type.value,
                        )
                        return FetchResult(
                            request=request,
                            items=items,
                            cached=True,
                            cross_source_page_count=page_count,
                            cross_source_page_total=page_total,
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

        try:
            raw_items, source_enabled = self._fetch_from_sources(request)
        except Exception as exc:  # noqa: BLE001 — 汇总到 FetchResult.error
            return FetchResult(request=request, items=[], error=str(exc))

        page_count, page_total = compute_page_cross_source(
            raw_items,
            source_enabled=source_enabled,
            media_type=request.media_type.value,
        )
        parsed = [_apply_parser(item) for item in raw_items]
        total_families = count_attempted_families(source_enabled)
        merged = merge_by_infohash(parsed, total_source_families=total_families)
        if merged:
            expires = _utc_expires_iso(self._cache_ttl_hours)
            self._cache.upsert(
                cache_key=cache_key,
                tmdb_id=request.tmdb_id,
                media_type=request.media_type.value,
                payload=[item.to_dict() for item in merged],
                expires_at=expires,
                season=request.season,
                episode=request.episode,
            )
        return FetchResult(
            request=request,
            items=merged,
            cached=False,
            cross_source_page_count=page_count,
            cross_source_page_total=page_total,
        )

    def _fetch_from_sources(
        self,
        request: FetchRequest,
    ) -> Tuple[List[ResourceItem], Dict[str, bool]]:
        """
        按媒体类型调用各 client。

        @param request: FetchRequest
        @returns: (未去重 items, 各源族是否参与拉取)
        """
        if request.media_type == MediaType.TV:
            return self._fetch_tv(request)
        return self._fetch_movie(request)

    def _jackett_tv_indexers_for(self, region: Optional[str]) -> List[str]:
        """
        按内容区域选择 Jackett 剧集 indexer 列表。

        @param region: jp | kr | None
        @returns: indexer id 列表
        """
        if region == "jp":
            return self._jackett_indexers["jp_tv"]
        if region == "kr":
            return self._jackett_indexers["kr_tv"]
        return self._jackett_indexers["tv"]

    def _jackett_movie_indexers_for(self, region: Optional[str]) -> List[str]:
        """
        按内容区域选择 Jackett 电影 indexer 列表。

        @param region: jp | kr | None
        @returns: indexer id 列表
        """
        if region == "jp":
            return self._jackett_indexers["jp_movie"]
        if region == "kr":
            return self._jackett_indexers["kr_movie"]
        return self._jackett_indexers["movie"]

    def _resolve_tv_metadata(self, request: FetchRequest) -> Dict[str, Any]:
        """
        解析剧集元数据（含日韩本地标题）。

        @param request: FetchRequest
        @returns: external_ids 扩展字典
        """
        from workflow.metadata.tmdb_api import enrich_external_ids

        return enrich_external_ids(
            request.tmdb_id,
            "tv",
            title=request.title,
            base={
                "imdb_id": request.imdb_id,
                "tvdb_id": request.tvdb_id,
            },
        )

    def _resolve_movie_metadata(self, request: FetchRequest) -> Dict[str, Any]:
        """
        解析电影元数据（含 slot 标题与 TMDB API 补全 IMDb）。

        @param request: FetchRequest
        @returns: external_ids 扩展字典
        """
        from workflow.metadata.tmdb_api import enrich_external_ids

        return enrich_external_ids(
            request.tmdb_id,
            "movie",
            title=request.title,
            base={
                "imdb_id": request.imdb_id,
                "tvdb_id": request.tvdb_id,
            },
        )

    def _resolve_show_title(self, request: FetchRequest) -> Optional[str]:
        """
        解析剧集/作品搜索标题（英文主标题）。

        @param request: FetchRequest
        @returns: 英文标题或 None
        """
        meta = self._resolve_tv_metadata(request)
        title = meta.get("title")
        return title if isinstance(title, str) and title.strip() else None

    def _fetch_tv(self, request: FetchRequest) -> Tuple[List[ResourceItem], Dict[str, bool]]:
        """
        剧集：欧美 EZTV + Nyaa；日韩 Nyaa LA + Jackett（含槽位标题过滤）。

        @param request: FetchRequest
        @returns: (items, source_enabled)
        """
        meta = self._resolve_tv_metadata(request)
        region = detect_content_region(meta)
        search_titles = build_search_titles(meta, region)
        show_title = search_titles[0] if search_titles else self._resolve_show_title(request)
        alt_titles = search_titles[1:] if len(search_titles) > 1 else None

        items, source_enabled, _ = self._collect_tv_items(request, meta, region, search_titles)
        if (
            show_title
            and request.season is not None
            and request.episode is not None
            and items
        ):
            items = filter_tv_slot_items(
                items,
                show_title=show_title,
                season=request.season,
                episode=request.episode,
                alt_titles=alt_titles,
            )
        return items, source_enabled

    def _collect_tv_items(
        self,
        request: FetchRequest,
        meta: Optional[Dict[str, Any]] = None,
        region: Optional[str] = None,
        search_titles: Optional[List[str]] = None,
    ) -> Tuple[List[ResourceItem], Dict[str, bool], Optional[str]]:
        """
        剧集多源拉取（过滤前原始列表）。

        @param request: FetchRequest
        @param meta: 可选预解析元数据
        @param region: jp | kr | None
        @param search_titles: 多语言搜索词
        @returns: (items, source_enabled, show_title)
        """
        meta = meta or self._resolve_tv_metadata(request)
        region = region if region is not None else detect_content_region(meta)
        search_titles = search_titles or build_search_titles(meta, region)
        show_title = search_titles[0] if search_titles else None

        items: List[ResourceItem] = []
        source_enabled: Dict[str, bool] = {
            "eztv": False,
            "nyaa": False,
            "jackett": bool(self._jackett),
        }
        is_asia = region in ("jp", "kr")

        if (
            not is_asia
            and request.imdb_id
            and request.season is not None
            and request.episode is not None
        ):
            source_enabled["eztv"] = True
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

        if (
            request.season is not None
            and request.episode is not None
            and search_titles
        ):
            if is_asia and self._nyaa_la.enabled:
                source_enabled["nyaa"] = True
                try:
                    items.extend(
                        self._nyaa_la.fetch_episode_titles(
                            search_titles,
                            request.season,
                            request.episode,
                        )
                    )
                except Exception:
                    pass
            elif self._nyaa.enabled and show_title:
                source_enabled["nyaa"] = True
                try:
                    items.extend(
                        self._nyaa.fetch_episode(
                            show_title,
                            request.season,
                            request.episode,
                        )
                    )
                except Exception:
                    pass

        if self._jackett and request.season is not None and request.episode is not None:
            for indexer in self._jackett_tv_indexers_for(region):
                try:
                    items.extend(
                        self._jackett.search_tv(
                            indexer=indexer,
                            tvdb_id=request.tvdb_id,
                            season=request.season,
                            episode=request.episode,
                            query_text=show_title,
                        )
                    )
                except Exception:
                    continue

        return items, source_enabled, show_title

    def _fetch_movie(self, request: FetchRequest) -> Tuple[List[ResourceItem], Dict[str, bool]]:
        """
        电影：YTS + Nyaa LA（日韩）+ Jackett。

        @param request: FetchRequest
        @returns: (items, source_enabled)
        """
        meta = self._resolve_movie_metadata(request)
        region = detect_content_region(meta)
        search_titles = build_search_titles(meta, region)
        is_asia = region in ("jp", "kr")
        imdb_id = request.imdb_id or meta.get("imdb_id")

        items: List[ResourceItem] = []
        source_enabled: Dict[str, bool] = {
            "yts": False,
            "nyaa": False,
            "jackett": bool(self._jackett),
        }

        if not is_asia and imdb_id:
            source_enabled["yts"] = True
            try:
                items.extend(self._yts.fetch_movie(imdb_id))
            except Exception:
                pass

        if is_asia and self._nyaa_la.enabled and search_titles:
            source_enabled["nyaa"] = True
            try:
                items.extend(self._nyaa_la.fetch_movie_titles(search_titles))
            except Exception:
                pass

        if self._jackett and imdb_id:
            for indexer in self._jackett_movie_indexers_for(region):
                try:
                    items.extend(
                        self._jackett.search_movie(
                            indexer=indexer,
                            imdb_id=imdb_id,
                            tmdb_id=request.tmdb_id,
                        )
                    )
                except Exception:
                    continue

        if self._jackett and not items and search_titles:
            for indexer in self._jackett_movie_indexers_for(region):
                for query in search_titles[:2]:
                    try:
                        items.extend(self._jackett.search_text(indexer, query))
                    except Exception:
                        continue
                if items:
                    break

        return items, source_enabled


def fetch_slot(request: FetchRequest, accounts_path: Optional[str] = None) -> FetchResult:
    """
    模块级便捷函数。

    @param request: FetchRequest
    @param accounts_path: 可选配置路径
    @returns: FetchResult
    """
    return FetchService(accounts_path=accounts_path).fetch_slot(request)
