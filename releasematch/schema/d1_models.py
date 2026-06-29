#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch Cloudflare D1 线上数据模型（Python dataclass）。

@module schema.d1_models
@description
  与 schema/d1_schema.sql 表结构一一对应，供：
    - sync Worker 序列化/反序列化
    - portal/generator/generate_one.py 读 D1 后组装 Jinja2 上下文
    - workflow 批补管道写入 D1 前的类型校验

UI 映射见 d1_schema.sql 文件头注释。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 常量：页面类型、作品类型、页面状态（与 SQL CHECK 约束一致）
# ---------------------------------------------------------------------------

PAGE_TYPE_EPISODE: str = "episode"
PAGE_TYPE_MOVIE: str = "movie"
PAGE_TYPE_SHOW_HUB: str = "show_hub"

MEDIA_KIND_TV: str = "tv"
MEDIA_KIND_MOVIE: str = "movie"

MEDIA_TYPE_TV_EPISODE: str = "tv_episode"
MEDIA_TYPE_MOVIE: str = "movie"

PAGE_STATUS_DRAFT: str = "draft"
PAGE_STATUS_PUBLISHED: str = "published"
PAGE_STATUS_THIN: str = "thin"

GROUP_TIERS: tuple[str, ...] = ("L0", "L1", "L2", "L3", "L4")

TMDB_POSTER_BASE: str = "https://image.tmdb.org/t/p/w300"


def build_catalog_id(tmdb_id: int, media_kind: str) -> str:
    """
    生成 media_catalog 主键。

    @param tmdb_id: TMDB 作品 ID
    @param media_kind: tv 或 movie
    @returns: 如 tv:1396 或 movie:27205
    """
    return f"{media_kind}:{tmdb_id}"


def build_page_id(
    tmdb_id: int,
    media_kind: str,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    page_type: str = PAGE_TYPE_EPISODE,
) -> str:
    """
    生成 media_pages 主键。

    @param tmdb_id: TMDB 作品 ID
    @param media_kind: tv 或 movie
    @param season: 季号（单集必填）
    @param episode: 集号（单集必填）
    @param page_type: episode | movie | show_hub
    @returns: 如 tv:1396:s04e06、movie:27205、tv:1396:hub
    """
    if page_type == PAGE_TYPE_SHOW_HUB:
        return f"{media_kind}:{tmdb_id}:hub"
    if page_type == PAGE_TYPE_MOVIE or media_kind == MEDIA_KIND_MOVIE:
        return f"movie:{tmdb_id}"
    s = season or 0
    e = episode or 0
    return f"tv:{tmdb_id}:s{s:02d}e{e:02d}"


def format_size_human(size_bytes: int) -> str:
    """
    将字节数格式化为 UI 展示文本（如 2.4 GB）。

    @param size_bytes: 文件大小（字节）
    @returns: 人类可读字符串
    """
    if size_bytes <= 0:
        return "—"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    mb = size_bytes / (1024 ** 2)
    return f"{mb:.0f} MB"


def poster_url_from_path(poster_path: str) -> str:
    """
    拼接 TMDB 海报完整 URL。

    @param poster_path: TMDB poster_path 或已含 /t/p/ 前缀的路径
    @returns: 可直接用于 img src 的 URL
    """
    if not poster_path:
        return ""
    if poster_path.startswith("http"):
        return poster_path
    if poster_path.startswith("/t/p/"):
        return f"https://image.tmdb.org{poster_path}"
    return f"{TMDB_POSTER_BASE}{poster_path}"


