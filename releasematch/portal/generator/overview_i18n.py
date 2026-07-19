#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMDB 简介双语解析（生成期，优先读 MySQL）。

@module portal.generator.overview_i18n
@description
  ``RM_SITE_I18N_ENABLED=true`` 时，从模板上下文的 ``overview_en`` / ``overview_zh``
  （已由 pipeline 一次性写入 MySQL）组装双语 payload；**默认不再 live 打 TMDB**。
  仅当两侧皆空且环境变量 ``RM_OVERVIEW_LIVE_TMDB=1`` 时才回退 API。
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

# CJK 字符检测（中日韩统一表意文字）
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def _looks_chinese(text: str) -> bool:
    """
    判断文本是否主要为中文。

    @param text: 待检测字符串
    @returns: 含 CJK 字符时为 True
    """
    return bool(_CJK_RE.search(text or ""))


def _fetch_tmdb_overview(
    *,
    tmdb_id: int,
    media_kind: str,
    language: str,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> str:
    """
    从 TMDB API 拉取指定语言的 overview（仅排障回退路径）。

    @param tmdb_id: TMDB 作品 ID
    @param media_kind: tv | movie
    @param language: en-US | zh-CN
    @param season: 剧集季号（单集页）
    @param episode: 剧集集号
    @returns: overview 文本；失败时空串
    """
    from workflow.metadata.tmdb_api import TmdbApiClient

    client = TmdbApiClient()
    if not client.configured():
        return ""

    if media_kind == "tv" and season and episode:
        path = f"/tv/{tmdb_id}/season/{season}/episode/{episode}"
    elif media_kind == "tv":
        path = f"/tv/{tmdb_id}"
    else:
        path = f"/movie/{tmdb_id}"

    target = client._build_target_url(path, language=language)
    data = client._get_json(target)
    if not data:
        return ""
    return str(data.get("overview") or "").strip()


def resolve_bilingual_overviews(
    ctx: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    """
    解析页面上下文中各 overview 字段的 en/zh 版本。

    @param ctx: 未本地化的 Jinja 模板变量（含 overview_en / overview_zh）
    @returns: ``{field_key: {en, zh}}``；无内容时省略键
    """
    db_en = str(ctx.get("overview_en") or "").strip()
    db_zh = str(ctx.get("overview_zh") or "").strip()

    field_sources: Dict[str, str] = {}
    for key in (
        "episode_overview",
        "tmdb_overview",
        "movie_overview",
        "show_overview",
    ):
        val = str(ctx.get(key) or "").strip()
        if val or db_en or db_zh:
            field_sources[key] = val or db_en or db_zh

    if not field_sources:
        return {}

    api_en = ""
    api_zh = ""
    live = str(os.environ.get("RM_OVERVIEW_LIVE_TMDB") or "").strip() in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )
    if live and not (db_en and db_zh):
        tmdb_id = int(ctx.get("tmdb_id") or 0)
        media_kind = str(ctx.get("media_kind") or "tv")
        season = ctx.get("season")
        episode = ctx.get("episode")
        if tmdb_id > 0:
            api_en = _fetch_tmdb_overview(
                tmdb_id=tmdb_id,
                media_kind=media_kind,
                language="en-US",
                season=int(season) if season is not None else None,
                episode=int(episode) if episode is not None else None,
            )
            api_zh = _fetch_tmdb_overview(
                tmdb_id=tmdb_id,
                media_kind=media_kind,
                language="zh-CN",
                season=int(season) if season is not None else None,
                episode=int(episode) if episode is not None else None,
            )

    out: Dict[str, Dict[str, str]] = {}
    for key, stored in field_sources.items():
        en = db_en or api_en or (stored if not _looks_chinese(stored) else "")
        zh = db_zh or api_zh or (stored if _looks_chinese(stored) else "")
        if not en and stored and not _looks_chinese(stored):
            en = stored
        if not zh and stored and _looks_chinese(stored):
            zh = stored
        if not en and stored:
            en = stored
        if not zh and stored:
            zh = stored
        if en or zh:
            out[key] = {"en": en, "zh": zh}
    return out
