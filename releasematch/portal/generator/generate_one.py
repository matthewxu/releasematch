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

from portal.generator.render import HOME_CATALOG_PER_PAGE, render_by_page_id, render_home_page
from portal.generator.sitemap import write_sitemap
from portal.generator.static_shell import sync_static_shell

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

    # 统管表：记录上线/最近生成时间（Ops 台账「上线时间」）
    try:
        store.mark_page_generated(page_id)
    except Exception:  # noqa: BLE001 — 写盘成功不因时间戳失败回滚
        pass

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
    on_page: Optional[Any] = None,
    on_phase: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    批量生成 episode/movie 静态 HTML，并写入首页、Hub、sitemap。

    indexable（published 且 magnet≥2）输出 index,follow；thin 页仍生成 HTML 但为 noindex,follow，
    避免 Hub/prev-next 内链 404，同时不进 sitemap。

    生成前会幂等补齐「有 episode、无 Hub」的 show_hub 行，避免 ``/{slug}/`` 空目录。

    @param out_root: 输出根目录
    @param site_origin: canonical origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @param on_page: 可选进度回调 ``(index, total, page_id, result) -> None``
    @param on_phase: 可选阶段回调 ``(phase, detail) -> None``
      phase: ensure_hubs | pages | home | hubs | sitemap | trust | static_shell
    @returns: 批量摘要
    """

    def _phase(name: str, detail: str = "") -> None:
        """安全调用阶段回调。"""
        if not callable(on_phase):
            return
        try:
            on_phase(name, detail)
        except Exception:  # noqa: BLE001 — 进度回调失败不阻断 generate
            pass

    store = MySQLStore()
    # 流程闸门：历史槽可能只有单集而无 Hub；generate 前先落库再渲染
    _phase("ensure_hubs", "补齐缺失 show_hub…")
    hub_ensure = store.ensure_missing_show_hubs()
    page_ids = store.list_renderable_page_ids()
    published_ids = set(store.list_published_page_ids())
    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    total = len(page_ids)

    _phase("pages", f"开始烘焙 {total} 个 episode/movie 页…")
    for idx, page_id in enumerate(page_ids):
        result = write_page_html(
            page_id,
            out_root=out_root,
            site_origin=site_origin,
            show_ig_debug=show_ig_debug,
        )
        result["indexable"] = page_id in published_ids
        results.append(result)
        if not result.get("ok"):
            errors.append(f"{page_id}: {result.get('error')}")
        if callable(on_page):
            try:
                on_page(idx + 1, total, page_id, result)
            except Exception:  # noqa: BLE001 — 进度回调失败不阻断 generate
                pass

    _phase("home", "写入首页目录（按源更新时间降序）…")
    home_result = write_home_page(out_root=out_root, site_origin=site_origin, show_ig_debug=show_ig_debug)
    _phase("hubs", "写入全部 show_hub…")
    hub_result = write_all_show_hubs(
        out_root=out_root, site_origin=site_origin, show_ig_debug=show_ig_debug
    )
    _phase("sitemap", "写入 sitemap…")
    sitemap_result = write_sitemap(out_root=out_root, site_origin=site_origin)

    from portal.generator.render_trust import write_trust_pages

    _phase("trust", "写入 Trust 页…")
    trust_result = write_trust_pages(out_root=out_root, site_origin=site_origin)

    _phase("static_shell", "同步 CSS/JS 静态壳…")
    static_shell_result = sync_static_shell(out_root=out_root)

    indexable_generated = sum(1 for r in results if r.get("ok") and r.get("indexable"))
    noindex_generated = sum(1 for r in results if r.get("ok") and not r.get("indexable"))

    return {
        "ok": len(errors) == 0 and hub_ensure.get("ok", True),
        "count": len(page_ids),
        "generated": sum(1 for r in results if r.get("ok")),
        "indexable_generated": indexable_generated,
        "noindex_generated": noindex_generated,
        "out_root": str(out_root),
        "pages": results,
        "errors": errors + list(hub_ensure.get("errors") or []),
        "hub_ensure": hub_ensure,
        "home": home_result,
        "hubs": hub_result,
        "sitemap": sitemap_result,
        "trust": trust_result,
        "static_shell": static_shell_result,
    }


def write_all_show_hubs(
    out_root: Path = DEFAULT_OUT_ROOT,
    site_origin: str = SITE_ORIGIN,
    *,
    show_ig_debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    批量生成全部 show_hub 静态页。

    调用前再次 ``ensure_missing_show_hubs``，保证单独跑 Hub 生成也不会漏页。

    @param out_root: 输出根目录
    @param site_origin: canonical origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: 批量摘要
    """
    store = MySQLStore()
    hub_ensure = store.ensure_missing_show_hubs()
    hub_ids = store.list_show_hub_page_ids()
    results: List[Dict[str, Any]] = []
    errors: List[str] = list(hub_ensure.get("errors") or [])

    for page_id in hub_ids:
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
        "count": len(hub_ids),
        "generated": sum(1 for r in results if r.get("ok")),
        "hub_ensure": hub_ensure,
        "pages": results,
        "errors": errors,
    }


def write_home_page(
    out_root: Path = DEFAULT_OUT_ROOT,
    site_origin: str = SITE_ORIGIN,
    *,
    show_ig_debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    生成首页目录静态页（按最新更新排序，每页 50 条）。

    @param out_root: 输出根目录
    @param site_origin: canonical origin
    @param show_ig_debug: 覆盖 RM_SHOW_IG_DEBUG
    @returns: 生成摘要（含各分页输出路径）
    @description
      第 1 页写入 ``index.html``；第 2 页起写入 ``catalog/page/N/index.html``。
      同步 ``static/`` 到 dist，确保分页 CSS 等资源可用。
    """
    from portal.generator.static_shell import sync_static_shell

    store = MySQLStore()
    peek = store.list_home_catalog_entries(limit=1, offset=0)
    total = int(peek.get("total") or 0)
    per_page = HOME_CATALOG_PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    output_files: list[str] = []
    for page_num in range(1, total_pages + 1):
        html = render_home_page(
            store,
            site_origin=site_origin,
            show_ig_debug=show_ig_debug,
            page=page_num,
            per_page=per_page,
        )
        if page_num <= 1:
            out_file = out_root / "index.html"
        else:
            out_file = out_root / "catalog" / "page" / str(page_num) / "index.html"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(html, encoding="utf-8")
        output_files.append(str(out_file))
    shell_result = sync_static_shell(out_root=out_root)
    return {
        "ok": True,
        "output_file": output_files[0] if output_files else str(out_root / "index.html"),
        "output_files": output_files,
        "catalog_count": total,
        "page_count": total_pages,
        "per_page": per_page,
        "static_shell": shell_result,
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