@dataclass
class ReleaseGroup:
    """
    release_groups 表一行 — Recommended 卡片 Group Badge。

    @var name: 压制组 canonical 名
    @var aliases: 别名列表
    @var tier: L0~L4 信誉档
    @var scene_compliant: 是否 Scene 合规
    @var compliance_rate: 合规率 0~1
    @var notes: 运营备注
    @var updated_at: ISO8601 UTC
    """

    name: str
    tier: str = "L4"
    aliases: List[str] = field(default_factory=list)
    scene_compliant: bool = False
    compliance_rate: float = 0.0
    notes: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "ReleaseGroup":
        """从 D1 查询行构造实例。"""
        aliases_raw = row.get("aliases") or "[]"
        aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
        return cls(
            name=str(row["name"]),
            tier=str(row.get("tier") or "L4"),
            aliases=list(aliases),
            scene_compliant=bool(row.get("scene_compliant")),
            compliance_rate=float(row.get("compliance_rate") or 0.0),
            notes=str(row.get("notes") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )


@dataclass
class MediaCatalog:
    """
    media_catalog 表一行 — 作品主数据（Hub / 侧栏）。

    @var catalog_id: 主键 tv:1396 | movie:27205
    @var tmdb_id: TMDB ID
    @var media_kind: tv | movie
    @var slug: URL slug
    @var title: 作品标题
    @var overview: 简介
    @var year: 年份
    @var runtime_minutes: 电影片长
    @var poster_path: TMDB poster path
    @var tmdb_url: TMDB 外链
    @var streaming_providers: Watch On 列表
    @var subtitle_url_pattern: 字幕站 URL 模板
    @var updated_at: ISO8601 UTC
    """

    catalog_id: str
    tmdb_id: int
    media_kind: str
    slug: str
    title: str
    overview: str = ""
    year: Optional[int] = None
    runtime_minutes: Optional[int] = None
    poster_path: str = ""
    tmdb_url: str = ""
    streaming_providers: List[str] = field(default_factory=list)
    subtitle_url_pattern: str = ""
    updated_at: str = ""

    def poster_url(self) -> str:
        """返回侧栏海报完整 URL。"""
        return poster_url_from_path(self.poster_path)

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "MediaCatalog":
        """从 D1 查询行构造实例。"""
        providers_raw = row.get("streaming_providers") or "[]"
        providers = json.loads(providers_raw) if isinstance(providers_raw, str) else providers_raw
        return cls(
            catalog_id=str(row["catalog_id"]),
            tmdb_id=int(row["tmdb_id"]),
            media_kind=str(row["media_kind"]),
            slug=str(row["slug"]),
            title=str(row["title"]),
            overview=str(row.get("overview") or ""),
            year=int(row["year"]) if row.get("year") is not None else None,
            runtime_minutes=int(row["runtime_minutes"]) if row.get("runtime_minutes") is not None else None,
            poster_path=str(row.get("poster_path") or ""),
            tmdb_url=str(row.get("tmdb_url") or ""),
            streaming_providers=list(providers),
            subtitle_url_pattern=str(row.get("subtitle_url_pattern") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )


@dataclass
class MediaPage:
    """
    media_pages 表一行 — 可发布页面槽位。

    @var page_id: 主键
    @var catalog_id: 关联作品
    @var page_type: episode | movie | show_hub
    @var season: 季号
    @var episode: 集号
    @var episode_title: 单集标题
    @var air_date: 播出日
    @var overview: 槽位简介
    @var cross_source_count: Hero 跨源 badge 分子
    @var cross_source_total: Hero 跨源 badge 分母
    @var prev_season: 上一集季号
    @var prev_episode: 上一集集号
    @var next_season: 下一集季号
    @var next_episode: 下一集集号
    @var magnet_count: magnet 条数（薄页门禁）
    @var page_status: draft | published | thin
    @var robots_noindex: 是否 noindex
    @var canonical_path: canonical URL 路径
    @var subtitle_url: 字幕站完整链接
    @var generated_at: 最近生成静态页时间
    @var updated_at: ISO8601 UTC
    """

    page_id: str
    catalog_id: str
    page_type: str
    canonical_path: str
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: str = ""
    air_date: str = ""
    overview: str = ""
    cross_source_count: int = 0
    cross_source_total: int = 3
    prev_season: Optional[int] = None
    prev_episode: Optional[int] = None
    next_season: Optional[int] = None
    next_episode: Optional[int] = None
    magnet_count: int = 0
    page_status: str = PAGE_STATUS_DRAFT
    robots_noindex: bool = False
    subtitle_url: str = ""
    generated_at: Optional[str] = None
    updated_at: str = ""

    def is_indexable(self) -> bool:
        """
        薄页门禁：magnet ≥ 2 且非 noindex 才允许 index。

        @returns: 是否应输出 index,follow
        """
        return self.magnet_count >= 2 and not self.robots_noindex

    def prev_episode_path(self, slug: str) -> Optional[str]:
        """
        生成上一集 URL 路径。

        @param slug: 作品 slug
        @returns: 如 /breaking-bad/s4e5/ 或 None
        """
        if self.prev_season is None or self.prev_episode is None:
            return None
        return f"/{slug}/s{self.prev_season}e{self.prev_episode}/"

    def next_episode_path(self, slug: str) -> Optional[str]:
        """
        生成下一集 URL 路径。

        @param slug: 作品 slug
        @returns: 如 /breaking-bad/s4e7/ 或 None
        """
        if self.next_season is None or self.next_episode is None:
            return None
        return f"/{slug}/s{self.next_season}e{self.next_episode}/"

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "MediaPage":
        """从 D1 查询行构造实例。"""
        return cls(
            page_id=str(row["page_id"]),
            catalog_id=str(row["catalog_id"]),
            page_type=str(row["page_type"]),
            canonical_path=str(row["canonical_path"]),
            season=int(row["season"]) if row.get("season") is not None else None,
            episode=int(row["episode"]) if row.get("episode") is not None else None,
            episode_title=str(row.get("episode_title") or ""),
            air_date=str(row.get("air_date") or ""),
            overview=str(row.get("overview") or ""),
            cross_source_count=int(row.get("cross_source_count") or 0),
            cross_source_total=int(row.get("cross_source_total") or 3),
            prev_season=int(row["prev_season"]) if row.get("prev_season") is not None else None,
            prev_episode=int(row["prev_episode"]) if row.get("prev_episode") is not None else None,
            next_season=int(row["next_season"]) if row.get("next_season") is not None else None,
            next_episode=int(row["next_episode"]) if row.get("next_episode") is not None else None,
            magnet_count=int(row.get("magnet_count") or 0),
            page_status=str(row.get("page_status") or PAGE_STATUS_DRAFT),
            robots_noindex=bool(row.get("robots_noindex")),
            subtitle_url=str(row.get("subtitle_url") or ""),
            generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
            updated_at=str(row.get("updated_at") or ""),
        )


@dataclass
class DownloadResource:
    """
    download_resources 表一行 — 单条 magnet / release。

    @var id: 主键（通常等于 infohash）
    @var page_id: 所属页面槽位
    @var tmdb_id: TMDB ID（冗余）
    @var media_type: tv_episode | movie
    @var season: 季号
    @var episode: 集号
    @var infohash: 40 字符 infohash
    @var title_raw: Release 标题
    @var release_group: 压制组
    @var source: WEB-DL / BluRay 等
    @var resolution: 1080p 等
    @var codec: H.264 等
    @var video_spec: 卡片 Video 行
    @var audio_spec: 卡片 Audio 行
    @var size_bytes: 体积（字节）
    @var seeders: 做种数
    @var peers: 连接数
    @var magnet_uri: magnet 链接
    @var indexer: 数据源标识
    @var is_recommended: 是否本站推荐
    @var match_score: 评分
    @var recommend_reason: 推荐理由
    @var group_tier: L0~L4
    @var cross_source_count: 跨源命中数
    @var cross_source_confidence: 跨源置信度
    @var indexed_at: 入库时间
    @var expires_at: 过期时间
    """

    id: str
    page_id: str
    tmdb_id: int
    media_type: str
    infohash: str
    title_raw: str
    season: Optional[int] = None
    episode: Optional[int] = None
    release_group: str = ""
    source: str = ""
    resolution: str = ""
    codec: str = ""
    video_spec: str = ""
    audio_spec: str = ""
    size_bytes: int = 0
    seeders: int = 0
    peers: int = 0
    magnet_uri: str = ""
    indexer: str = ""
    is_recommended: bool = False
    match_score: float = 0.0
    recommend_reason: str = ""
    group_tier: str = "L4"
    cross_source_count: int = 1
    cross_source_confidence: float = 0.0
    indexed_at: str = ""
    expires_at: str = ""

    @property
    def size_human(self) -> str:
        """UI All Sources 表 Size 列。"""
        return format_size_human(self.size_bytes)

    def to_template_dict(self) -> Dict[str, Any]:
        """
        转为 Jinja2 sources / recommended 循环项字典。

        @returns: 含 size_human、is_recommended 等渲染字段
        """
        data = asdict(self)
        data["size_human"] = self.size_human
        data["is_recommended"] = self.is_recommended
        data["speed"] = ""  # 可由 slot_speed_summary 或 per-hash 测速填充
        return data

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "DownloadResource":
        """从 D1 查询行构造实例。"""
        return cls(
            id=str(row["id"]),
            page_id=str(row["page_id"]),
            tmdb_id=int(row["tmdb_id"]),
            media_type=str(row["media_type"]),
            infohash=str(row["infohash"]),
            title_raw=str(row["title_raw"]),
            season=int(row["season"]) if row.get("season") is not None else None,
            episode=int(row["episode"]) if row.get("episode") is not None else None,
            release_group=str(row.get("release_group") or ""),
            source=str(row.get("source") or ""),
            resolution=str(row.get("resolution") or ""),
            codec=str(row.get("codec") or ""),
            video_spec=str(row.get("video_spec") or ""),
            audio_spec=str(row.get("audio_spec") or ""),
            size_bytes=int(row.get("size_bytes") or 0),
            seeders=int(row.get("seeders") or 0),
            peers=int(row.get("peers") or 0),
            magnet_uri=str(row.get("magnet_uri") or ""),
            indexer=str(row.get("indexer") or ""),
            is_recommended=bool(row.get("is_recommended")),
            match_score=float(row.get("match_score") or 0.0),
            recommend_reason=str(row.get("recommend_reason") or ""),
            group_tier=str(row.get("group_tier") or "L4"),
            cross_source_count=int(row.get("cross_source_count") or 1),
            cross_source_confidence=float(row.get("cross_source_confidence") or 0.0),
            indexed_at=str(row.get("indexed_at") or ""),
            expires_at=str(row.get("expires_at") or ""),
        )


@dataclass
class SlotSpeedSummary:
    """
    slot_speed_summary 表一行 — 测速摘要条（T2）。

    @var page_id: 页面槽位主键
    @var recommended_infohash: 对应 Recommended release
    @var recommended_speed: 展示速度文本
    @var reachability: 可达性：高/中/低
    @var updated_at: ISO8601 UTC
    """

    page_id: str
    recommended_speed: str = ""
    reachability: str = ""
    recommended_infohash: str = ""
    updated_at: str = ""

    def to_template_dict(self) -> Dict[str, Any]:
        """转为 episode.html speed_summary 上下文。"""
        return {
            "recommended_speed": self.recommended_speed,
            "reachability": self.reachability,
            "updated_at": self.updated_at[:10] if self.updated_at else "",
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "SlotSpeedSummary":
        """从 D1 查询行构造实例。"""
        return cls(
            page_id=str(row["page_id"]),
            recommended_speed=str(row.get("recommended_speed") or ""),
            reachability=str(row.get("reachability") or ""),
            recommended_infohash=str(row.get("recommended_infohash") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )


@dataclass
class SpeedTestResult:
    """
    speedtest_results 表一行 — 单 magnet 测速明细。

    @var id: 主键 uuid
    @var infohash: magnet infohash
    @var page_id: 可选关联页面
    @var phase: 1=连接性 2=片段测速
    @var peers_reachable: 可达 peer 数
    @var peers_total: 总 peer 数
    @var avg_kbps: 平均 KB/s
    @var max_kbps: 峰值 KB/s
    @var latency_ms: 延迟毫秒
    @var status: ok | timeout | error
    @var tested_at: 测试时间 ISO8601
    """

    id: str
    infohash: str
    phase: int = 1
    page_id: Optional[str] = None
    peers_reachable: int = 0
    peers_total: int = 0
    avg_kbps: float = 0.0
    max_kbps: float = 0.0
    latency_ms: int = 0
    status: str = "ok"
    tested_at: str = ""

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "SpeedTestResult":
        """从 D1 查询行构造实例。"""
        return cls(
            id=str(row["id"]),
            infohash=str(row["infohash"]),
            phase=int(row.get("phase") or 1),
            page_id=str(row["page_id"]) if row.get("page_id") else None,
            peers_reachable=int(row.get("peers_reachable") or 0),
            peers_total=int(row.get("peers_total") or 0),
            avg_kbps=float(row.get("avg_kbps") or 0.0),
            max_kbps=float(row.get("max_kbps") or 0.0),
            latency_ms=int(row.get("latency_ms") or 0),
            status=str(row.get("status") or "ok"),
            tested_at=str(row.get("tested_at") or ""),
        )


@dataclass
class EpisodePageContext:
    """
    单集页 Jinja2 完整上下文 — 聚合 D1 多表查询结果。

    @var catalog: 作品主数据
    @var page: 页面槽位
    @var sources: All Sources 列表（含 recommended）
    @var recommended: Recommended release（sources 中 is_recommended=1）
    @var speed_summary: 测速摘要条（可选）
    @var canonical_url: 完整 canonical URL
    """

    catalog: MediaCatalog
    page: MediaPage
    sources: List[DownloadResource]
    recommended: Optional[DownloadResource] = None
    speed_summary: Optional[SlotSpeedSummary] = None
    canonical_url: str = ""

    def to_template_context(self, site_origin: str = "https://releasematch.io") -> Dict[str, Any]:
        """
        组装 episode.html 渲染上下文。

        @param site_origin: 站点 origin，用于 canonical 与 prev/next 绝对 URL
        @returns: Jinja2 render 参数字典
        """
        slug = self.catalog.slug
        recommended = self.recommended
        if recommended and self.speed_summary and self.speed_summary.recommended_speed:
            rec_dict = recommended.to_template_dict()
            rec_dict["speed"] = self.speed_summary.recommended_speed
        elif recommended:
            rec_dict = recommended.to_template_dict()
        else:
            rec_dict = None

        prev_path = self.page.prev_episode_path(slug)
        next_path = self.page.next_episode_path(slug)

        return {
            "show_title": self.catalog.title,
            "show_slug": slug,
            "season": self.page.season,
            "episode": self.page.episode,
            "air_date": self.page.air_date,
            "episode_overview": self.page.overview or self.catalog.overview,
            "cross_source_count": self.page.cross_source_count,
            "cross_source_total": self.page.cross_source_total,
            "speed_summary": self.speed_summary.to_template_dict() if self.speed_summary else None,
            "recommended": rec_dict,
            "recommended_quality": recommended.resolution if recommended else "",
            "sources": [s.to_template_dict() for s in self.sources],
            "source_count": len(self.sources),
            "prev_episode_url": f"{site_origin}{prev_path}" if prev_path else None,
            "prev_episode_label": (
                f"S{self.page.prev_season:02d}E{self.page.prev_episode:02d}"
                if prev_path
                else None
            ),
            "next_episode_url": f"{site_origin}{next_path}" if next_path else None,
            "next_episode_label": (
                f"S{self.page.next_season:02d}E{self.page.next_episode:02d}"
                if next_path
                else None
            ),
            "poster_url": self.catalog.poster_url(),
            "tmdb_overview": self.page.overview,
            "tmdb_url": (
                f"https://www.themoviedb.org/tv/{self.catalog.tmdb_id}"
                f"/season/{self.page.season}/episode/{self.page.episode}"
                if self.page.season and self.page.episode
                else self.catalog.tmdb_url
            ),
            "streaming_providers": self.catalog.streaming_providers,
            "subtitle_url": self.page.subtitle_url,
            "canonical_url": self.canonical_url or f"{site_origin}{self.page.canonical_path}",
            "robots_noindex": not self.page.is_indexable(),
            "meta_description": (
                f"{self.catalog.title} 第 {self.page.season} 季第 {self.page.episode} 集 "
                f"Release 导航：本站 Recommended Release、{len(self.sources)} 条多源对比与对版说明。"
            ),
        }
