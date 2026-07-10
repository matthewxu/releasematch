#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出站链接 HTML 属性常量 — 全站外链统一 target / rel。

@module portal.generator.link_attrs
@description
  页面上的外出链接（TMDB、SubtitlePortal、magnet 等）统一：
  - ``target="_blank"`` 新标签打开，不离开本站浏览上下文
  - ``rel="nofollow"`` 不向目标站传递 PageRank 权重
  - ``noopener noreferrer`` 配合 target=_blank 的安全与隐私最佳实践
"""

from __future__ import annotations

from typing import Dict

# 出站链接 target：新标签页打开
OUTBOUND_LINK_TARGET: str = "_blank"

# 出站链接 rel：不传权重 + 新窗口安全属性（TMDB、magnet 等通用外链）
OUTBOUND_LINK_REL: str = "nofollow noopener noreferrer"

# 用户生成/跨站语境出站链（如 SubtitlePortal）：在 nofollow 基础上保留 ugc
OUTBOUND_LINK_REL_UGC: str = "nofollow ugc noopener noreferrer"

# 测速可信度与 RM Grab 指数说明页（站内 Trust 页，非外出链）
METRICS_GUIDE_PATH: str = "/trust/speed-and-grab/"


def outbound_link_context() -> Dict[str, str]:
    """
    注入 Jinja 模板的链接策略变量。

    @returns: 含出站链 target/rel 与 metrics_guide_path 的字典
    """
    return {
        "outbound_link_target": OUTBOUND_LINK_TARGET,
        "outbound_link_rel": OUTBOUND_LINK_REL,
        "outbound_link_rel_ugc": OUTBOUND_LINK_REL_UGC,
        "metrics_guide_path": METRICS_GUIDE_PATH,
    }
