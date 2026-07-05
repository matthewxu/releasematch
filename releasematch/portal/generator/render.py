#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jinja2 页面渲染器 — 读 DB 上下文 → HTML。

@module portal.generator.render
@description
  将 EpisodePageContext / MoviePageContext / ShowHubPageContext
  渲染为 portal/generator/templates/ 下的静态 HTML。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from schema.d1_models import EpisodePageContext, MoviePageContext, ShowHubPageContext

# 模板目录
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# 页面类型 → 模板文件名
_TEMPLATE_BY_TYPE = {
    "episode": "episode.html",
    "movie": "movie.html",
    "show_hub": "show_hub.html",
}

PageContext = Union[EpisodePageContext, MoviePageContext, ShowHubPageContext]


def _build_jinja_env() -> Environment:
    """
    创建 Jinja2 环境。

    @returns: 配置好的 Environment
    """
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def context_to_template_vars(
    ctx: PageContext,
    site_origin: str = "",
    *,
    show_ig_debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    将页面上下文 dataclass 转为模板变量 dict。

    @param ctx: 页面上下文对象
    @param site_origin: 站点 origin；本地预览传 http://localhost:8080 或空串
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG；None 时读配置
    @returns: Jinja2 render 参数字典
    """
    from workflow.config import SHOW_IG_DEBUG

    from portal.generator.ig_debug import build_ig_debug_panel

    from portal.generator.i18n import merge_render_context

    variables = ctx.to_template_context(site_origin=site_origin)
    enabled = SHOW_IG_DEBUG if show_ig_debug is None else show_ig_debug
    variables["show_ig_debug"] = enabled
    variables["ig_debug"] = build_ig_debug_panel(ctx, variables) if enabled else None
    return merge_render_context(variables)


def render_html(
    template_name: str,
    context: Dict[str, Any],
) -> str:
    """
    渲染单个模板为 HTML 字符串。

    @param template_name: 如 episode.html
    @param context: 模板变量
    @returns: 完整 HTML 文档
    """
    from portal.generator.i18n import merge_render_context

    env = _build_jinja_env()
    template = env.get_template(template_name)
    return template.render(**merge_render_context(context))


def render_page_context(
    page_bundle: Dict[str, Any],
    site_origin: str = "",
    *,
    show_ig_debug: Optional[bool] = None,
) -> str:
    """
    从 mysql_store.load_page_for_url 返回的 bundle 渲染 HTML。

    @param page_bundle: 含 template、context 的字典
    @param site_origin: 站点 origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: HTML 字符串
    """
    ctx = page_bundle["context"]
    template_name = page_bundle["template"]
    variables = context_to_template_vars(
        ctx, site_origin=site_origin, show_ig_debug=show_ig_debug
    )
    return render_html(template_name, variables)


def render_home_page(
    store: Any,
    site_origin: str = "",
    *,
    show_ig_debug: Optional[bool] = None,
) -> str:
    """
    渲染首页目录（全部 published 槽位入口）。

    @param store: MySQLStore 实例
    @param site_origin: 站点 origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: 完整 HTML 字符串
    """
    from datetime import datetime, timezone

    from workflow.config import SHOW_IG_DEBUG

    from workflow.storage.failed_slots_store import list_scarcity_home_entries

    entries = store.list_home_catalog_entries()
    movie_count = sum(1 for e in entries if e.get("media_kind") == "movie")
    tv_count = sum(1 for e in entries if e.get("media_kind") == "tv")
    scarcity_entries = list_scarcity_home_entries(limit=8)
    context = {
        "nav_active": "home",
        "canonical_url": f"{site_origin.rstrip('/')}/" if site_origin else "https://releasematch.io/",
        "catalog_entries": entries,
        "catalog_count": len(entries),
        "movie_count": movie_count,
        "tv_count": tv_count,
        "scarcity_entries": scarcity_entries,
        "scarcity_count": len(scarcity_entries),
        "year": str(datetime.now(timezone.utc).year),
        "show_ig_debug": SHOW_IG_DEBUG if show_ig_debug is None else show_ig_debug,
        "ig_debug": None,
    }
    return render_html("home.html", context)


def render_by_page_id(
    store: Any,
    page_id: str,
    site_origin: str = "",
    *,
    show_ig_debug: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """
    按 page_id 从 MySQL 加载并渲染。

    @param store: MySQLStore 实例
    @param page_id: 页面主键
    @param site_origin: 站点 origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: 含 html、template、output_path 的字典；失败返回 None
    """
    bundle = _load_bundle_by_page_id(store, page_id)
    if not bundle:
        return None

    ctx = bundle["context"]
    page = ctx.page
    variables = context_to_template_vars(
        ctx, site_origin=site_origin, show_ig_debug=show_ig_debug
    )
    html = render_html(bundle["template"], variables)
    return {
        "page_id": page_id,
        "template": bundle["template"],
        "canonical_path": page.canonical_path,
        "output_relpath": _canonical_to_output_relpath(page.canonical_path),
        "html": html,
    }


def _load_bundle_by_page_id(store: Any, page_id: str) -> Optional[Dict[str, Any]]:
    """
    按 page_id 加载页面 bundle。

    @param store: MySQLStore
    @param page_id: 主键
    @returns: template + context 字典
    """
    if ":hub" in page_id:
        ctx = store.get_show_hub_page_context(page_id)
        if not ctx:
            return None
        return {"template": "show_hub.html", "context": ctx}

    ctx = store.get_movie_page_context(page_id)
    if ctx:
        return {"template": "movie.html", "context": ctx}

    ctx = store.get_episode_page_context(page_id)
    if ctx:
        return {"template": "episode.html", "context": ctx}
    return None


def _canonical_to_output_relpath(canonical_path: str) -> str:
    """
    将 canonical 路径转为 dist 下相对路径（含 index.html）。

    @param canonical_path: 如 /breaking-bad/s4e6/
    @returns: 如 breaking-bad/s4e6/index.html
    """
    parts = [p for p in canonical_path.strip("/").split("/") if p]
    if not parts:
        return "index.html"
    return "/".join(parts) + "/index.html"
