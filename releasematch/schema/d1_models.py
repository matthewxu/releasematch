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
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# torrent 面板：主视频扩展名（与 speedtest/torrent_metadata 一致）
_TORRENT_VIDEO_EXTENSIONS = frozenset(
    {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".m2ts", ".mov", ".webm"}
)


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
    @var overview: 简介（en-US）
    @var overview_zh: 简介（zh-CN）
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
    overview_zh: str = ""
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
            overview_zh=str(row.get("overview_zh") or ""),
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
    @var overview: 槽位简介（en-US）
    @var overview_zh: 槽位简介（zh-CN）
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
    overview_zh: str = ""
    cross_source_count: int = 0
    cross_source_total: int = 4
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

    def is_indexable(self, *, has_recommended: bool = True) -> bool:
        """
        薄页门禁：magnet ≥ 2、有 Recommended、且非 robots noindex 才允许 index。

        @param has_recommended: 槽位是否已产出 Recommended release
        @returns: 是否应输出 index,follow
        """
        if self.magnet_count < 2:
            return False
        if self.robots_noindex:
            return False
        if not has_recommended:
            return False
        return True

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
            overview_zh=str(row.get("overview_zh") or ""),
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
class TorrentMetadataRecord:
    """
    torrent_metadata 表一行 — swarm 侧 torrent 结构（等价 .torrent info）。

    @var infohash: 主键，40 位小写
    @var page_id: 最近关联页面
    @var torrent_name: torrent 名称
    @var total_size_bytes: 总大小
    @var file_count: 文件数
    @var piece_length: piece 大小
    @var is_private: 是否 private
    @var primary_file: 主视频文件路径
    @var primary_file_size_bytes: 主文件大小
    @var files_json: 文件列表 JSON
    @var indexer_size_bytes: 入库时 indexer 体积
    @var size_match: ok | mismatch | unknown
    @var size_delta_bytes: total - indexer
    @var status: ok | no_metadata | error
    @var extracted_at: 提取时间
    """

    infohash: str
    page_id: Optional[str] = None
    torrent_name: str = ""
    total_size_bytes: int = 0
    file_count: int = 0
    piece_length: int = 0
    is_private: bool = False
    primary_file: str = ""
    primary_file_size_bytes: int = 0
    files_json: str = "[]"
    indexer_size_bytes: int = 0
    size_match: str = "unknown"
    size_delta_bytes: int = 0
    status: str = "ok"
    extracted_at: str = ""

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "TorrentMetadataRecord":
        """从 MySQL/D1 查询行构造实例。"""
        return cls(
            infohash=str(row.get("infohash") or ""),
            page_id=str(row["page_id"]) if row.get("page_id") else None,
            torrent_name=str(row.get("torrent_name") or ""),
            total_size_bytes=int(row.get("total_size_bytes") or 0),
            file_count=int(row.get("file_count") or 0),
            piece_length=int(row.get("piece_length") or 0),
            is_private=bool(row.get("is_private")),
            primary_file=str(row.get("primary_file") or ""),
            primary_file_size_bytes=int(row.get("primary_file_size_bytes") or 0),
            files_json=str(row.get("files_json") or "[]"),
            indexer_size_bytes=int(row.get("indexer_size_bytes") or 0),
            size_match=str(row.get("size_match") or "unknown"),
            size_delta_bytes=int(row.get("size_delta_bytes") or 0),
            status=str(row.get("status") or "ok"),
            extracted_at=str(row.get("extracted_at") or ""),
        )


def _torrent_path_basename(path: str) -> str:
    """
    取 torrent 内文件路径的文件名（兼容 / 与 \\）。

    @param path: swarm 内相对路径
    @returns: 文件名或空串
    """
    normalized = (path or "").replace("\\", "/").strip()
    if not normalized:
        return ""
    return normalized.rsplit("/", 1)[-1]


