#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面跟踪 JS：以 ``portal/static/js/tracking.js`` 为真相源。

@module portal.generator.tracking
@description
  每个页面只引用 ``/static/js/tracking.js``（见 ``base.html``）。
  直接手改该文件，或经 Ops 读写；``sync_static_shell`` / Ops「同步到 dist」
  将其复制到 ``portal/dist/static/js/tracking.js``，无需重烘全部 HTML。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

# 本模块所在目录（portal/generator/）
_MODULE_DIR: Path = Path(__file__).resolve().parent

# portal 根目录（含 static/、dist/）
_PORTAL_ROOT: Path = _MODULE_DIR.parent

# 站点内跟踪脚本相对 URL（稳定路径，便于只更新 JS）
TRACKING_JS_HREF: str = "/static/js/tracking.js"

# 源码树中的跟踪脚本（真相源，可手改 / Ops 编辑）
TRACKING_JS_STATIC: Path = _PORTAL_ROOT / "static" / "js" / "tracking.js"

# dist 中的跟踪脚本（线上实际被页面加载）
TRACKING_JS_DIST: Path = _PORTAL_ROOT / "dist" / "static" / "js" / "tracking.js"

# 缺文件时写入的空壳模板（完整注释便于手改）
_DEFAULT_TRACKING_JS: str = """\
/* ReleaseMatch tracking.js
 * 页面引用 /static/js/tracking.js；改此文件后 sync 到 dist（或 Ops「保存并同步」）。
 * 更新本文件即可，无需重烘全部 HTML。
 */
(function () {
  "use strict";
  // 在此填写跟踪代码。可用 Ops「生成 GA4 模板」预填，或手写其它分析脚本。
})();
"""


def tracking_js_static_path(portal_root: Optional[Path] = None) -> Path:
    """
    真相源 tracking.js 路径。

    @param portal_root: portal 根；默认本仓库 portal/
    @returns: ``…/static/js/tracking.js``
    """
    root = Path(portal_root) if portal_root is not None else _PORTAL_ROOT
    return root / "static" / "js" / "tracking.js"


def tracking_js_dist_path(out_root: Optional[Path] = None) -> Path:
    """
    dist 内 tracking.js 路径。

    @param out_root: dist 根；默认 ``portal/dist``
    @returns: ``…/static/js/tracking.js``
    """
    root = Path(out_root) if out_root is not None else (_PORTAL_ROOT / "dist")
    return root / "static" / "js" / "tracking.js"


