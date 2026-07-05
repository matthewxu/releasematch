#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推荐理由渲染期本地化。

@module portal.generator.i18n_reason
@description
  ``RM_SITE_LOCALE=en`` 时从 Recommended 结构化字段重建英文 ``recommend_reason``，
  不修改 MySQL 中存储的中文 reason。
"""

from __future__ import annotations

from typing import Any, Dict

from portal.generator.i18n import normalize_locale
from workflow.recommended.groups_registry import lookup_group_detail
from workflow.recommended.scorer import build_recommend_reason


def localize_recommend_reason(rec: Dict[str, Any], locale: str) -> None:
    """
    就地重建 ``recommend_reason`` 为指定 locale（仅非 zh 时生效）。

    @param rec: recommended 模板字典（含 release_group、group_tier 等）
    @param locale: en | zh
    @returns: None
    """
    loc = normalize_locale(locale)
    if loc == "zh":
        return

    release_group = str(rec.get("release_group") or "")
    group_info = lookup_group_detail(release_group)
    canonical = group_info.canonical or release_group or "Unknown"
    tier = str(rec.get("group_tier") or group_info.tier or "L4")
    scene_flag = group_info.scene_compliant if group_info.canonical else None

    rec["recommend_reason"] = build_recommend_reason(
        rec,
        tier,
        canonical,
        scene_compliant=scene_flag,
        locale=loc,
    )
