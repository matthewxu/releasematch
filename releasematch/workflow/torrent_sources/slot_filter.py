#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
剧集槽位标题过滤（P0：剔除 Jackett 等同季集误匹配）。

@module workflow.torrent_sources.slot_filter
@description
  Torznab /all 按 tvdbid 搜索时，常返回其他作品的同季集 release（如 FROM S04E06…）。
  本模块在 fetch 层按 **季集 + 作品名 token** 过滤；EZTV 等 API 已按 imdb 过滤的源可豁免。
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, List, Optional, Sequence

from workflow.torrent_sources.models import ResourceItem

# S04E06 / s4e6 / Season 4 Episode 6
_SEASON_EPISODE_RE = re.compile(
    r"(?:^|[\s._\-])s(?:eason)?\s*0*(\d+)\s*e(?:p(?:isode)?)?\s*0*(\d+)(?:[\s._\-]|$)",
    re.IGNORECASE,
)
# 4x06
_SEASON_EPISODE_X_RE = re.compile(
    r"(?:^|[\s._\-])0*(\d+)x0*(\d+)(?:[\s._\-]|$)",
    re.IGNORECASE,
)
# 中文「第01集」「第1话」；多季「第2季第1集」
_CN_EPISODE_RE = re.compile(
    r"第\s*0*(\d+)\s*(?:集|话|回)",
    re.IGNORECASE,
)
_CN_SEASON_EPISODE_RE = re.compile(
    r"第\s*0*(\d+)\s*季\s*第\s*0*(\d+)\s*(?:集|话|回)",
    re.IGNORECASE,
)
# 独立 E01 / EP01（无季号时视为 S01）
_STANDALONE_EP_RE = re.compile(
    r"(?:^|[\s._\-])e(?:p(?:isode)?)?\s*0*(\d+)(?:[\s._\-]|$)",
    re.IGNORECASE,
)
# 整季/Complete 包（华语常见 NYHD Complete）
_CN_COMPLETE_RE = re.compile(
    r"(?:^|[\s._\-])(?:complete|全集|整季)(?:[\s._\-]|$)",
    re.IGNORECASE,
)
# EP01-20 / E01-E54 范围包（首集可视为 S01E01）
_CN_EP_RANGE_START_RE = re.compile(
    r"(?:^|[\s._\-])e(?:p(?:isode)?)?\s*0*(\d+)\s*[\-–—~至到]\s*0*(\d+)(?:[\s._\-]|$)",
    re.IGNORECASE,
)
# 国漫/字幕组常见：01-15 Fin、[1~15]、【1~15】、2022][01-15
_CN_BRACKET_RANGE_RE = re.compile(
    r"[\[\(【]?\s*0*(\d+)\s*[\-–—~至到]\s*0*(\d+)\s*(?:Fin|fin|全集)?\s*[\]\)】]?",
    re.IGNORECASE,
)
# 单集号：[2022][14]、【01】、- 09 (
_CN_BRACKET_EP_RE = re.compile(
    r"[\[\(【]\s*0*(\d+)\s*[\]\)】]",
    re.IGNORECASE,
)
_CN_DASH_EP_RE = re.compile(
    r"[\-–—]\s*0*(\d+)\s*\(",
    re.IGNORECASE,
)

_STOP_WORDS: FrozenSet[str] = frozenset({"the", "a", "an", "of", "and", "in", "to"})

# API 已按 imdb_id + season + episode 过滤，不再要求标题含作品名
_TRUSTED_TV_INDEXERS: FrozenSet[str] = frozenset({"eztv"})


def normalize_title(text: str) -> str:
    """
    将 release 标题归一化为小写空格分隔串。

    @param text: 原始标题
    @returns: 归一化字符串
    """
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def show_title_tokens(show_title: str) -> List[str]:
    """
    从作品名提取用于匹配的显著 token。

    @param show_title: TMDB 作品英文名
    @returns: token 列表（去停用词，长度 >= 2）
    """
    words = normalize_title(show_title).split()
    return [w for w in words if len(w) >= 2 and w not in _STOP_WORDS]


