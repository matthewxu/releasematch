#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日韩内容区域判定与多语言搜索词。

@module workflow.torrent_sources.asia_region
@description 依据 TMDB original_language / standalone 映射选择 Nyaa LA 路由与搜索标题。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# CJK 字符检测（含日文假名、韩文 Hangul）
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def detect_content_region(metadata: Dict[str, Any]) -> Optional[str]:
    """
    判定作品是否走日韩路由。

    @param metadata: resolve_external_ids 或扩展字段（含 original_language）
    @returns: "jp" | "kr" | None（None 走欧美默认路由）
    """
    lang = str(metadata.get("original_language") or "").lower().strip()
    if lang == "ja":
        return "jp"
    if lang == "ko":
        return "kr"
    countries = metadata.get("origin_country") or []
    if isinstance(countries, str):
        countries = [countries]
    upper = {str(c).upper() for c in countries}
    if "JP" in upper and lang in ("ja", "en", ""):
        return "jp"
    if "KR" in upper and lang in ("ko", "en", ""):
        return "kr"
    return None


def build_search_titles(metadata: Dict[str, Any], region: Optional[str] = None) -> List[str]:
    """
    生成 Nyaa / Jackett 多语言搜索词列表（去重保序）。

    @param metadata: 含 title、title_ja、title_ko
    @param region: jp | kr | None
    @returns: 标题变体列表
    """
    region = region or detect_content_region(metadata)
    titles: List[str] = []

    def _add(value: Any) -> None:
        """追加非空标题。"""
        if isinstance(value, str) and value.strip():
            titles.append(value.strip())

    _add(metadata.get("title"))
    if region == "jp":
        _add(metadata.get("title_ja"))
    elif region == "kr":
        _add(metadata.get("title_ko"))

    seen: set[str] = set()
    ordered: List[str] = []
    for title in titles:
        key = title.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(title)
    return ordered


def title_matches_release(release_title: str, search_title: str) -> bool:
    """
    判断 release 标题是否命中某一搜索词（支持 CJK 子串）。

    @param release_title: torrent 标题
    @param search_title: 搜索用词
    @returns: 是否匹配
    """
    if not search_title or not str(search_title).strip():
        return False
    query = str(search_title).strip()
    raw = release_title or ""
    if _CJK_RE.search(query):
        return query in raw
    from workflow.torrent_sources.slot_filter import matches_show_title

    return matches_show_title(raw, query)


def any_title_matches_release(release_title: str, search_titles: List[str]) -> bool:
    """
    任一搜索词命中 release 标题。

    @param release_title: torrent 标题
    @param search_titles: 多语言标题列表
    @returns: 是否匹配
    """
    return any(title_matches_release(release_title, t) for t in search_titles)