def ensure_tracking_js(portal_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    若真相源不存在则写入空壳模板。

    @param portal_root: portal 根
    @returns: {ok, path, created, bytes}
    """
    path = tracking_js_static_path(portal_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if not path.is_file():
        path.write_text(_DEFAULT_TRACKING_JS, encoding="utf-8")
        created = True
    text = path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "path": str(path),
        "created": created,
        "bytes": len(text.encode("utf-8")),
    }


def read_tracking_js(portal_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    读取真相源 tracking.js（不存在则先 ensure）。

    @param portal_root: portal 根
    @returns: {ok, path, content, bytes, dist_path, dist_exists, href}
    """
    ensure = ensure_tracking_js(portal_root)
    path = Path(ensure["path"])
    content = path.read_text(encoding="utf-8")
    dist = tracking_js_dist_path(
        (Path(portal_root) / "dist") if portal_root is not None else None
    )
    return {
        "ok": True,
        "path": str(path),
        "content": content,
        "bytes": len(content.encode("utf-8")),
        "dist_path": str(dist),
        "dist_exists": dist.is_file(),
        "href": TRACKING_JS_HREF,
        "created": bool(ensure.get("created")),
    }


def write_tracking_js(
    content: str,
    *,
    portal_root: Optional[Path] = None,
    sync_dist: bool = True,
    out_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    写入真相源 tracking.js，可选同步到 dist。

    @param content: JS 全文
    @param portal_root: portal 根
    @param sync_dist: True 时复制到 dist/static/js/tracking.js
    @param out_root: dist 根（仅 sync_dist 时有用）
    @returns: {ok, path, bytes, synced, dist_path?}
    """
    path = tracking_js_static_path(portal_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content if content.endswith("\n") else content + "\n"
    path.write_text(text, encoding="utf-8")
    result: Dict[str, Any] = {
        "ok": True,
        "path": str(path),
        "bytes": len(text.encode("utf-8")),
        "synced": False,
    }
    if sync_dist:
        sync = sync_tracking_js_to_dist(portal_root=portal_root, out_root=out_root)
        result["synced"] = bool(sync.get("ok"))
        result["dist_path"] = sync.get("dist_path")
        if not sync.get("ok"):
            result["ok"] = False
            result["error"] = sync.get("error")
    return result


def sync_tracking_js_to_dist(
    *,
    portal_root: Optional[Path] = None,
    out_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    将真相源 tracking.js 复制到 dist（不重烘 HTML）。

    @param portal_root: portal 根
    @param out_root: dist 根
    @returns: {ok, path, dist_path, bytes}
    """
    ensure_tracking_js(portal_root)
    src = tracking_js_static_path(portal_root)
    dist_root = Path(out_root) if out_root is not None else (
        Path(portal_root) / "dist" if portal_root is not None else _PORTAL_ROOT / "dist"
    )
    dest = tracking_js_dist_path(dist_root)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    except OSError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "path": str(src),
            "dist_path": str(dest),
        }
    return {
        "ok": True,
        "path": str(src),
        "dist_path": str(dest),
        "bytes": dest.stat().st_size,
    }


def build_ga4_tracking_js(measurement_id: str) -> str:
    """
    生成含 GA4 加载逻辑的 tracking.js 全文（供 Ops「生成」按钮）。

    @param measurement_id: 形如 G-XXXXXXXX
    @returns: 完整 JS 源码
    """
    mid = str(measurement_id or "").strip()
    if not mid:
        raise ValueError("measurement_id 不能为空")
    mid_js = json.dumps(mid)
    return (
        "/* ReleaseMatch tracking.js — GA4\n"
        " * 页面引用 /static/js/tracking.js；改此文件后 sync 到 dist 即可。\n"
        " */\n"
        "(function () {\n"
        '  "use strict";\n'
        f"  var MEASUREMENT_ID = {mid_js};\n"
        "  window.dataLayer = window.dataLayer || [];\n"
        "  function gtag() { dataLayer.push(arguments); }\n"
        "  window.gtag = gtag;\n"
        "  gtag('js', new Date());\n"
        "  gtag('config', MEASUREMENT_ID);\n"
        "  var s = document.createElement('script');\n"
        "  s.async = true;\n"
        "  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + MEASUREMENT_ID;\n"
        "  document.head.appendChild(s);\n"
        "})();\n"
    )


def build_clarity_tracking_js(project_id: str) -> str:
    """
    生成 Microsoft Clarity 加载逻辑的 tracking.js 全文。

    @param project_id: Clarity 项目 ID（如 xsjixeey9o）
    @returns: 完整 JS 源码（无 HTML ``<script>`` 外壳）
    @description
      官网粘贴片段是 HTML；tracking.js 只能是纯 JS，故去掉外层 script 标签，
      保留官方 IIFE 本体。
    """
    pid = str(project_id or "").strip()
    if not pid:
        raise ValueError("clarity project_id 不能为空")
    # 完整注释：仅允许常见 ID 字符，防止注入破坏 JS 字符串
    if not all(ch.isalnum() or ch in "-_" for ch in pid):
        raise ValueError("clarity project_id 含非法字符")
    pid_js = json.dumps(pid)
    return (
        "/* ReleaseMatch tracking.js — Microsoft Clarity\n"
        " * 页面引用 /static/js/tracking.js；勿在此文件写 <script> HTML 标签。\n"
        " * 改完后 Ops「保存并同步到 dist」即可，无需重烘全部 HTML。\n"
        " */\n"
        "(function (c, l, a, r, i, t, y) {\n"
        "  c[a] =\n"
        "    c[a] ||\n"
        "    function () {\n"
        "      (c[a].q = c[a].q || []).push(arguments);\n"
        "    };\n"
        "  t = l.createElement(r);\n"
        "  t.async = 1;\n"
        "  t.src = 'https://www.clarity.ms/tag/' + i;\n"
        "  y = l.getElementsByTagName(r)[0];\n"
        "  y.parentNode.insertBefore(t, y);\n"
        "})(window, document, 'clarity', 'script', "
        + pid_js
        + ");\n"
    )


def build_tracking_js_for_provider(
    provider: str,
    *,
    measurement_id: str = "",
    project_id: str = "",
) -> str:
    """
    按 provider 生成 tracking.js 源码。

    @param provider: ga4 | clarity
    @param measurement_id: GA4 Measurement ID
    @param project_id: Clarity 项目 ID
    @returns: JS 全文
    """
    name = str(provider or "").strip().lower()
    if name == "ga4":
        return build_ga4_tracking_js(measurement_id)
    if name == "clarity":
        return build_clarity_tracking_js(project_id or measurement_id)
    raise ValueError(f"不支持的 provider: {provider}（可用 ga4 / clarity）")


def build_tracking_context() -> Dict[str, Any]:
    """
    构建模板所需的跟踪引用变量（页面只挂 script src）。

    @returns: {tracking_js_href}
    """
    return {
        # 完整注释：稳定 URL；逻辑在 tracking.js，更新 JS 无需改 HTML
        "tracking_js_href": TRACKING_JS_HREF,
    }


def render_tracking_script_tag() -> str:
    """
    渲染单一 ``<script src=…>`` 标签（供 404/410 等非 Jinja 页注入）。

    @returns: HTML 字符串
    """
    return f'<!-- rm-tracking -->\n<script src="{TRACKING_JS_HREF}" defer></script>\n'