def matches_cn_season_pack(
    title: str,
    season: int,
    episode: int,
    search_titles: Optional[List[str]] = None,
) -> bool:
    """
    华语整季包是否可映射到目标槽位（如 Nirvana.in.Fire.Complete → S01E01）。

    @param title: release 标题
    @param season: 季号
    @param episode: 集号
    @param search_titles: 多语言作品名
    @returns: Complete/EP01-N 包且标题命中作品名时为 True
    """
    if season != 1 or episode != 1:
        return False
    raw = title or ""
    from workflow.torrent_sources.asia_region import any_title_matches_release

    titles = [t for t in (search_titles or []) if t]
    if not titles or not any_title_matches_release(raw, titles):
        return False
    if _CN_COMPLETE_RE.search(raw):
        return True
    range_match = _CN_EP_RANGE_START_RE.search(raw)
    if range_match:
        try:
            return int(range_match.group(1)) == 1
        except (TypeError, ValueError):
            pass
    bracket_range = _CN_BRACKET_RANGE_RE.search(raw)
    if bracket_range:
        try:
            return int(bracket_range.group(1)) == 1
        except (TypeError, ValueError):
            pass
    return False


def matches_cn_episode_in_pack(
    title: str,
    season: int,
    episode: int,
    search_titles: Optional[List[str]] = None,
) -> bool:
    """
    国漫单集或全集包内某一集是否命中槽位（如 [2022][14] 或 01-15 Fin 含 E01）。

    @param title: release 标题
    @param season: 季号
    @param episode: 集号
    @param search_titles: 多语言作品名
    @returns: 标题命中作品且季集可解析时为 True
    """
    if season != 1:
        return False
    raw = title or ""
    from workflow.torrent_sources.asia_region import any_title_matches_release

    titles = [t for t in (search_titles or []) if t]
    if not titles or not any_title_matches_release(raw, titles):
        return False
    if matches_cn_season_pack(raw, season, episode, titles):
        return True
    bracket_range = _CN_BRACKET_RANGE_RE.search(raw)
    if bracket_range:
        try:
            start = int(bracket_range.group(1))
            end = int(bracket_range.group(2))
            if start <= episode <= end:
                return True
        except (TypeError, ValueError):
            pass
    for match in _CN_BRACKET_EP_RE.finditer(raw):
        try:
            ep_num = int(match.group(1))
            # 跳过四位年份误匹配（如 [2022]）
            if ep_num >= 1900:
                continue
            if ep_num == episode:
                return True
        except (TypeError, ValueError):
            continue
    dash_match = _CN_DASH_EP_RE.search(raw)
    if dash_match:
        try:
            if int(dash_match.group(1)) == episode:
                return True
        except (TypeError, ValueError):
            pass
    return False


def matches_season_episode(title: str, season: int, episode: int) -> bool:
    """
    判断标题是否包含目标季集号。

    @param title: release 标题
    @param season: 季号
    @param episode: 集号
    @returns: 是否匹配中文第N集、SxxExx、NxM 或 EP01 等形式
    """
    text = title or ""
    season_ep = _CN_SEASON_EPISODE_RE.search(text)
    if season_ep:
        try:
            if int(season_ep.group(1)) == season and int(season_ep.group(2)) == episode:
                return True
        except (TypeError, ValueError):
            pass
    for pattern in (_SEASON_EPISODE_RE, _SEASON_EPISODE_X_RE):
        match = pattern.search(text)
        if not match:
            continue
        try:
            if int(match.group(1)) == season and int(match.group(2)) == episode:
                return True
        except (TypeError, ValueError):
            continue
    cn_match = _CN_EPISODE_RE.search(text)
    if cn_match:
        try:
            if season <= 1 and int(cn_match.group(1)) == episode:
                return True
        except (TypeError, ValueError):
            pass
    ep_match = _STANDALONE_EP_RE.search(text)
    if ep_match and season <= 1:
        try:
            if int(ep_match.group(1)) == episode:
                return True
        except (TypeError, ValueError):
            pass
    return False


