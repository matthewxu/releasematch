#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态资源壳同步 — 将 portal/static 等复制到 portal/dist。

@module portal.generator.static_shell
@description
  生成的 HTML 引用 ``/static/js/site.js`` 等绝对路径。
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

# 需要从 portal 根复制到 dist 根的单文件列表
SHELL_FILES = ("404.html", "410.html")


def sync_static_shell(
    out_root: Path = DEFAULT_OUT_ROOT,
    portal_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    将静态壳（``static/``、404/410）同步到 dist，供纯静态预览与部署。

    @param out_root: 生成输出根目录，默认 ``portal/dist``
    @param portal_root: portal 源目录，默认 ``portal/``
    @returns: 同步摘要（路径、复制项、文件数）
    """
    portal_root = portal_root or DEFAULT_PORTAL_ROOT
    out_root.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []

    for name in SHELL_FILES:
        src = portal_root / name
        if src.is_file():
            dst = out_root / name
            shutil.copy2(src, dst)
            copied.append(name)

    static_src = portal_root / "static"
    static_dst = out_root / "static"
    static_files = 0
    if static_src.is_dir():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
        static_files = sum(1 for _ in static_dst.rglob("*") if _.is_file())
        copied.append("static/")

    site_js = static_dst / "js" / "site.js"
    return {
        "ok": site_js.is_file(),
        "out_root": str(out_root),
        "portal_root": str(portal_root),
        "copied": copied,
        "static_file_count": static_files,
        "site_js": str(site_js),
    }
