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
}


def resolve_external_ids(
    tmdb_id: int,
    media_type: str = "tv",
    imdb_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    解析作品的 IMDb / TVDB 外部 ID。

    @param tmdb_id: TMDB 作品 ID
    @param media_type: movie 或 tv
    @param imdb_id: 可选，调用方已知的 IMDb ID（优先使用）
    @returns: 含 tmdb_id、imdb_id、tvdb_id、source 的字典
    """
    if imdb_id:
        return {
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "imdb_id": imdb_id,
            "tvdb_id": _lookup_tvdb_standalone(tmdb_id),
            "source": "caller",
        }

    if TMDB_DATA_MODE == "mysql" and MYSQL_USER:
        row = _fetch_from_mysql(tmdb_id, media_type)
        if row:
            return row

    return _fetch_standalone(tmdb_id, media_type)


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
            "original_language": entry.get("original_language"),
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
