#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
torrent_sources 数据模型。

@module workflow.torrent_sources.models
@description ResourceItem / FetchRequest / FetchResult 定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MediaType(str, Enum):
    """TMDB 媒体类型。"""

    MOVIE = "movie"
    TV = "tv"


class FetchMode(str, Enum):
    """拉取模式。"""

    BATCH = "batch"
    ON_DEMAND = "on_demand"


@dataclass
class FetchRequest:
    """
    单次资源清单拉取请求。

    @var tmdb_id: TMDB 作品 ID
    @var media_type: movie 或 tv
    @var season: 季号（电影为 None）
    @var episode: 集号（电影为 None）
    @var imdb_id: IMDb ID
    @var tvdb_id: TVDB ID（剧集 Jackett 搜索）
    @var mode: batch 或 on_demand
    @var force: 忽略缓存强制重爬
    """

    tmdb_id: int
    media_type: MediaType
    season: Optional[int] = None
    episode: Optional[int] = None
    imdb_id: Optional[str] = None
    tvdb_id: Optional[int] = None
    mode: FetchMode = FetchMode.ON_DEMAND
    force: bool = False

    def cache_key(self) -> str:
        """
        生成缓存唯一键。

        @returns: 如 movie:603 或 tv:1396:s04e06
        """
        if self.media_type == MediaType.MOVIE:
            return f"movie:{self.tmdb_id}"
        s = self.season or 0
        e = self.episode or 0
        return f"tv:{self.tmdb_id}:s{s:02d}e{e:02d}"


@dataclass
class ResourceItem:
    """
    归一化后的单条 torrent 元数据。

    @var infohash: 40 字符 infohash（小写）
    @var title_raw: 原始 release 标题
    @var release_group: 压制组名
    @var source: WEB-DL / BluRay 等
    @var resolution: 1080p / 720p 等
    @var codec: H.264 / HEVC 等
    @var size_bytes: 文件大小
    @var seeders: 做种数
    @var peers: 连接数
    @var magnet_uri: magnet 链接
    @var indexer: 来源 indexer 标识
    @var cross_source_count: 出现在几个数据源（跨源验证后填充）
    @var cross_source_confidence: 跨源置信度 cross_count / total_sources
    """

    infohash: str
    title_raw: str
    release_group: str = ""
    source: str = ""
    resolution: str = ""
    codec: str = ""
    size_bytes: int = 0
    seeders: int = 0
    peers: int = 0
    magnet_uri: str = ""
    indexer: str = ""
    cross_source_count: int = 1
    cross_source_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "infohash": self.infohash,
            "title_raw": self.title_raw,
            "release_group": self.release_group,
            "source": self.source,
            "resolution": self.resolution,
            "codec": self.codec,
            "size_bytes": self.size_bytes,
            "seeders": self.seeders,
            "peers": self.peers,
            "magnet_uri": self.magnet_uri,
            "indexer": self.indexer,
            "cross_source_count": self.cross_source_count,
            "cross_source_confidence": self.cross_source_confidence,
        }


@dataclass
class FetchResult:
    """
    单次槽位拉取结果。

    @var request: 原始请求
    @var items: 归一化后的资源列表
    @var cached: 是否命中本地缓存
    @var error: 失败原因
    """

    request: FetchRequest
    items: List[ResourceItem] = field(default_factory=list)
    cached: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "request": {
                "tmdb_id": self.request.tmdb_id,
                "media_type": self.request.media_type.value,
                "season": self.request.season,
                "episode": self.request.episode,
                "cache_key": self.request.cache_key(),
            },
            "items": [i.to_dict() for i in self.items],
            "count": len(self.items),
            "cached": self.cached,
            "error": self.error,
        }