def matches_show_title(title_raw: str, show_title: Optional[str]) -> bool:
    """
    判断 release 标题是否包含目标作品名 token。

    @param title_raw: release 标题
    @param show_title: 作品英文名
    @returns: 无作品名时 True；否则按 token 命中率判定
    """
    if not show_title or not str(show_title).strip():
        return True
    tokens = show_title_tokens(show_title)
    if not tokens:
        return True
    norm = normalize_title(title_raw)
    if not norm:
        return False
    matched = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", norm))
    if len(tokens) <= 2:
        return matched >= len(tokens)
    return matched >= max(2, (len(tokens) + 1) // 2)


def indexer_family(indexer: str) -> str:
    """
    将 indexer 字段归一化为源族名（eztv / jackett / nyaa …）。

    @param indexer: ResourceItem.indexer
    @returns: 小写源族标识
    """
    label = (indexer or "").lower().strip()
    if label.startswith("jackett:"):
        return "jackett"
    if label.startswith("nyaa"):
        return "nyaa"
    return label.split(":", 1)[0]


def matches_tv_slot(
    title_raw: str,
    show_title: Optional[str],
    season: int,
    episode: int,
    *,
    indexer: str = "",
    require_show_title: bool = True,
    alt_titles: Optional[List[str]] = None,
) -> bool:
    """
    单条 release 是否属于目标剧集槽位。

    @param title_raw: release 标题
    @param show_title: 作品英文名
    @param season: 季号
    @param episode: 集号
    @param indexer: 来源 indexer（用于 EZTV 豁免）
    @param require_show_title: 是否校验作品名 token
    @param alt_titles: 额外搜索标题（日韩本地名等）
    @returns: 是否保留
    """
    from workflow.torrent_sources.asia_region import any_title_matches_release

    candidates = [t for t in ([show_title] if show_title else []) + list(alt_titles or []) if t]
    if matches_cn_season_pack(title_raw, season, episode, candidates):
        return True
    if matches_cn_episode_in_pack(title_raw, season, episode, candidates):
        return True
    if not matches_season_episode(title_raw, season, episode):
        return False
    family = indexer_family(indexer)
    if family in _TRUSTED_TV_INDEXERS:
        return True
    if not require_show_title:
        return True

    if not candidates:
        return True
    return any_title_matches_release(title_raw, candidates)


def explain_tv_slot_rejection(
    title_raw: str,
    show_title: Optional[str],
    season: int,
    episode: int,
    *,
    indexer: str = "",
) -> Optional[str]:
    """
    若条目被过滤，返回人类可读原因；保留则返回 None。

    @param title_raw: release 标题
    @param show_title: 作品英文名
    @param season: 季号
    @param episode: 集号
    @param indexer: 来源 indexer
    @returns: 过滤原因或 None（表示保留）
    """
    if not matches_season_episode(title_raw, season, episode):
        return "season_episode_mismatch"
    family = indexer_family(indexer)
    if family in _TRUSTED_TV_INDEXERS:
        return None
    if not matches_show_title(title_raw, show_title):
        tokens = show_title_tokens(show_title or "")
        norm = normalize_title(title_raw)
        missing = [t for t in tokens if not re.search(rf"\b{re.escape(t)}\b", norm)]
        return f"show_title_mismatch(missing={missing})"
    return None


def audit_tv_slot_filter(
    items: Sequence[ResourceItem],
    show_title: Optional[str],
    season: int,
    episode: int,
) -> Dict[str, List[Dict[str, str]]]:
    """
    审计过滤结果：保留 / 剔除清单及原因。

    @param items: 过滤前 ResourceItem 列表
    @param show_title: 作品英文名
    @param season: 季号
    @param episode: 集号
    @returns: {"kept": [...], "rejected": [...]} 字典
    """
    kept: List[Dict[str, str]] = []
    rejected: List[Dict[str, str]] = []
    for item in items:
        reason = explain_tv_slot_rejection(
            item.title_raw,
            show_title,
            season,
            episode,
            indexer=item.indexer,
        )
        row = {
            "indexer": item.indexer,
            "title_raw": item.title_raw,
            "infohash": item.infohash[:12],
        }
        if reason:
            row["reason"] = reason
            rejected.append(row)
        else:
            kept.append(row)
    return {"kept": kept, "rejected": rejected}


def filter_tv_slot_items(
    items: Sequence[ResourceItem],
    show_title: Optional[str],
    season: int,
    episode: int,
    alt_titles: Optional[List[str]] = None,
) -> List[ResourceItem]:
    """
    过滤剧集槽位 items，剔除 Jackett 等源的误匹配。

    @param items: 原始 ResourceItem 列表
    @param show_title: 作品英文名
    @param season: 季号
    @param episode: 集号
    @param alt_titles: 日韩等多语言标题
    @returns: 过滤后的新列表
    """
    kept: List[ResourceItem] = []
    for item in items:
        if matches_tv_slot(
            item.title_raw,
            show_title,
            season,
            episode,
            indexer=item.indexer,
            alt_titles=alt_titles,
        ):
            kept.append(item)
    return kept
