#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMDB external_ids 解析（独立版，解耦 W004）。

@module workflow.metadata.external_ids
@description
  原规划依赖 tmdbpy/workflow/W004_metadata_crawler.py 写入 tv_detail.imdb_id/tvdb_id。
  Release 导航站通过本模块：
    - standalone 模式：使用内置 Demo 映射 + 可选 CLI 传入
    - mysql 模式：只读查询 TMDB MySQL（不修改字幕表）

  R0 阶段可先使用 standalone；R1 可对接共享 MySQL。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from workflow.config import MYSQL_DB, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER, TMDB_DATA_MODE

# Demo 冷启动静态映射（Breaking Bad + 示例电影）
_STANDALONE_MAP: Dict[int, Dict[str, Any]] = {
    1396: {
        "tmdb_id": 1396,
        "media_type": "tv",
        "title": "Breaking Bad",
        "imdb_id": "tt0903747",
        "tvdb_id": 81189,
        "original_language": "en",
    },
    603: {
        "tmdb_id": 603,
        "media_type": "movie",
        "title": "The Matrix",
        "imdb_id": "tt0133093",
        "tvdb_id": None,
    },
    155: {
        "tmdb_id": 155,
        "media_type": "movie",
        "title": "The Dark Knight",
        "imdb_id": "tt0468569",
        "tvdb_id": None,
    },
    157336: {
        "tmdb_id": 157336,
        "media_type": "movie",
        "title": "Interstellar",
        "imdb_id": "tt0816692",
        "tvdb_id": None,
    },
    550: {
        "tmdb_id": 550,
        "media_type": "movie",
        "title": "Fight Club",
        "imdb_id": "tt0137523",
        "tvdb_id": None,
    },
    680: {
        "tmdb_id": 680,
        "media_type": "movie",
        "title": "Pulp Fiction",
        "imdb_id": "tt0110912",
        "tvdb_id": None,
    },
    122: {
        "tmdb_id": 122,
        "media_type": "movie",
        "title": "The Lord of the Rings: The Return of the King",
        "imdb_id": "tt0167260",
        "tvdb_id": None,
    },
    120: {
        "tmdb_id": 120,
        "media_type": "movie",
        "title": "The Lord of the Rings: The Fellowship of the Ring",
        "imdb_id": "tt0120737",
        "tvdb_id": None,
    },
    1399: {
        "tmdb_id": 1399,
        "media_type": "tv",
        "title": "Game of Thrones",
        "imdb_id": "tt0944947",
        "tvdb_id": 121361,
    },
    66732: {
        "tmdb_id": 66732,
        "media_type": "tv",
        "title": "Stranger Things",
        "imdb_id": "tt4574334",
        "tvdb_id": 305288,
    },
    82856: {
        "tmdb_id": 82856,
        "media_type": "tv",
        "title": "The Mandalorian",
        "imdb_id": "tt8111088",
        "tvdb_id": 361753,
    },
    94997: {
        "tmdb_id": 94997,
        "media_type": "tv",
        "title": "House of the Dragon",
        "imdb_id": "tt11198330",
        "tvdb_id": 371572,
    },
    4604: {
        "tmdb_id": 4604,
        "media_type": "tv",
        "title": "Smallville",
        "imdb_id": "tt0279600",
        "tvdb_id": 72248,
    },
    1408: {
        "tmdb_id": 1408,
        "media_type": "tv",
        "title": "House",
        "imdb_id": "tt0412142",
        "tvdb_id": 73255,
    },
    27205: {
        "tmdb_id": 27205,
        "media_type": "movie",
        "title": "Inception",
        "imdb_id": "tt1375666",
        "tvdb_id": None,
        "original_language": "en",
    },
    93405: {
        "tmdb_id": 93405,
        "media_type": "tv",
        "title": "Squid Game",
        "title_ko": "오징어 게임",
        "imdb_id": "tt10919420",
        "tvdb_id": 383275,
        "original_language": "ko",
    },
    94796: {
        "tmdb_id": 94796,
        "media_type": "tv",
        "title": "Crash Landing on You",
        "title_ko": "사랑의 불시착",
        "imdb_id": "tt10525632",
        "tvdb_id": 371806,
        "original_language": "ko",
    },
    110316: {
        "tmdb_id": 110316,
        "media_type": "tv",
        "title": "Alice in Borderland",
        "title_ja": "今際の国のアリス",
        "imdb_id": "tt10755656",
        "tvdb_id": 376459,
        "original_language": "ja",
    },
    # ── 华语剧 / 电影（cn 路由 · 中文标题搜索）────────────────────────────
    95842: {
        "tmdb_id": 95842,
        "media_type": "tv",
        "title": "Joy of Life",
        "title_zh": "庆余年",
        "original_title": "庆余年",
        "original_language": "zh",
        "origin_country": ["CN"],
        "imdb_id": "tt11273352",
        "tvdb_id": 372881,
    },
    97113: {
        "tmdb_id": 97113,
        "media_type": "tv",
        "title": "The Three-Body Problem",
        "title_zh": "三体",
        "original_title": "三体",
        "original_language": "zh",
        "origin_country": ["CN"],
        "imdb_id": "tt24244206",
        "tvdb_id": 426655,
    },
    64197: {
        "tmdb_id": 64197,
        "media_type": "tv",
        "title": "Nirvana in Fire",
        "title_zh": "琅琊榜",
        "original_title": "琅琊榜",
        "original_language": "zh",
        "origin_country": ["CN"],
        "imdb_id": "tt5141800",
        "tvdb_id": 301369,
    },
    90761: {
        "tmdb_id": 90761,
        "media_type": "tv",
        "title": "The Untamed",
        "title_zh": "陈情令",
        "original_title": "陈情令",
        "original_language": "zh",
        "origin_country": ["CN"],
        "imdb_id": "tt10554898",
        "tvdb_id": 355148,
    },
    535167: {
        "tmdb_id": 535167,
        "media_type": "movie",
        "title": "The Wandering Earth",
        "title_zh": "流浪地球",
        "original_title": "流浪地球",
        "original_language": "zh",
        "origin_country": ["CN"],
        "imdb_id": "tt7605074",
        "tvdb_id": None,
        "year": 2019,
    },
}


