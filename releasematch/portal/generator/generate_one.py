#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单页 / 批量静态 HTML 生成器。

@module portal.generator.generate_one
@description
  从 MySQL 读取槽位数据，渲染 Jinja2 模板，写入 portal/dist/。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT, SHOW_IG_DEBUG, SITE_ORIGIN
from workflow.storage.mysql_store import MySQLStore

from portal.generator.render import render_by_page_id

# 默认输出根目录
DEFAULT_OUT_ROOT = PROJECT_ROOT / "portal" / "dist"


def write_page_html(
    page_id: str,
    out_root: Path = DEFAULT_OUT_ROOT,
    site_origin: str = SITE_ORIGIN,
    *,
    show_ig_debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    生成单个 page_id 的静态 HTML 文件。

    @param page_id: 如 tv:1396:s04e06
    @param out_root: 输出根目录（portal/dist）
    @param site_origin: canonical 用 origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG；None 时读环境配置
    @returns: 生成结果摘要
    """
    store = MySQLStore()
    ig_debug = SHOW_IG_DEBUG if show_ig_debug is None else show_ig_debug
    rendered = render_by_page_id(
        store, page_id, site_origin=site_origin, show_ig_debug=ig_debug
    )
    if not rendered:
        return {"ok": False, "page_id": page_id, "error": "页面不存在或无法加载"}

    out_file = out_root / rendered["output_relpath"]
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(rendered["html"], encoding="utf-8")

    return {
        "ok": True,
        "page_id": page_id,
        "template": rendered["template"],
        "output_file": str(out_file),
        "canonical_path": rendered["canonical_path"],
        "show_ig_debug": ig_debug,
    }


def write_all_published(
    out_root: Path = DEFAULT_OUT_ROOT,
    site_origin: str = SITE_ORIGIN,
    *,
    show_ig_debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    批量生成所有 published 且 magnet≥2 的页面。

    @param out_root: 输出根目录
    @param site_origin: canonical origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: 批量摘要
    """
    store = MySQLStore()
    page_ids = store.list_published_page_ids()
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    for page_id in page_ids:
        result = write_page_html(
            page_id,
            out_root=out_root,
            site_origin=site_origin,
            show_ig_debug=show_ig_debug,
        )
        results.append(result)
        if not result.get("ok"):
            errors.append(f"{page_id}: {result.get('error')}")

    return {
        "ok": len(errors) == 0,
        "count": len(page_ids),
        "generated": sum(1 for r in results if r.get("ok")),
        "out_root": str(out_root),
        "pages": results,
        "errors": errors,
    }


def write_by_url_path(
    url_path: str,
    out_root: Path = DEFAULT_OUT_ROOT,
    site_origin: str = SITE_ORIGIN,
    *,
    show_ig_debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    按 URL 路径生成页面（自动解析 episode/movie/hub）。

    @param url_path: 如 /breaking-bad/s4e6/
    @param out_root: 输出目录
    @param site_origin: origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: 生成摘要
    """
    store = MySQLStore()
    resolved = store.resolve_url_path(url_path)
    if not resolved:
        return {"ok": False, "url_path": url_path, "error": "无法解析路径"}
    return write_page_html(
        resolved["page_id"],
        out_root=out_root,
        site_origin=site_origin,
        show_ig_debug=show_ig_debug,
    )