def _sanitize_torrent_display_name(raw_name: str) -> str:
    """
    清理 torrent 根名中的 indexer 垃圾前缀（如 UIndex 文件夹名）。

    @param raw_name: libtorrent torrent_name
    @returns: 适合页面展示的短名称
    """
    name = re.sub(r"\s+", " ", (raw_name or "").strip())
    if not name:
        return ""
    # 常见：www.UIndex.org    -    Show S01E01 ...
    cleaned = re.sub(r"^www\.\S+\s*-\s*", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or name


def _is_torrent_video_path(path: str) -> bool:
    """
    判断路径是否为主视频类扩展名。

    @param path: 文件相对路径
    @returns: True 表示视频文件
    """
    base = _torrent_path_basename(path).lower()
    if not base:
        return False
    dot = base.rfind(".")
    if dot < 0:
        return False
    return base[dot:] in _TORRENT_VIDEO_EXTENSIONS


@dataclass
class TorrentMetadataContext:
    """
    页面 torrent 结构面板上下文 — Recommended release 绑定。

    @var record: DB 行
    @var files: 解析后的文件列表
    """

    record: TorrentMetadataRecord
    files: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: TorrentMetadataRecord) -> "TorrentMetadataContext":
        """
        由 DB 记录构造展示上下文。

        @param record: torrent_metadata 行
        @returns: TorrentMetadataContext
        """
        files: List[Dict[str, Any]] = []
        try:
            parsed = json.loads(record.files_json or "[]")
            if isinstance(parsed, list):
                files = parsed
        except (json.JSONDecodeError, TypeError):
            files = []
        return cls(record=record, files=files)

    def is_publishable(self) -> bool:
        """
        是否 bake 进静态 HTML。

        @returns: True 表示可展示
        """
        return (
            self.record.status == "ok"
            and self.record.total_size_bytes > 0
            and self.record.file_count > 0
        )

    def to_template_dict(self) -> Dict[str, Any]:
        """
        转为 Jinja2 partial 参数字典。

        @returns: torrent_metadata_panel 渲染字段
        """
        rec = self.record
        primary_display = _torrent_path_basename(rec.primary_file)
        sanitized_root = _sanitize_torrent_display_name(rec.torrent_name)
        if not primary_display and sanitized_root:
            primary_display = sanitized_root
        display_name = primary_display or sanitized_root
        size_match_label_key = f"torrent.size_match.{rec.size_match}"
        total_human = format_size_human(rec.total_size_bytes)

        video_rows: List[Dict[str, Any]] = []
        ancillary_count = 0
        for item in self.files:
            raw_path = str(item.get("path") or "")
            size_b = int(item.get("size_bytes") or 0)
            row = {
                "path": raw_path,
                "path_display": _torrent_path_basename(raw_path) or raw_path,
                "size_bytes": size_b,
                "size_human": format_size_human(size_b),
            }
            if _is_torrent_video_path(raw_path):
                video_rows.append(row)
            else:
                ancillary_count += 1

        files_display = video_rows if video_rows else [
            {
                "path": str(item.get("path") or ""),
                "path_display": _torrent_path_basename(str(item.get("path") or ""))
                or str(item.get("path") or ""),
                "size_bytes": int(item.get("size_bytes") or 0),
                "size_human": format_size_human(int(item.get("size_bytes") or 0)),
            }
            for item in self.files
        ]

        return {
            "infohash_short": rec.infohash[:8] if rec.infohash else "",
            "torrent_name": rec.torrent_name,
            "display_name": display_name,
            "total_size_bytes": rec.total_size_bytes,
            "total_size_human": total_human,
            "indexer_size_bytes": rec.indexer_size_bytes,
            "indexer_size_human": format_size_human(rec.indexer_size_bytes),
            "file_count": rec.file_count,
            "video_file_count": len(video_rows) if video_rows else rec.file_count,
            "ancillary_file_count": ancillary_count,
            "piece_length": rec.piece_length,
            "piece_length_human": format_size_human(rec.piece_length) if rec.piece_length else "—",
            "is_private": rec.is_private,
            "primary_file": rec.primary_file,
            "primary_file_display": primary_display,
            "primary_file_size_human": format_size_human(rec.primary_file_size_bytes),
            "size_match": rec.size_match,
            "size_match_label_key": size_match_label_key,
            "size_delta_bytes": rec.size_delta_bytes,
            "files": self.files,
            "files_display": files_display,
            "extracted_at": rec.extracted_at,
            "method_note_key": "torrent.method_note",
            "panel_facts": f"{total_human} · {rec.file_count} files · {rec.size_match}",
        }


def _format_kbps_display(kbps: float) -> str:
    """
    将 KiB/s 格式化为带单位的展示文本。

    @param kbps: 千字节/秒
    @returns: 如 29 KB/s 或 1.2 MB/s
    """
    if kbps <= 0:
        return "—"
    mb_per_sec = kbps / 1024.0
    if mb_per_sec >= 1.0:
        return f"{mb_per_sec:.1f} MB/s"
    return f"{int(round(kbps))} KB/s"


def _format_latency_display(latency_ms: int) -> str:
    """
    将首包延迟毫秒格式化为可读文案（A-09）。

    @param latency_ms: 毫秒
    @returns: 如 21.8 s 或 850 ms
    """
    if latency_ms <= 0:
        return "—"
    if latency_ms >= 1000:
        return f"{latency_ms / 1000:.1f} s"
    return f"{latency_ms} ms"


def _reachability_css_class(reachability: str) -> str:
    """
    可达性等级 → CSS 修饰类名。

    @param reachability: 高/中/低/不可达
    @returns: high | medium | low | unreachable
    """
    mapping = {"高": "high", "中": "medium", "低": "low", "不可达": "unreachable"}
    return mapping.get(reachability, "unknown")


def _format_datetime_utc_display(ts: str) -> str:
    """
    将 MySQL DATETIME 格式化为 UTC 展示（A-03）。

    @param ts: 如 2026-07-02 09:57:10.217
    @returns: 如 2026-07-02 09:57 UTC
    """
    text = (ts or "").strip()
    if not text:
        return ""
    # 去掉毫秒，标注 UTC
    base = text.split(".")[0] if "." in text else text
    if len(base) >= 16:
        return f"{base[:16].replace('T', ' ')} UTC"
    return f"{base} UTC"


