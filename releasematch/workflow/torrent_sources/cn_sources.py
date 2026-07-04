#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华语专用源清单与逐源探测 — 不含 thepiratebay / 1337x 等国际聚合。

@module workflow.torrent_sources.cn_sources
@description
  Layer 2F DMHy、Mikan、ACG.RIP、Nyaa 真人/动漫区；供 cn_probe_sources 与 fetch 路由使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from workflow.torrent_sources.asia_region import build_cn_jackett_queries, build_search_titles
from workflow.torrent_sources.config import is_jackett_api_key_configured, load_accounts_config
from workflow.torrent_sources.dmhy_client import DmhyClient
from workflow.torrent_sources.http_fetch import proxy_settings_from_config
from workflow.torrent_sources.jackett_client import JackettClient
from workflow.torrent_sources.models import ResourceItem
from workflow.torrent_sources.nyaa_live_action_client import NyaaLiveActionClient
from workflow.torrent_sources.slot_filter import filter_tv_slot_items

# 默认华语 Jackett indexer（中文向公开站）
DEFAULT_CN_JACKETT_INDEXERS: List[str] = [
    "dmhy",
    "mikan",
    "acgrip",
]

# 默认华语直连源 id
DEFAULT_CN_DIRECT_SOURCES: List[str] = [
    "dmhy",
    "nyaa_live_action",
    "nyaa_anime",
]


@dataclass
class CnSourceProbeResult:
    """
    单华语源探测结果。

    @var source_id: 源标识（dmhy / mikan / nyaa_live_action …）
    @var raw_count: 过滤前条数
    @var filtered_count: 槽位过滤后条数
    @var sample_titles: 样例标题
    @var error: 错误信息
    """

    source_id: str
    raw_count: int = 0
    filtered_count: int = 0
    sample_titles: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return {
            "source_id": self.source_id,
            "raw_count": self.raw_count,
            "filtered_count": self.filtered_count,
            "sample_titles": self.sample_titles,
            "error": self.error,
            "ok": self.error is None and self.filtered_count > 0,
        }


def resolve_cn_source_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """
    解析 accounts 中华语专用源配置。

    @param cfg: load_accounts_config 产物；None 时自动加载
    @returns: jackett 与 direct 源 id 列表
    """
    data = cfg or load_accounts_config()
    block = data.get("cn_sources") or {}
    return {
        "jackett": list(block.get("jackett") or DEFAULT_CN_JACKETT_INDEXERS),
        "direct": list(block.get("direct") or DEFAULT_CN_DIRECT_SOURCES),
    }


