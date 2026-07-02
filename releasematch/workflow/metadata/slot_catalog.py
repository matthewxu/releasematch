# -*- coding: utf-8 -*-
"""
测试 slot 作品元数据 — catalog slug / 年份 / canonical 路径。

@module workflow.metadata.slot_catalog
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


def slugify_title(title: str, *, year: Optional[int] = None, max_len: int = 80) -> str:
    """
    将作品标题转为 URL slug。

    @param title: 原始标题
    @param year: 可选年份后缀
    @param max_len: 最大长度
    @returns: 如 the-matrix-1999
    """
    cleaned = re.sub(r"[^\w\s-]", "", (title or "").lower())
    slug = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    if year:
        slug = f"{slug}-{year}" if slug else str(year)
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "untitled"

# TMDB ID → 扩槽写库元数据
SLOT_CATALOG_META: Dict[int, Dict[str, Any]] = {
    603: {"title": "The Matrix", "media_kind": "movie", "year": 1999, "slug": "the-matrix-1999"},
    155: {"title": "The Dark Knight", "media_kind": "movie", "year": 2008, "slug": "the-dark-knight-2008"},
    157336: {"title": "Interstellar", "media_kind": "movie", "year": 2014, "slug": "interstellar-2014"},
    550: {"title": "Fight Club", "media_kind": "movie", "year": 1999, "slug": "fight-club-1999"},
    680: {"title": "Pulp Fiction", "media_kind": "movie", "year": 1994, "slug": "pulp-fiction-1994"},
    122: {
        "title": "The Lord of the Rings: The Return of the King",
        "media_kind": "movie",
        "year": 2003,
        "slug": "lord-of-the-rings-return-of-the-king-2003",
    },
    120: {
        "title": "The Lord of the Rings: The Fellowship of the Ring",
        "media_kind": "movie",
        "year": 2001,
        "slug": "lord-of-the-rings-fellowship-2001",
    },
    1399: {"title": "Game of Thrones", "media_kind": "tv", "slug": "game-of-thrones"},
    66732: {"title": "Stranger Things", "media_kind": "tv", "slug": "stranger-things"},
    82856: {"title": "The Mandalorian", "media_kind": "tv", "slug": "the-mandalorian"},
    94997: {"title": "House of the Dragon", "media_kind": "tv", "slug": "house-of-the-dragon"},
    4604: {"title": "Smallville", "media_kind": "tv", "slug": "smallville"},
    1408: {"title": "House", "media_kind": "tv", "slug": "house"},
}


def get_slot_catalog_meta(tmdb_id: int) -> Optional[Dict[str, Any]]:
    """查询 slot 扩槽 catalog 元数据。"""
    return SLOT_CATALOG_META.get(tmdb_id)


def canonical_path_for_slot(
    meta: Dict[str, Any],
    *,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> str:
    """生成 canonical 路径。"""
    slug = str(meta["slug"])
    if meta.get("media_kind") == "movie":
        return f"/{slug}/"
    if season is not None and episode is not None:
        return f"/{slug}/s{season}e{episode}/"
    return f"/{slug}/"