def _parse_mysql_utc_datetime(ts: str) -> Optional[datetime]:
    """
    解析 MySQL DATETIME 为 UTC aware datetime。

    @param ts: 时间字符串
    @returns: datetime 或 None
    """
    from datetime import datetime, timezone

    text = (ts or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(text[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _format_age_display(age_hours: float) -> str:
    """
    将距现在的小时数格式化为中文相对时间。

    @param age_hours: 小时数
    @returns: 如「35 分钟前」「2.5 小时前」
    """
    if age_hours < 0:
        age_hours = 0.0
    if age_hours < 1.0:
        minutes = max(1, int(round(age_hours * 60)))
        return f"{minutes} 分钟前"
    if age_hours < 48:
        return f"{age_hours:.1f} 小时前".replace(".0 小时", " 小时")
    days = age_hours / 24.0
    return f"{days:.1f} 天前".replace(".0 天", " 天")


# 测速可信度（A-03）时间窗口（小时）— 与 trust/speed-and-grab 说明页一致
FRESHNESS_FRESH_HOURS: float = 24.0
FRESHNESS_VALID_HOURS: float = 48.0
FRESHNESS_STALE_HOURS: float = 72.0
# 分级边界容差（秒级时间戳往返误差，使 ≤24/48/72h 按「以内」含边界）
FRESHNESS_BOUNDARY_GRACE_HOURS: float = 1.0 / 60.0


def compute_test_freshness(
    tested_at_raw: str,
    *,
    ttl_hours: int = 6,
) -> Dict[str, Any]:
    """
    根据测速时间计算有效性等级（A-03），供页面与 debug 展示。

    分级：≤24h Fresh · ≤48h Valid · ≤72h Stale · >72h Aged（较久，非断言已失效）

    @param tested_at_raw: MySQL tested_at / updated_at 原始值
    @param ttl_hours: cron 增量 TTL（默认 6h）；仅作展示参考，不单独决定 Fresh 档位
    @returns: freshness_class、freshness_label、age_display、freshness_note 等
    """
    from datetime import datetime, timezone

    parsed = _parse_mysql_utc_datetime(tested_at_raw)
    if not parsed:
        return {
            "freshness_class": "unknown",
            "freshness_label": "未测速",
            "validity_level": "未知",
            "age_hours": None,
            "age_display": "—",
            "freshness_note": "尚无 libtorrent 实测记录，以下速度不可作为 IG 背书。",
            "tested_at_iso": "",
            "ttl_hours": ttl_hours,
        }

    now = datetime.now(timezone.utc)
    age_sec = max(0.0, (now - parsed).total_seconds())
    age_hours = age_sec / 3600.0
    age_display = _format_age_display(age_hours)
    tested_at_iso = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")

    if age_hours <= FRESHNESS_FRESH_HOURS + FRESHNESS_BOUNDARY_GRACE_HOURS:
        freshness_class = "fresh"
        freshness_label = "新鲜"
        validity_level = "高"
        freshness_note = (
            f"距测速 {age_display}（≤{int(FRESHNESS_FRESH_HOURS)}h）；"
            f"数据可直接用于 Recommended 实测背书（S-07）。"
        )
    elif age_hours <= FRESHNESS_VALID_HOURS + FRESHNESS_BOUNDARY_GRACE_HOURS:
        freshness_class = "valid"
        freshness_label = "有效"
        validity_level = "中"
        freshness_note = (
            f"距测速 {age_display}（{int(FRESHNESS_FRESH_HOURS)}–{int(FRESHNESS_VALID_HOURS)}h）；"
            f"仍可参考，建议在 cron（{ttl_hours}h TTL）窗口外安排复测。"
        )
    elif age_hours <= FRESHNESS_STALE_HOURS + FRESHNESS_BOUNDARY_GRACE_HOURS:
        freshness_class = "stale"
        freshness_label = "陈旧"
        validity_level = "低"
        freshness_note = (
            f"距测速 {age_display}（{int(FRESHNESS_VALID_HOURS)}–{int(FRESHNESS_STALE_HOURS)}h）；"
            f"peer/速度可能已变化，IG 背书效力降低，应优先复测。"
        )
    else:
        freshness_class = "aged"
        freshness_label = "较久"
        validity_level = "待确认"
        freshness_note = (
            f"距测速 {age_display}（>{int(FRESHNESS_STALE_HOURS)}h）；"
            f"swarm 状态可能已有变化，建议复测后再作主要依据（非断言已失效）。"
        )

    return {
        "freshness_class": freshness_class,
        "freshness_label": freshness_label,
        "validity_level": validity_level,
        "age_hours": round(age_hours, 2),
        "age_display": age_display,
        "freshness_note": freshness_note,
        "tested_at_iso": tested_at_iso,
        "ttl_hours": ttl_hours,
    }


@dataclass
class SpeedEvidenceContext:
    """
    页面测速 IG 证据面板上下文（S-06 / S-07 / A-01~A-03 / A-09 / A-10）。

    @var summary: slot_speed_summary 聚合行
    @var phase1: 最近一次 Phase 1 明细（可选）
    @var phase2: 最近一次 Phase 2 明细（可选）
    @var indexed_seeders: Recommended 在索引侧的 seeders（A-10 对照）
    @var target_bytes_label: 片段测速大小说明
    """

    summary: SlotSpeedSummary
    phase1: Optional[SpeedTestResult] = None
    phase2: Optional[SpeedTestResult] = None
    indexed_seeders: int = 0
    target_bytes_label: str = "256 KB"

    @classmethod
    def from_parts(
        cls,
        summary: SlotSpeedSummary,
        phase1: Optional[SpeedTestResult] = None,
        phase2: Optional[SpeedTestResult] = None,
        *,
        indexed_seeders: int = 0,
        target_bytes_label: str = "256 KB",
    ) -> "SpeedEvidenceContext":
        """
        由摘要 + Phase 明细 + 索引 seeders 组装证据上下文。

        @param summary: 槽位测速摘要
        @param phase1: Phase 1 结果
        @param phase2: Phase 2 结果
        @param indexed_seeders: 索引 seeders
        @param target_bytes_label: 片段大小文案
        @returns: SpeedEvidenceContext 实例
        """
        return cls(
            summary=summary,
            phase1=phase1,
            phase2=phase2,
            indexed_seeders=indexed_seeders,
            target_bytes_label=target_bytes_label,
        )

    def build_endorsement_sentence(self, release_title: str = "") -> str:
        """
        生成 S-07 Recommended 实测背书句。

        @param release_title: Recommended release 标题
        @returns: 完整背书文案
        """
        from workflow.torrent_sources.speedtest.reachability import (
            format_reachability_display,
            format_speed_pair_display,
        )

        peers = (
            self.phase2.peers_total
            if self.phase2 and self.phase2.peers_total
            else (self.phase1.peers_total if self.phase1 else 0)
        )
        peers_reachable = (
            self.phase2.peers_reachable
            if self.phase2 and self.phase2.peers_reachable
            else (self.phase1.peers_reachable if self.phase1 else 0)
        )
        status = (self.phase2.status if self.phase2 else "") or (self.phase1.status if self.phase1 else "ok")
        speed_pair = format_speed_pair_display(
            self.phase2.avg_kbps if self.phase2 else 0.0,
            self.phase2.max_kbps if self.phase2 else 0.0,
        )
        reach = format_reachability_display(
            self.summary.reachability or "—",
            peers_total=peers,
            peers_reachable=peers_reachable,
            status=status,
        )
        title_part = f"「{release_title}」" if release_title else "本站 Recommended release"
        freshness = compute_test_freshness(
            (self.phase2.tested_at if self.phase2 else "")
            or (self.phase1.tested_at if self.phase1 else "")
            or self.summary.updated_at
        )
        time_part = ""
        if freshness.get("tested_at_iso"):
            tested_display = _format_datetime_utc_display(
                (self.phase2.tested_at if self.phase2 else "")
                or (self.phase1.tested_at if self.phase1 else "")
                or self.summary.updated_at
            )
            time_part = (
                f"测速于 {tested_display}（{freshness['age_display']}，"
                f"有效性 {freshness['validity_level']}·{freshness['freshness_label']}）。"
            )
        return (
            f"以下数据绑定 {title_part}（infohash …{self.summary.recommended_infohash[:8]}），"
            f"libtorrent 片段实测 {speed_pair['speed_pair_display']}，"
            f"Peer 可达性 {reach['reachability_display']}。"
            f"{time_part}"
        )

    def build_index_vs_measured_text(self) -> str:
        """
        生成 A-10 索引 seeders vs 实测 peers 对照句。

        @returns: 对照文案；缺数据时空串
        """
        peers = 0
        if self.phase2 and self.phase2.peers_total:
            peers = self.phase2.peers_total
        elif self.phase1 and self.phase1.peers_total:
            peers = self.phase1.peers_total
        if self.indexed_seeders <= 0 and peers <= 0:
            return ""
        if self.indexed_seeders <= 0:
            return f"索引 seeders 未记录；libtorrent 实测 {peers} peers（A-02）。"
        return (
            f"索引 seeders {self.indexed_seeders}（B-02 参考） vs "
            f"libtorrent 实测 {peers} peers（A-02）— 以实测为准。"
        )

    def to_template_dict(self) -> Dict[str, Any]:
        """
        转为 episode.html 测速证据面板变量。

        @returns: Jinja2 渲染字典
        """
        p2 = self.phase2
        p1 = self.phase1
        avg_kbps = p2.avg_kbps if p2 else 0.0
        max_kbps = p2.max_kbps if p2 else 0.0
        peers_total = (p2.peers_total if p2 else 0) or (p1.peers_total if p1 else 0)
        peers_reachable = (p2.peers_reachable if p2 else 0) or (p1.peers_reachable if p1 else 0)
        latency_ms = p2.latency_ms if p2 else 0
        tested_at_raw = (p2.tested_at if p2 else "") or (p1.tested_at if p1 else "") or self.summary.updated_at
        tested_at = _format_datetime_utc_display(tested_at_raw)
        reachability = self.summary.reachability or "—"

        from workflow.config import TORRENT_SEEDERS_TTL_HOURS

        freshness = compute_test_freshness(
            tested_at_raw,
            ttl_hours=TORRENT_SEEDERS_TTL_HOURS,
        )

        ig_badges = ["S-06", "S-07", "A-01", "A-02", "A-03"]
        if latency_ms > 0:
            ig_badges.append("A-09")
        if self.indexed_seeders > 0 and peers_total > 0:
            ig_badges.append("A-10")

        from workflow.torrent_sources.speedtest.reachability import (
            format_peers_summary_display,
            format_reachability_display,
            format_speed_pair_display,
        )

        status = (p2.status if p2 else "") or (p1.status if p1 else "ok")
        speed_pair = format_speed_pair_display(avg_kbps, max_kbps)
        peers_summary = format_peers_summary_display(peers_total, peers_reachable)
        reach = format_reachability_display(
            reachability,
            peers_total=peers_total,
            peers_reachable=peers_reachable,
            status=status,
        )

        from workflow.torrent_sources.speedtest.grab_index import compute_grab_index

        grab = compute_grab_index(
            avg_kbps=avg_kbps,
            max_kbps=max_kbps,
            reachability=reachability if reachability not in ("—", "") else "",
            peers_total=peers_total,
            peers_reachable=peers_reachable,
            status=status,
            freshness_class=freshness.get("freshness_class", "unknown"),
            validity_level=freshness.get("validity_level", ""),
        )

        return {
            "recommended_speed": self.summary.recommended_speed or speed_pair["avg_speed"],
            "avg_speed": speed_pair["avg_speed"],
            "max_speed": speed_pair["max_speed"],
            "speed_pair_display": speed_pair["speed_pair_display"],
            "speed_spread_display": speed_pair["speed_spread_display"],
            "avg_kbps": round(avg_kbps, 2) if avg_kbps else 0,
            "max_kbps": round(max_kbps, 2) if max_kbps else 0,
            "reachability": reachability,
            "reachability_display": reach["reachability_display"],
            "reachability_detail": reach["reachability_detail"],
            "reachability_rule": reach["reachability_rule"],
            "connect_rate_display": peers_summary["connect_rate_display"],
            "connect_rate_pct": peers_summary["connect_rate_pct"],
            "peers_pair_display": peers_summary["peers_pair_display"],
            "peers_total_display": peers_summary["peers_total_display"],
            "peers_reachable_display": peers_summary["peers_reachable_display"],
            "reachability_class": _reachability_css_class(reachability),
            "peers_total": peers_total,
            "peers_reachable": peers_reachable,
            "latency_ms": latency_ms,
            "latency_display": _format_latency_display(latency_ms),
            "updated_at": _format_datetime_utc_display(self.summary.updated_at),
            "tested_at": tested_at,
            "tested_at_raw": tested_at_raw,
            "tested_at_iso": freshness.get("tested_at_iso", ""),
            "freshness_class": freshness.get("freshness_class", "unknown"),
            "freshness_label": freshness.get("freshness_label", "未知"),
            "validity_level": freshness.get("validity_level", "未知"),
            "age_hours": freshness.get("age_hours"),
            "age_display": freshness.get("age_display", "—"),
            "freshness_note": freshness.get("freshness_note", ""),
            "ttl_hours": freshness.get("ttl_hours", 6),
            "infohash_short": (
                self.summary.recommended_infohash[:8]
                if self.summary.recommended_infohash
                else ""
            ),
            "indexed_seeders": self.indexed_seeders,
            "index_vs_measured": self.build_index_vs_measured_text(),
            "method_note": f"libtorrent 片段下载（{self.target_bytes_label}，策略 A2）",
            "target_bytes_label": self.target_bytes_label,
            "ig_badges": ig_badges,
            "status": (p2.status if p2 else "") or (p1.status if p1 else "ok"),
            **grab,
        }


def _merge_measured_into_recommend_reason(
    rec_dict: Dict[str, Any],
    speed_evidence: "SpeedEvidenceContext",
    speed_ctx: Dict[str, Any],
    endorsement: str,
) -> None:
    """
    E-05 / S-02：将 libtorrent 实测事实并入 ``recommend_reason``（渲染期，不写回 MySQL）。

    优先使用 A-10 ``index_vs_measured``；若无则回退 ``speed_endorsement`` 核心（均速 + peers + UTC）。

    @param rec_dict: Recommended 模板字典（就地修改）
    @param speed_evidence: 测速 IG 证据上下文
    @param speed_ctx: ``speed_evidence.to_template_dict()`` 结果
    @param endorsement: ``build_endorsement_sentence`` 完整背书句
    @returns: None
    """
    base = str(rec_dict.get("recommend_reason") or "").strip()
    measured = str(
        speed_ctx.get("index_vs_measured") or speed_evidence.build_index_vs_measured_text()
    ).strip()
    if not measured and endorsement:
        tested = str(speed_ctx.get("tested_at") or "").strip()
        avg = str(speed_ctx.get("avg_speed") or "").strip()
        peers = str(
            speed_ctx.get("peers_pair_display")
            or speed_ctx.get("peers_total_display")
            or ""
        ).strip()
        parts: List[str] = []
        if avg:
            parts.append(f"libtorrent 实测均速 {avg}")
        if peers:
            parts.append(f"Peer {peers}")
        if tested:
            parts.append(f"测于 {tested} UTC")
        measured = "，".join(parts)
    if not measured or measured in base:
        return
    rec_dict["recommend_reason"] = f"{base}；{measured}" if base else measured


def _enrich_recommended_with_speed(
    rec_dict: Dict[str, Any],
    speed_evidence: Optional[SpeedEvidenceContext],
    speed_summary: Optional[SlotSpeedSummary],
    release_title: str,
) -> None:
    """
    就地写入 Recommended 模板的测速、Grab 指数、S-07 背书与 E-05 reason 合并字段。

    @param rec_dict: recommended.to_template_dict() 结果（会被修改）
    @param speed_evidence: 测速 IG 证据上下文
    @param speed_summary: 测速摘要（无明细时的回退）
    @param release_title: release 标题，用于背书句
    """
    if speed_evidence:
        speed_ctx = speed_evidence.to_template_dict()
        rec_dict["speed"] = speed_evidence.summary.recommended_speed or speed_ctx["avg_speed"]
        rec_dict["speed_max"] = speed_ctx["max_speed"]
        rec_dict["speed_test"] = {
            "tested_at": speed_ctx["tested_at"],
            "tested_at_iso": speed_ctx["tested_at_iso"],
            "age_display": speed_ctx["age_display"],
            "freshness_label": speed_ctx["freshness_label"],
            "freshness_class": speed_ctx["freshness_class"],
            "validity_level": speed_ctx["validity_level"],
            "avg_speed": speed_ctx["avg_speed"],
            "max_speed": speed_ctx["max_speed"],
            "avg_kbps": speed_ctx["avg_kbps"],
            "max_kbps": speed_ctx["max_kbps"],
            "peers_total": speed_ctx["peers_total"],
            "peers_reachable": speed_ctx["peers_reachable"],
            "peers_total_display": speed_ctx["peers_total_display"],
            "peers_reachable_display": speed_ctx["peers_reachable_display"],
            "connect_rate_pct": speed_ctx["connect_rate_pct"],
            "connect_rate_display": speed_ctx["connect_rate_display"],
            "peers_pair_display": speed_ctx["peers_pair_display"],
            "reachability": speed_ctx["reachability"],
        }
        rec_dict["grab_index"] = {
            "grab_index_name": speed_ctx["grab_index_name"],
            "grab_index_tagline": speed_ctx["grab_index_tagline"],
            "grab_index_score": speed_ctx["grab_index_score"],
            "grab_index_display": speed_ctx["grab_index_display"],
            "grab_index_tier": speed_ctx["grab_index_tier"],
            "grab_index_tier_label": speed_ctx["grab_index_tier_label"],
            "grab_index_tier_class": speed_ctx["grab_index_tier_class"],
            "grab_index_summary": speed_ctx["grab_index_summary"],
            "grab_index_breakdown": speed_ctx["grab_index_breakdown"],
            "grab_index_has_data": speed_ctx["grab_index_has_data"],
        }
        endorsement = speed_evidence.build_endorsement_sentence(release_title)
        rec_dict["speed_endorsement"] = endorsement
        _merge_measured_into_recommend_reason(
            rec_dict, speed_evidence, speed_ctx, endorsement
        )
    elif speed_summary and speed_summary.recommended_speed:
        rec_dict["speed"] = speed_summary.recommended_speed


def build_tv_episode_schema_ld(
    *,
    episode_title: str,
    show_title: str,
    season: int,
    episode: int,
    canonical_url: str,
    show_hub_url: str,
    air_date: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """
    构造单集页 schema.org TVEpisode JSON-LD 字典（T-SEO-04 / D-T1）。

    @param episode_title: TMDB 单集标题；空则回退 SxxExx
    @param show_title: 剧集名（TVSeries.name）
    @param season: 季号
    @param episode: 集号（TVEpisode.position）
    @param canonical_url: 本页 canonical 绝对 URL
    @param show_hub_url: 剧集 Hub 页 URL（partOfSeries.url）
    @param air_date: 播出日 YYYY-MM-DD（可选，写入 datePublished）
    @param description: 单集简介（可选）
    @returns: 可直接 Jinja ``|tojson`` 的字典
    """
    name = episode_title.strip() if episode_title.strip() else f"S{season:02d}E{episode:02d}"
    schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "TVEpisode",
        "name": name,
        "position": episode,
        "season": season,
        "partOfSeries": {
            "@type": "TVSeries",
            "name": show_title,
            "url": show_hub_url,
        },
        "url": canonical_url,
    }
    if air_date:
        schema["datePublished"] = air_date
    if description:
        schema["description"] = description
    return schema


def build_movie_schema_ld(
    *,
    movie_title: str,
    year: str,
    canonical_url: str,
    description: str = "",
) -> Dict[str, Any]:
    """
    构造电影页 schema.org Movie JSON-LD 字典（T-SEO-04）。

    @param movie_title: 电影名
    @param year: 上映年份
    @param canonical_url: 本页 canonical 绝对 URL
    @param description: 简介（可选）
    @returns: 可直接 Jinja ``|tojson`` 的字典
    """
    schema: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": movie_title,
        "url": canonical_url,
    }
    if year:
        schema["datePublished"] = year
    if description:
        schema["description"] = description
    return schema


def build_breadcrumb_list_schema_ld(
    items: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    构造 BreadcrumbList JSON-LD（T-SEO-08 / P2 技术 SEO）。

    @param items: 有序列表，每项含 name；末项可不含 item（当前页）
    @returns: schema.org BreadcrumbList 字典
    """
    elements: List[Dict[str, Any]] = []
    for index, entry in enumerate(items, start=1):
        node: Dict[str, Any] = {
            "@type": "ListItem",
            "position": index,
            "name": entry.get("name") or "",
        }
        url = (entry.get("url") or "").strip()
        if url:
            node["item"] = url
        elements.append(node)
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def is_speed_evidence_publishable(
    summary: Optional["SlotSpeedSummary"],
    phase1: Optional["SpeedTestResult"] = None,
    phase2: Optional["SpeedTestResult"] = None,
) -> bool:
    """
    A-07：timeout/error 且无 peers 时不向页面输出测速 IG 面板。

    @param summary: slot_speed_summary 行
    @param phase1: Phase 1 测速明细
    @param phase2: Phase 2 测速明细
    @returns: True 表示可 bake speed_evidence
    """
    if not summary or not (summary.recommended_infohash or "").strip():
        return False
    status = (phase2.status if phase2 else "") or (phase1.status if phase1 else "ok")
    peers = (phase2.peers_total if phase2 else 0) or (phase1.peers_total if phase1 else 0)
    if status in ("timeout", "error") and peers <= 0:
        return False
    return True


@dataclass
class EpisodePageContext:
    """
    单集页 Jinja2 完整上下文 — 聚合 D1 多表查询结果。

    @var catalog: 作品主数据
    @var page: 页面槽位
    @var sources: All Sources 列表（含 recommended）
    @var recommended: Recommended release（sources 中 is_recommended=1）
    @var speed_summary: 测速摘要条（可选，兼容旧模板）
    @var speed_evidence: 测速 IG 证据面板（S-06 / S-07 / A 级字段）
    @var torrent_metadata: swarm torrent 结构面板（测速 metadata 提取）
    @var canonical_url: 完整 canonical URL
    """

    catalog: MediaCatalog
    page: MediaPage
    sources: List[DownloadResource]
    recommended: Optional[DownloadResource] = None
    speed_summary: Optional[SlotSpeedSummary] = None
    speed_evidence: Optional[SpeedEvidenceContext] = None
    torrent_metadata: Optional[TorrentMetadataContext] = None
    canonical_url: str = ""

    def to_template_context(self, site_origin: str = "https://releasematch.com") -> Dict[str, Any]:
        """
        组装 episode.html 渲染上下文。

        @param site_origin: 站点 origin，用于 canonical 与 prev/next 绝对 URL
        @returns: Jinja2 render 参数字典
        """
        slug = self.catalog.slug
        recommended = self.recommended
        rec_dict = None
        if recommended:
            from workflow.torrent_sources.release_parser import enrich_item_dict

            rec_dict = recommended.to_template_dict()
            enrich_item_dict(rec_dict, force_specs=True)
            _enrich_recommended_with_speed(
                rec_dict,
                self.speed_evidence,
                self.speed_summary,
                recommended.title_raw,
            )

        prev_path = self.page.prev_episode_path(slug)
        next_path = self.page.next_episode_path(slug)

        def _nav_url(path: Optional[str]) -> Optional[str]:
            """站内导航 URL：本地预览用相对路径，生产可传 site_origin。"""
            if not path:
                return None
            if site_origin and site_origin not in ("", "/"):
                return f"{site_origin.rstrip('/')}{path}"
            return path

        origin = site_origin.rstrip("/") if site_origin else ""
        canonical = self.canonical_url or (
            f"{origin}{self.page.canonical_path}" if origin else self.page.canonical_path
        )
        hub_path = f"/{slug}/"
        show_hub_url = f"{origin}{hub_path}" if origin else hub_path
        season_num = self.page.season or 0
        episode_num = self.page.episode or 0
        overview_en = self.page.overview or self.catalog.overview or ""
        overview_zh = self.page.overview_zh or self.catalog.overview_zh or ""
        overview = overview_en

        from workflow.torrent_sources.release_parser import enrich_item_dict

        source_dicts = [
            enrich_item_dict(src.to_template_dict(), force_specs=True) for src in self.sources
        ]

        return {
            "show_title": self.catalog.title,
            "show_slug": slug,
            "tmdb_id": self.catalog.tmdb_id,
            "media_kind": self.catalog.media_kind,
            "season": self.page.season,
            "episode": self.page.episode,
            "episode_title": self.page.episode_title,
            "air_date": self.page.air_date,
            "episode_overview": overview_en,
            "overview_en": overview_en,
            "overview_zh": overview_zh,
            "cross_source_count": self.page.cross_source_count,
            "cross_source_total": self.page.cross_source_total,
            "speed_summary": self.speed_summary.to_template_dict() if self.speed_summary else None,
            "speed_evidence": self.speed_evidence.to_template_dict() if self.speed_evidence else None,
            "torrent_metadata": self.torrent_metadata.to_template_dict()
            if self.torrent_metadata
            else None,
            "recommended": rec_dict,
            "recommended_quality": (rec_dict or {}).get("resolution") or "",
            "recommended_source": (rec_dict or {}).get("source") or "",
            "recommended_group": (rec_dict or {}).get("release_group") or "",
            "sources": source_dicts,
            "source_count": len(source_dicts),
            "prev_episode_url": _nav_url(prev_path),
            "prev_episode_label": (
                f"S{self.page.prev_season:02d}E{self.page.prev_episode:02d}"
                if prev_path
                else None
            ),
            "next_episode_url": _nav_url(next_path),
            "next_episode_label": (
                f"S{self.page.next_season:02d}E{self.page.next_episode:02d}"
                if next_path
                else None
            ),
            "poster_url": self.catalog.poster_url(),
            "tmdb_overview": overview_en,
            "tmdb_url": (
                f"https://www.themoviedb.org/tv/{self.catalog.tmdb_id}"
                f"/season/{self.page.season}/episode/{self.page.episode}"
                if self.page.season and self.page.episode
                else self.catalog.tmdb_url
            ),
            "streaming_providers": self.catalog.streaming_providers,
            "subtitle_url": self.page.subtitle_url,
            "canonical_url": canonical,
            "show_hub_url": show_hub_url,
            "schema_ld": build_tv_episode_schema_ld(
                episode_title=self.page.episode_title,
                show_title=self.catalog.title,
                season=season_num,
                episode=episode_num,
                canonical_url=canonical,
                show_hub_url=show_hub_url,
                air_date=self.page.air_date,
                description=overview,
            ),
            "breadcrumb_ld": build_breadcrumb_list_schema_ld(
                [
                    {
                        "name": _ui_text("nav.home"),
                        "url": f"{origin}/" if origin else "/",
                    },
                    {"name": self.catalog.title, "url": show_hub_url},
                    {
                        "name": f"S{season_num:02d}E{episode_num:02d}",
                    },
                ]
            ),
            "robots_noindex": not self.page.is_indexable(
                has_recommended=self.recommended is not None
            ),
            # 最终 SEO desc 由 i18n.attach_seo_meta_description 在渲染时写入 seo_meta_description
        }


@dataclass
class MoviePageContext:
    """
    电影页 Jinja2 完整上下文。

    @var catalog: 作品主数据
    @var page: 页面槽位
    @var sources: All Versions 列表
    @var recommended: Recommended release
    @var speed_summary: 测速摘要条（可选）
    @var speed_evidence: 测速 IG 证据面板（S-06 / S-07 / A 级字段）
    @var torrent_metadata: swarm torrent 结构面板
    @var canonical_url: canonical URL
    """

    catalog: MediaCatalog
    page: MediaPage
    sources: List[DownloadResource]
    recommended: Optional[DownloadResource] = None
    speed_summary: Optional[SlotSpeedSummary] = None
    speed_evidence: Optional[SpeedEvidenceContext] = None
    torrent_metadata: Optional[TorrentMetadataContext] = None
    canonical_url: str = ""

    def to_template_context(self, site_origin: str = "https://releasematch.com") -> Dict[str, Any]:
        """
        组装 movie.html 渲染上下文。

        @param site_origin: 站点 origin
        @returns: Jinja2 参数字典
        """
        from workflow.torrent_sources.release_parser import enrich_item_dict

        recommended = self.recommended
        rec_dict = None
        if recommended:
            rec_dict = recommended.to_template_dict()
            enrich_item_dict(rec_dict, force_specs=True)
            _enrich_recommended_with_speed(
                rec_dict,
                self.speed_evidence,
                self.speed_summary,
                recommended.title_raw,
            )
        from workflow.movie_editions import annotate_source_dict, group_movie_sources

        source_dicts = []
        for src in self.sources:
            row = annotate_source_dict(
                enrich_item_dict(src.to_template_dict(), force_specs=True)
            )
            source_dicts.append(row)
        source_editions = group_movie_sources(source_dicts)
        edition_pick_hashes = {
            str(g["best"].get("infohash"))
            for g in source_editions
            if g.get("best") and g["best"].get("infohash")
        }
        for row in source_dicts:
            row["is_edition_pick"] = str(row.get("infohash") or "") in edition_pick_hashes
        runtime = (
            f"{self.catalog.runtime_minutes} min"
            if self.catalog.runtime_minutes
            else ""
        )
        origin = site_origin.rstrip("/") if site_origin else ""
        canonical = self.canonical_url or (
            f"{origin}{self.page.canonical_path}" if origin else self.page.canonical_path
        )
        overview_en = self.page.overview or self.catalog.overview or ""
        overview_zh = self.page.overview_zh or self.catalog.overview_zh or ""
        overview = overview_en
        year = self.catalog.year or ""
        return {
            "movie_title": self.catalog.title,
            "tmdb_id": self.catalog.tmdb_id,
            "media_kind": self.catalog.media_kind,
            "year": year,
            "runtime": runtime,
            "movie_overview": overview_en,
            "overview_en": overview_en,
            "overview_zh": overview_zh,
            "cross_source_count": self.page.cross_source_count,
            "cross_source_total": self.page.cross_source_total,
            "speed_summary": self.speed_summary.to_template_dict() if self.speed_summary else None,
            "speed_evidence": self.speed_evidence.to_template_dict() if self.speed_evidence else None,
            "torrent_metadata": self.torrent_metadata.to_template_dict()
            if self.torrent_metadata
            else None,
            "recommended": rec_dict,
            "recommended_quality": (rec_dict or {}).get("resolution") or "",
            "recommended_source": (rec_dict or {}).get("source") or "",
            "recommended_group": (rec_dict or {}).get("release_group") or "",
            "sources": source_dicts,
            "source_editions": source_editions,
            "source_count": len(source_dicts),
            "poster_url": self.catalog.poster_url(),
            "tmdb_overview": overview_en,
            "tmdb_url": self.catalog.tmdb_url,
            "canonical_url": canonical,
            "schema_ld": build_movie_schema_ld(
                movie_title=self.catalog.title,
                year=year,
                canonical_url=canonical,
                description=overview,
            ),
            "breadcrumb_ld": build_breadcrumb_list_schema_ld(
                [
                    {
                        "name": _ui_text("nav.home"),
                        "url": f"{origin}/" if origin else "/",
                    },
                    {"name": f"{self.catalog.title} ({year})" if year else self.catalog.title},
                ]
            ),
            "robots_noindex": not self.page.is_indexable(
                has_recommended=self.recommended is not None
            ),
        }


@dataclass
class ShowHubPageContext:
    """
    剧集 Hub 页 Jinja2 上下文。

    @var catalog: 作品主数据
    @var page: Hub 槽位
    @var seasons: 季/集芯片结构
    @var active_season: 高亮季号（可选）
    @var active_episode: 高亮集号（可选）
    """

    catalog: MediaCatalog
    page: MediaPage
    seasons: List[Dict[str, Any]]
    active_season: Optional[int] = None
    active_episode: Optional[int] = None
    canonical_url: str = ""

    def to_template_context(self, site_origin: str = "https://releasematch.com") -> Dict[str, Any]:
        """
        组装 show_hub.html 渲染上下文。

        @param site_origin: 站点 origin
        @returns: Jinja2 参数字典
        """
        seasons_out: List[Dict[str, Any]] = []
        for season in self.seasons:
            eps_out = []
            for ep in season.get("episodes", []):
                is_active = (
                    self.active_season == season["number"]
                    and self.active_episode == ep["number"]
                )
                eps_out.append({"number": ep["number"], "is_active": is_active})
            seasons_out.append({"number": season["number"], "episodes": eps_out})

        origin = site_origin.rstrip("/") if site_origin else ""
        canonical = self.canonical_url or (
            f"{origin}{self.page.canonical_path}" if origin else self.page.canonical_path
        )
        overview_en = self.page.overview or self.catalog.overview or ""
        overview_zh = self.page.overview_zh or self.catalog.overview_zh or ""
        return {
            "show_title": self.catalog.title,
            "show_slug": self.catalog.slug,
            "tmdb_id": self.catalog.tmdb_id,
            "media_kind": self.catalog.media_kind,
            "show_overview": overview_en,
            "overview_en": overview_en,
            "overview_zh": overview_zh,
            "seasons": seasons_out,
            "poster_url": self.catalog.poster_url(),
            "tmdb_url": self.catalog.tmdb_url,
            "canonical_url": canonical,
            "robots_noindex": True,
            "meta_description": _ui_text(
                "hub.meta_description",
                show=self.catalog.title,
            ),
        }


def _ui_text(key: str, **kwargs: Any) -> str:
    """
    按站点 locale 解析 UI 文案（供 to_template_context 内 meta / breadcrumb 使用）。

    @param key: portal.generator.i18n.MESSAGES 键
    @param kwargs: format 占位符
    @returns: 翻译字符串
    """
    from portal.generator.i18n import build_i18n_runtime, translate

    runtime = build_i18n_runtime()
    return translate(key, runtime.locale, **kwargs)