class CnSourceProber:
    """
    华语源逐源探测（不走 EZTV/YTS/国际 Jackett）。

    @param accounts_path: 可选 accounts 配置路径
    """

    def __init__(self, accounts_path: Optional[str] = None) -> None:
        from pathlib import Path

        path = Path(accounts_path) if accounts_path else None
        self._cfg = load_accounts_config(path)
        self._sources = resolve_cn_source_config(self._cfg)
        rate = float(self._cfg.get("rate_limit", {}).get("min_interval_sec", 2.0))
        proxy = proxy_settings_from_config(self._cfg.get("proxy"))

        dmhy_cfg = self._cfg.get("dmhy", {})
        self._dmhy = DmhyClient(
            base_url=str(dmhy_cfg.get("base_url") or "https://share.dmhy.org"),
            mirrors=list(dmhy_cfg.get("mirrors") or []),
            min_interval_sec=max(rate, 3.0),
            enabled=bool(dmhy_cfg.get("enabled", True)),
            proxy=proxy,
        )
        nyaa_cfg = self._cfg.get("nyaa", {})
        la_cfg = self._cfg.get("nyaa_live_action", {})
        anime_cfg = self._cfg.get("nyaa_anime", {})
        base = str(nyaa_cfg.get("base_url") or "https://nyaa.si")
        mirrors = list(nyaa_cfg.get("mirrors") or [])
        self._nyaa_la = NyaaLiveActionClient(
            base_url=str(la_cfg.get("base_url") or base),
            mirrors=list(la_cfg.get("mirrors") or mirrors),
            min_interval_sec=max(rate, 3.0),
            enabled=bool(la_cfg.get("enabled", True)),
            proxy=proxy,
            category=str(la_cfg.get("category") or "4_0"),
        )
        self._nyaa_anime = NyaaLiveActionClient(
            base_url=str(anime_cfg.get("base_url") or base),
            mirrors=list(anime_cfg.get("mirrors") or mirrors),
            min_interval_sec=max(rate, 3.0),
            enabled=bool(anime_cfg.get("enabled", True)),
            proxy=proxy,
            category=str(anime_cfg.get("category") or "1_0"),
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

    def probe_tv_slot(
        self,
        metadata: Dict[str, Any],
        season: int,
        episode: int,
    ) -> List[CnSourceProbeResult]:
        """
        对单剧集槽逐华语源探测。

        @param metadata: enrich_external_ids 字典
        @param season: 季号
        @param episode: 集号
        @returns: 各源探测结果
        """
        search_titles = build_search_titles(metadata, "cn")
        show_title = search_titles[0] if search_titles else metadata.get("title")
        alt = search_titles[1:] if len(search_titles) > 1 else None
        queries = build_cn_jackett_queries(search_titles, season, episode)[:6]

        results: List[CnSourceProbeResult] = []
        for source_id in self._sources["direct"]:
            results.append(
                self._probe_direct(source_id, search_titles, queries, season, episode)
            )
        for indexer in self._sources["jackett"]:
            results.append(
                self._probe_jackett_indexer(
                    indexer,
                    queries,
                    show_title,
                    season,
                    episode,
                    alt,
                )
            )
        return results

    def _filter_tv(
        self,
        items: List[ResourceItem],
        show_title: Optional[str],
        season: int,
        episode: int,
        alt_titles: Optional[List[str]],
    ) -> List[ResourceItem]:
        """
        槽位标题过滤。

        @param items: 原始列表
        @param show_title: 主搜索标题
        @param season: 季号
        @param episode: 集号
        @param alt_titles: 备用标题
        @returns: 过滤后列表
        """
        return filter_tv_slot_items(
            items,
            show_title=show_title,
            season=season,
            episode=episode,
            alt_titles=alt_titles,
        )

    def _probe_direct(
        self,
        source_id: str,
        search_titles: List[str],
        queries: List[str],
        season: int,
        episode: int,
    ) -> CnSourceProbeResult:
        """
        探测直连华语源。

        @param source_id: dmhy | nyaa_live_action | nyaa_anime
        @param search_titles: 多语言标题
        @param queries: Jackett 风格查询词（Nyaa 回退用）
        @param season: 季号
        @param episode: 集号
        @returns: CnSourceProbeResult
        """
        show_title = search_titles[0] if search_titles else None
        alt = search_titles[1:] if len(search_titles) > 1 else None
        raw: List[ResourceItem] = []
        try:
            if source_id == "dmhy" and self._dmhy.enabled:
                raw = self._dmhy.fetch_episode_titles(search_titles, season, episode)
            elif source_id == "nyaa_live_action" and self._nyaa_la.enabled:
                raw = self._nyaa_la.fetch_episode_titles(search_titles, season, episode)
                if not raw:
                    for q in queries[:3]:
                        try:
                            raw.extend(self._nyaa_la.search_rss(q, limit=30))
                        except Exception:
                            continue
            elif source_id == "nyaa_anime" and self._nyaa_anime.enabled:
                raw = self._nyaa_anime.fetch_episode_titles(search_titles, season, episode)
                if not raw:
                    for q in queries[:3]:
                        try:
                            batch = self._nyaa_anime.search_rss(q, limit=30)
                            for item in batch:
                                item.indexer = "nyaa_anime"
                            raw.extend(batch)
                        except Exception:
                            continue
            else:
                return CnSourceProbeResult(source_id=source_id, error="disabled_or_unknown")
        except Exception as exc:  # noqa: BLE001
            return CnSourceProbeResult(source_id=source_id, error=str(exc))

        filtered = self._filter_tv(raw, show_title, season, episode, alt)
        return CnSourceProbeResult(
            source_id=source_id,
            raw_count=len(raw),
            filtered_count=len(filtered),
            sample_titles=[i.title_raw[:80] for i in filtered[:3]],
        )

    def _probe_jackett_indexer(
        self,
        indexer: str,
        queries: List[str],
        show_title: Optional[str],
        season: int,
        episode: int,
        alt_titles: Optional[List[str]],
    ) -> CnSourceProbeResult:
        """
        探测单个华语 Jackett indexer。

        @param indexer: Jackett id（dmhy / mikan / acgrip）
        @param queries: 搜索词列表
        @param show_title: 主标题
        @param season: 季号
        @param episode: 集号
        @param alt_titles: 备用标题
        @returns: CnSourceProbeResult
        """
        if not self._jackett:
            return CnSourceProbeResult(
                source_id=f"jackett:{indexer}",
                error="jackett_not_configured",
            )
        raw: List[ResourceItem] = []
        try:
            for query in queries[:4]:
                try:
                    raw.extend(self._jackett.search_text(indexer, query))
                except Exception:
                    continue
        except Exception as exc:  # noqa: BLE001
            return CnSourceProbeResult(
                source_id=f"jackett:{indexer}",
                error=str(exc),
            )

        filtered = self._filter_tv(raw, show_title, season, episode, alt_titles)
        return CnSourceProbeResult(
            source_id=f"jackett:{indexer}",
            raw_count=len(raw),
            filtered_count=len(filtered),
            sample_titles=[i.title_raw[:80] for i in filtered[:3]],
        )
