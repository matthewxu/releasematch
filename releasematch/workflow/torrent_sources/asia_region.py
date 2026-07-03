#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
亚洲内容区域判定与多语言搜索词（日韩中）。

@module workflow.torrent_sources.asia_region
@description
  依据 TMDB original_language / origin_country 选择 Nyaa LA、DMHy、Jackett 路由与搜索标题。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# CJK 字符检测（含日文假名、韩文 Hangul）
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def detect_content_region(metadata: Dict[str, Any]) -> Optional[str]:
    """
    判定作品是否走亚洲专用路由。

    @param metadata: resolve_external_ids 或扩展字段（含 original_language）
    @returns: "jp" | "kr" | "cn" | None（None 走欧美默认路由）
    """
    lang = str(metadata.get("original_language") or "").lower().strip()
    if lang == "ja":
        return "jp"
    if lang == "ko":
        return "kr"
    if lang in ("zh", "cn"):
        return "cn"
    countries = metadata.get("origin_country") or []
    if isinstance(countries, str):
        countries = [countries]
    upper = {str(c).upper() for c in countries}
    if "JP" in upper and lang in ("ja", "en", ""):
        return "jp"
    if "KR" in upper and lang in ("ko", "en", ""):
        return "kr"
    if upper & {"CN", "HK", "TW"} and lang in ("zh", "cn", "en", ""):
        return "cn"
    return None


def is_asia_region(region: Optional[str]) -> bool:
    """
    是否为亚洲专用路由（日韩中）。

    @param region: detect_content_region 返回值
    @returns: True 表示跳过 EZTV/YTS 欧美主源
    """
    return region in ("jp", "kr", "cn")


def build_search_titles(metadata: Dict[str, Any], region: Optional[str] = None) -> List[str]:
    """
    生成 Nyaa / DMHy / Jackett 多语言搜索词列表（去重保序）。

    @param metadata: 含 title、title_ja、title_ko、title_zh
    @param region: jp | kr | cn | None
    @returns: 标题变体列表（中文区优先本地标题）
    """
    region = region or detect_content_region(metadata)
    primary: List[str] = []
    secondary: List[str] = []

    def _add(bucket: List[str], value: Any) -> None:
        """追加非空标题到指定桶。"""
        if isinstance(value, str) and value.strip():
            bucket.append(value.strip())

    if region == "cn":
        _add(primary, metadata.get("title_zh"))
        _add(primary, metadata.get("original_title"))
        _add(secondary, metadata.get("title"))
    elif region == "jp":
        _add(secondary, metadata.get("title"))
        _add(primary, metadata.get("title_ja"))
    elif region == "kr":
        _add(secondary, metadata.get("title"))
        _add(primary, metadata.get("title_ko"))
    else:
        _add(primary, metadata.get("title"))

    seen: set[str] = set()
    ordered: List[str] = []
    for title in primary + secondary:
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
