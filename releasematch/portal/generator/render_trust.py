#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trust 五页静态 HTML 生成器。

@module portal.generator.render_trust
@description
  将 ``/trust/*`` 从手写静态 HTML 迁移为 Jinja 模板，支持 ``RM_SITE_I18N_ENABLED`` 双语切换。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from portal.generator.i18n import build_i18n_runtime, merge_render_context
from portal.generator.render import render_html
from portal.generator.trust_content import TRUST_PAGES
from workflow.config import PROJECT_ROOT, SITE_ORIGIN


def _trust_page_context(page_def: Dict[str, Any], site_origin: str) -> Dict[str, Any]:
    """
    组装单 Trust 页模板变量。

    @param page_def: TRUST_PAGES 条目
    @param site_origin: canonical origin
    @returns: Jinja 参数字典
    """
    slug = str(page_def["slug"])
    body = page_def["body"]
    locale = build_i18n_runtime().locale
    ctx: Dict[str, Any] = {
        "nav_active": slug if slug == "how-matching-works" else "",
        "trust_slug": slug,
        "trust_title_key": page_def["title_key"],
        "trust_meta_key": page_def["meta_key"],
        "trust_heading_key": page_def["title_key"].replace(".title", ".heading"),
        "trust_body_html": body.get(locale) or body.get("en") or "",
        "canonical_url": f"{site_origin.rstrip('/')}{page_def['canonical']}",
        "year": "2026",
        "show_ig_debug": False,
        "ig_debug": None,
    }
    runtime = build_i18n_runtime()
    ctx = merge_render_context(ctx)
    if runtime.enabled:
        ctx["i18n_dynamic"] = {**(ctx.get("i18n_dynamic") or {}), "trust_body": body}
    return ctx


def write_trust_pages(
    out_root: Path | None = None,
    site_origin: str = SITE_ORIGIN,
) -> Dict[str, Any]:
    """
    生成全部 Trust 页至 ``portal/dist/trust/*/index.html``。

    @param out_root: 输出根目录，默认 portal/dist
    @param site_origin: canonical origin
    @returns: 批量摘要
    """
    root = out_root or (PROJECT_ROOT / "portal" / "dist")
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    for page_def in TRUST_PAGES:
        slug = str(page_def["slug"])
        try:
            ctx = _trust_page_context(page_def, site_origin)
            html = render_html("trust/page.html", ctx)
            out_file = root / "trust" / slug / "index.html"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(html, encoding="utf-8")
            results.append({"ok": True, "slug": slug, "output_file": str(out_file)})
        except Exception as exc:  # noqa: BLE001 — 批量生成需汇总错误
            errors.append(f"{slug}: {exc}")
            results.append({"ok": False, "slug": slug, "error": str(exc)})

    return {
        "ok": len(errors) == 0,
        "count": len(TRUST_PAGES),
        "generated": sum(1 for r in results if r.get("ok")),
        "pages": results,
        "errors": errors,
    }