def resolve_external_ids(
    tmdb_id: int,
    media_type: str = "tv",
    imdb_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    解析作品的 IMDb / TVDB 外部 ID。

    @param tmdb_id: TMDB 作品 ID
    @param media_type: movie 或 tv
    @param imdb_id: 可选，调用方已知的 IMDb ID（优先使用）
    @param title: 可选，slot 导出标题（standalone 缺失时供搜索）
    @returns: 含 tmdb_id、imdb_id、tvdb_id、source 的字典
    """
    if imdb_id:
        row = {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "imdb_id": imdb_id,
            "tvdb_id": _lookup_tvdb_standalone(tmdb_id),
            "source": "caller",
        }
        if title:
            row["title"] = title
        return row

    if TMDB_DATA_MODE == "mysql" and MYSQL_USER:
        row = _fetch_from_mysql(tmdb_id, media_type)
        if row:
            if title and not row.get("title"):
                row["title"] = title
            return row

    row = _fetch_standalone(tmdb_id, media_type)
    if title and not row.get("title"):
        row["title"] = title
        if row.get("source") == "standalone_missing":
            row["source"] = "slot_title"
    return row


def _lookup_tvdb_standalone(tmdb_id: int) -> Optional[int]:
    """从 Demo 映射查 tvdb_id。"""
    entry = _STANDALONE_MAP.get(tmdb_id)
    if entry:
        tvdb = entry.get("tvdb_id")
        return int(tvdb) if tvdb is not None else None
    return None


def _fetch_standalone(tmdb_id: int, media_type: str) -> Dict[str, Any]:
    """
    standalone 模式：Demo 映射或空 ID。

    @param tmdb_id: TMDB ID
    @param media_type: 媒体类型
    @returns: external_ids 字典
    """
    entry = _STANDALONE_MAP.get(tmdb_id)
    if entry:
        return {
            "tmdb_id": tmdb_id,
            "media_type": entry.get("media_type", media_type),
            "title": entry.get("title"),
            "title_ja": entry.get("title_ja"),
            "title_ko": entry.get("title_ko"),
            "title_zh": entry.get("title_zh"),
            "original_title": entry.get("original_title"),
            "original_language": entry.get("original_language"),
            "origin_country": entry.get("origin_country"),
            "imdb_id": entry.get("imdb_id"),
            "tvdb_id": entry.get("tvdb_id"),
            "source": "standalone_map",
        }
    return {
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "title": None,
        "imdb_id": None,
        "tvdb_id": None,
        "source": "standalone_missing",
        "hint": "添加映射到 external_ids._STANDALONE_MAP 或启用 RM_TMDB_DATA_MODE=mysql",
    }


def _fetch_from_mysql(tmdb_id: int, media_type: str) -> Optional[Dict[str, Any]]:
    """
    只读 MySQL 查询 external_ids（R1 实现完整 SQL）。

    @param tmdb_id: TMDB ID
    @param media_type: 媒体类型
    @returns: 命中时返回字典，否则 None
    """
    try:
        import pymysql  # noqa: WPS433 — 可选依赖
    except ImportError:
        return None

    table = "movie_detail" if media_type == "movie" else "tv_detail"
    sql = f"SELECT imdb_id, tvdb_id FROM {table} WHERE tmdb_id = %s LIMIT 1"

    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn.cursor() as cur:
            cur.execute(sql, (tmdb_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "imdb_id": row.get("imdb_id"),
            "tvdb_id": row.get("tvdb_id"),
            "source": "mysql",
        }
    except Exception:
        return None
