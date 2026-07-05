#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前端语言切换 — 动态正文双语 payload。

@module portal.generator.i18n_dynamic
@description
  ``RM_SITE_I18N_ENABLED=true`` 时，在 ``rm-i18n-data`` 中注入 ``dynamic`` 字段，
  供 ``site.js`` 通过 ``data-i18n-dynamic`` 切换 recommend_reason、测速摘要、TMDB 简介等。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Tuple

from portal.generator.i18n import normalize_locale, translate
from portal.generator.i18n_speed import apply_page_locale
from portal.generator.overview_i18n import resolve_bilingual_overviews

# 动态字段提取：(payload_key, getter)
_DYNAMIC_EXTRACTORS: List[Tuple[str, Callable[[Dict[str, Any]], Optional[str]]]] = [
    ("recommend_reason", lambda c: _get_nested(c, "recommended", "recommend_reason")),
    ("speed_endorsement", lambda c: _get_nested(c, "recommended", "speed_endorsement")),
    ("grab_index_summary", lambda c: _get_nested(c, "recommended", "grab_index", "grab_index_summary")),
    ("grab_index_tier_label", lambda c: _get_nested(c, "recommended", "grab_index", "grab_index_tier_label")),
    ("speed_method_note", lambda c: _get_nested(c, "speed_evidence", "method_note")),
    ("speed_freshness_label", lambda c: _get_nested(c, "speed_evidence", "freshness_label")),
    ("speed_freshness_note", lambda c: _get_nested(c, "speed_evidence", "freshness_note")),
    ("speed_age_display", lambda c: _get_nested(c, "speed_evidence", "age_display")),
    ("speed_validity_level", lambda c: _get_nested(c, "speed_evidence", "validity_level")),
    ("speed_reachability_display", lambda c: _get_nested(c, "speed_evidence", "reachability_display")),
    ("speed_reachability_detail", lambda c: _get_nested(c, "speed_evidence", "reachability_detail")),
    ("speed_index_vs_measured", lambda c: _get_nested(c, "speed_evidence", "index_vs_measured")),
    ("speed_spread_display", lambda c: _get_nested(c, "speed_evidence", "speed_spread_display")),
    ("speed_connect_rate_display", lambda c: _get_nested(c, "speed_evidence", "connect_rate_display")),
    ("speed_freshness_validity_line", lambda c: ""),  # 由 _freshness_validity_line_for_locale 生成
    ("speed_facts_time_sub", lambda c: ""),  # 由 _speed_facts_time_sub_for_locale 生成
]


def _freshness_validity_line_for_locale(ctx: Dict[str, Any], locale: str) -> str:
    """
    按 locale 生成可信度行文案。

    @param ctx: 本地化后的上下文
    @param locale: en | zh
    @returns: 如「Confidence Low」
    """
    level = _get_nested(ctx, "speed_evidence", "validity_level")
    if not level:
        return ""
    return translate("speed.freshness.validity", normalize_locale(locale), level=level)


def _get_nested(ctx: Dict[str, Any], *keys: str) -> str:
    """
    安全读取嵌套 dict 字符串字段。

    @param ctx: 根 dict
    @param keys: 键路径
    @returns: 字符串或空串
    """
    cur: Any = ctx
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return str(cur or "").strip()


def _speed_facts_time_sub_for_locale(ctx: Dict[str, Any], locale: str) -> str:
    """
    按 locale 生成测速 facts 时间副文案。

    @param ctx: 本地化后的模板上下文
    @param locale: en | zh
    @returns: 拼接字符串
    """
    se = ctx.get("speed_evidence")
    if not isinstance(se, dict):
        return ""
    loc = normalize_locale(locale)
    parts: List[str] = []
    age = str(se.get("age_display") or "").strip()
    if age:
        parts.append(age)
    fresh = str(se.get("freshness_label") or "").strip()
    if fresh:
        parts.append(fresh)
    validity = str(se.get("validity_level") or "").strip()
    if validity:
        parts.append(translate("speed.metric.validity", loc, level=validity))
    return " · ".join(parts)


def _speed_panel_summary(ctx: Dict[str, Any], locale: str) -> str:
    """
    测速面板 summary 行文案。

    @param ctx: 本地化后的模板上下文
    @param locale: en | zh
    @returns: summary 字符串
    """
    se = ctx.get("speed_evidence")
    if not isinstance(se, dict):
        return ""
    loc = normalize_locale(locale)
    return translate(
        "speed.panel.summary",
        loc,
        avg=se.get("avg_speed") or "—",
        reach=se.get("reachability_display") or se.get("reachability") or "—",
    )


def _speed_footnote(ctx: Dict[str, Any], locale: str) -> str:
    """
    测速面板脚注（含 HTML strong）。

    @param ctx: 本地化后的模板上下文
    @param locale: en | zh
    @returns: HTML 字符串
    """
    se = ctx.get("speed_evidence")
    if not isinstance(se, dict):
        return ""
    loc = normalize_locale(locale)
    return translate("speed.footnote", loc, method=se.get("method_note") or "")


def _extract_locale_fields(ctx: Dict[str, Any], locale: str) -> Dict[str, str]:
    """
    从已本地化上下文提取动态字段。

    @param ctx: 应用 locale 后的 dict
    @param locale: en | zh
    @returns: payload_key -> 文本
    """
    out: Dict[str, str] = {}
    for key, getter in _DYNAMIC_EXTRACTORS:
        if key == "speed_facts_time_sub":
            val = _speed_facts_time_sub_for_locale(ctx, locale)
        elif key == "speed_freshness_validity_line":
            val = _freshness_validity_line_for_locale(ctx, locale)
        else:
            val = getter(ctx) or ""
        if val:
            out[key] = val
    summary = _speed_panel_summary(ctx, locale)
    if summary:
        out["speed_panel_summary"] = summary
    footnote = _speed_footnote(ctx, locale)
    if footnote:
        out["speed_footnote"] = footnote
    return out


def build_i18n_dynamic(ctx: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    构建 ``{field: {en, zh}}`` 动态文案 catalog。

    @param ctx: 合并 i18n 前或后的模板上下文（须含 speed_evidence / recommended 等）
    @returns: 供前端 ``data-i18n-dynamic`` 使用的 dict
    """
    dynamic: Dict[str, Dict[str, str]] = {}

    for loc in ("en", "zh"):
        snap = deepcopy(ctx)
        apply_page_locale(snap, loc)
        for key, text in _extract_locale_fields(snap, loc).items():
            dynamic.setdefault(key, {})[loc] = text

    for field_key, texts in resolve_bilingual_overviews(ctx).items():
        dynamic[field_key] = texts

    return dynamic
