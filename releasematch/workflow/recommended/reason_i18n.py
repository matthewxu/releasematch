#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recommended Release 推荐理由文案（en / zh）。

@module workflow.recommended.reason_i18n
@description
  供 ``scorer.build_recommend_reason`` 与生成器渲染期重建 reason 使用；
  与 ``portal.generator.i18n`` 解耦，避免 workflow 依赖 portal。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# 推荐理由片段：key -> {en, zh}
REASON_MESSAGES: Dict[str, Dict[str, str]] = {
    "verified_group": {
        "en": "Verified Group {group} ({tier} tier)",
        "zh": "Verified Group {group}（{tier} 档信誉）",
    },
    "community_group": {
        "en": "Community Group {group} ({tier} tier)",
        "zh": "Community Group {group}（{tier} 档）",
    },
    "scene_compliant": {
        "en": "Scene-compliant release",
        "zh": "Scene 合规压制",
    },
    "p2p_quality": {
        "en": "High-quality P2P group",
        "zh": "P2P 高质量组",
    },
    "resolution": {
        "en": "{resolution} quality",
        "zh": "{resolution} 画质",
    },
    "source": {
        "en": "Source {source}",
        "zh": "来源 {source}",
    },
    "seeders": {
        "en": "{seeders} seeders currently",
        "zh": "当前 {seeders} seeders",
    },
    "cross_verified": {
        "en": "Cross-verified on {count} source families (S-04)",
        "zh": "跨 {count} 个源族交叉验证（S-04）",
    },
    "default": {
        "en": "Highest composite score",
        "zh": "综合评分最高",
    },
}


def normalize_reason_locale(raw: Optional[str]) -> str:
    """
    将 locale 归一化为 en | zh。

    @param raw: 配置或调用方传入的语言代码
    @returns: en 或 zh
    """
    token = (raw or "zh").strip().lower().replace("_", "-")
    if token.startswith("zh"):
        return "zh"
    return "en"


def reason_translate(key: str, locale: str, **kwargs: Any) -> str:
    """
    按 key 与 locale 返回推荐理由片段。

    @param key: REASON_MESSAGES 键
    @param locale: en | zh
    @param kwargs: format 占位符
    @returns: 翻译字符串
    """
    loc = normalize_reason_locale(locale)
    bucket = REASON_MESSAGES.get(key, {})
    text = bucket.get(loc) or bucket.get("zh") or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def reason_separator(locale: str) -> str:
    """
    推荐理由分句分隔符。

    @param locale: en | zh
    @returns: 「；」或 "; "
    """
    return "; " if normalize_reason_locale(locale) == "en" else "；"
