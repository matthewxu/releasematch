#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态资源壳同步 — 将 portal/static 等复制到 portal/dist。

@module portal.generator.static_shell
@description
  生成的 HTML 引用 ``/static/js/site.js`` / ``/static/js/tracking.js`` 等绝对路径。
  ``python -m http.server`` 若以 ``portal/dist`` 为根目录启动，
  必须先同步 static，否则双语切换脚本 404、语言按钮无效。
  部署脚本 ``scripts/deploy_cf_pages.sh`` 亦依赖同一逻辑。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT

# 默认 portal 根目录
DEFAULT_PORTAL_ROOT = PROJECT_ROOT / "portal"

# 默认 dist 输出目录
DEFAULT_OUT_ROOT = DEFAULT_PORTAL_ROOT / "dist"

# 需要从 portal 根复制到 dist 根的单文件列表（错误页壳）
SHELL_FILES = ("404.html", "410.html")

# Bing Webmaster Tools 站点所有权验证文件名（须位于站点根 /BingSiteAuth.xml）
BING_SITE_AUTH_FILENAME = "BingSiteAuth.xml"


def _sync_google_site_verification_files(
    portal_root: Path,
    out_root: Path,
) -> List[str]:
    """
    将 Google Search Console 所有权验证 HTML 复制到 dist 根。

    @param portal_root: portal 源目录
    @param out_root: dist 输出根
    @returns: 已复制文件名列表
    @description
      GSC「HTML 文件」验证要求站点根可访问 ``/googleXXXX.html``。
      真相源放在 ``portal/google*.html``，随 static_shell 同步，避免仅手拷 dist 后被 generate 冲掉。
    """
    copied: List[str] = []
    for src in sorted(portal_root.glob("google*.html")):
        if not src.is_file():
            continue
        # 完整注释：仅复制标准验证文件名（google + 十六进制/字母数字 + .html）
        name = src.name
        if not name.startswith("google") or not name.endswith(".html"):
            continue
        shutil.copy2(src, out_root / name)
        copied.append(name)
    return copied


def _sync_bing_site_auth_file(
    portal_root: Path,
    out_root: Path,
) -> List[str]:
    """
    将 Bing Webmaster Tools 验证文件复制到 dist 根。

    @param portal_root: portal 源目录
    @param out_root: dist 输出根
    @returns: 已复制文件名列表（0 或 1 项）
    @description
      Bing「XML 文件」验证要求站点根可访问 ``/BingSiteAuth.xml``。
      真相源放在 ``portal/BingSiteAuth.xml``，随 static_shell 同步。
    """
    src = portal_root / BING_SITE_AUTH_FILENAME
    if not src.is_file():
        return []
    shutil.copy2(src, out_root / BING_SITE_AUTH_FILENAME)
    return [BING_SITE_AUTH_FILENAME]


def sync_static_shell(
    out_root: Path = DEFAULT_OUT_ROOT,
    portal_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    将静态壳（``static/``、404/410、根 ``robots.txt``、搜索引擎验证、跟踪 JS）同步到 dist。

    @param out_root: 生成输出根目录，默认 ``portal/dist``
    @param portal_root: portal 源目录，默认 ``portal/``
    @returns: 同步摘要（路径、复制项、文件数）
    @description
      爬虫只认站点根 ``/robots.txt``；仅放在 ``/static/robots.txt`` 不会被遵守。
      因此在同步 ``static/`` 后，额外把 ``static/robots.txt`` 复制到 dist 根。
      ``tracking.js`` 真相源为 ``portal/static/js/tracking.js``，随 static/ 复制进 dist。
      Google 验证 ``portal/google*.html``、Bing 验证 ``portal/BingSiteAuth.xml`` → dist 根。
    """
    from portal.generator.tracking import ensure_tracking_js, sync_tracking_js_to_dist

    portal_root = portal_root or DEFAULT_PORTAL_ROOT
    out_root.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []

    # 完整注释：缺文件时写入空壳，避免页面引用 404
    tracking_ensure = ensure_tracking_js(portal_root)

    for name in SHELL_FILES:
        src = portal_root / name
        if src.is_file():
            dst = out_root / name
            shutil.copy2(src, dst)
            # 完整注释：404/410 非 Jinja，只挂 tracking.js 引用标签
            if _inject_tracking_script_ref(dst):
                copied.append(f"{name}+tracking")
            else:
                copied.append(name)

    # 完整注释：GSC 所有权验证文件 → 站点根路径
    for name in _sync_google_site_verification_files(portal_root, out_root):
        copied.append(name)

    # 完整注释：Bing Webmaster 所有权验证 → /BingSiteAuth.xml
    for name in _sync_bing_site_auth_file(portal_root, out_root):
        copied.append(name)

    static_src = portal_root / "static"
    static_dst = out_root / "static"
    static_files = 0
    if static_src.is_dir():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
        static_files = sum(1 for _ in static_dst.rglob("*") if _.is_file())
        copied.append("static/")

    # 完整注释：再显式 sync 一次，确保 dist 与真相源一致
    tracking_sync = sync_tracking_js_to_dist(portal_root=portal_root, out_root=out_root)
    if tracking_sync.get("ok"):
        copied.append("static/js/tracking.js")

    # 爬虫入口：/robots.txt（与 /static/robots.txt 内容一致）
    robots_src = static_dst / "robots.txt"
    if not robots_src.is_file():
        robots_src = static_src / "robots.txt"
    robots_root = False
    if robots_src.is_file():
        shutil.copy2(robots_src, out_root / "robots.txt")
        copied.append("robots.txt")
        robots_root = True

    site_js = static_dst / "js" / "site.js"
    tracking_js = static_dst / "js" / "tracking.js"
    return {
        "ok": site_js.is_file() and robots_root and tracking_js.is_file(),
        "out_root": str(out_root),
        "portal_root": str(portal_root),
        "copied": copied,
        "static_file_count": static_files,
        "site_js": str(site_js),
        "tracking_js": str(tracking_js),
        "tracking_ensure": tracking_ensure,
        "tracking_sync": tracking_sync,
        "robots_root": robots_root,
    }


def _inject_tracking_script_ref(html_path: Path) -> bool:
    """
    向非 Jinja 壳页（404/410）的 ``</body>`` 前插入 tracking.js 引用。

    @param html_path: dist 下的 HTML 文件路径
    @returns: True 表示已写入引用；False 表示已存在而跳过
    """
    from portal.generator.tracking import render_tracking_script_tag

    text = html_path.read_text(encoding="utf-8")
    # 完整注释：已注入则跳过，避免 generate all 重复叠加
    if "<!-- rm-tracking -->" in text or "/static/js/tracking.js" in text:
        return False

    snippet = render_tracking_script_tag()
    if "</body>" not in text:
        return False

    html_path.write_text(text.replace("</body>", snippet + "</body>", 1), encoding="utf-8")
    return True
