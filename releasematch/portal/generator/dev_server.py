#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地开发服务器 — 静态资源 + MySQL 动态渲染。

@module portal.generator.dev_server
@description
  启动 HTTP 服务：
    - /static/、404/410 等走 portal/ 静态文件
    - /trust/* 优先读 portal/dist/trust/（generate all 产出），否则 Jinja 动态渲染
    - 首页与槽位路径（如 /breaking-bad/s4e6/）实时读 MySQL 渲染 Jinja2
"""

from __future__ import annotations

import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from workflow.config import PROJECT_ROOT, SHOW_IG_DEBUG
from workflow.storage.mysql_store import MySQLStore

from portal.generator.render import render_home_page, render_page_context

# portal 根目录（静态资源）
PORTAL_ROOT = PROJECT_ROOT / "portal"

# generate all 产出目录（Trust 页等）
DIST_ROOT = PROJECT_ROOT / "portal" / "dist"

# DB 动态路由 slug 模式（排除 static、trust 等）
_DB_ROUTE_RE = re.compile(r"^/([^/]+)(/s\d+e\d+)?/?$")


class PortalDevHandler(BaseHTTPRequestHandler):
    """
    HTTP 请求处理器：优先 DB 渲染，其次静态文件。

    @var portal_root: portal 目录
    @var store: MySQLStore 实例
    @var site_origin: 用于 canonical 的 origin
    """

    portal_root: Path = PORTAL_ROOT
    dist_root: Path = DIST_ROOT
    store: Optional[MySQLStore] = None
    site_origin: str = "http://127.0.0.1:8080"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        """简化访问日志。"""
        print(f"[portal] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:  # noqa: N802
        """处理 GET：DB 页面或静态文件。"""
        path = unquote(self.path.split("?", 1)[0])
        if path == "/":
            path = "/index.html"

        # 1. 尝试 MySQL 动态渲染（剧集/电影 slug 路径）
        if self._try_render_db_page(path):
            return

        # 2. Trust 说明页：dist 优先，否则 Jinja 动态渲染
        if self._try_serve_trust_page(path):
            return

        # 3. 静态文件回退
        self._serve_static(path)

    def _try_render_db_page(self, path: str) -> bool:
        """
        尝试从 MySQL 渲染页面。

        @param path: URL 路径
        @returns: 是否已响应
        """
        if path.startswith("/static/") or path.startswith("/trust/"):
            return False

        normalized = path.rstrip("/")
        if normalized in ("", "/index.html"):
            return self._try_render_home()

        if normalized.endswith(".html"):
            return False

        store = self.store or MySQLStore()
        url_path = normalized if normalized.startswith("/") else f"/{normalized}"
        bundle = store.load_page_for_url(url_path)
        if not bundle:
            return False

        origin = f"http://{self.headers.get('Host', '127.0.0.1:8080')}"
        html = render_page_context(
            bundle,
            site_origin=origin,
            show_ig_debug=SHOW_IG_DEBUG,
        )
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-RM-Source", "mysql")
        self.send_header("X-RM-Page-Id", bundle.get("page_id", ""))
        self.end_headers()
        self.wfile.write(body)
        return True

    def _try_render_home(self) -> bool:
        """
        渲染 DB 驱动的首页目录。

        @returns: 是否已响应
        """
        store = self.store or MySQLStore()
        origin = f"http://{self.headers.get('Host', '127.0.0.1:8080')}"
        html = render_home_page(store, site_origin=origin, show_ig_debug=SHOW_IG_DEBUG)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-RM-Source", "mysql-home")
        self.end_headers()
        self.wfile.write(body)
        return True

    def _trust_slug_from_path(self, path: str) -> Optional[str]:
        """
        从 URL 解析 Trust slug。

        @param path: 如 /trust/speed-and-grab/ 或 /trust/speed-and-grab
        @returns: slug 或 None
        """
        normalized = path.rstrip("/")
        parts = [p for p in normalized.split("/") if p]
        if len(parts) != 2 or parts[0] != "trust":
            return None
        return parts[1]

    def _try_serve_trust_page(self, path: str) -> bool:
        """
        提供 Trust 页：先读 dist，再动态渲染 TRUST_PAGES。

        @param path: URL 路径
        @returns: 是否已响应
        """
        slug = self._trust_slug_from_path(path)
        if not slug:
            return False

        dist_file = self.dist_root / "trust" / slug / "index.html"
        if dist_file.is_file():
            body = dist_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-RM-Source", "dist-trust")
            self.end_headers()
            self.wfile.write(body)
            return True

        from portal.generator.render import render_html
        from portal.generator.render_trust import _trust_page_context
        from portal.generator.trust_content import TRUST_PAGES

        page_def = next((p for p in TRUST_PAGES if str(p.get("slug")) == slug), None)
        if not page_def:
            return False

        origin = f"http://{self.headers.get('Host', '127.0.0.1:8080')}"
        ctx = _trust_page_context(page_def, origin)
        html = render_html("trust/page.html", ctx)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-RM-Source", "trust-render")
        self.end_headers()
        self.wfile.write(body)
        return True

    def _serve_static(self, path: str) -> None:
        """
        从 portal/ 目录提供静态文件。

        @param path: URL 路径
        @returns: None
        """
        rel = path.lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel = f"{rel}index.html".lstrip("/")

        file_path = (self.portal_root / rel).resolve()
        try:
            file_path.relative_to(self.portal_root.resolve())
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if not file_path.is_file():
            # 目录 index.html
            if file_path.is_dir() and (file_path / "index.html").is_file():
                file_path = file_path / "index.html"
            else:
                self.send_error(404, "Not Found")
                return

        content = file_path.read_bytes()
        mime, _ = mimetypes.guess_type(str(file_path))
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_static_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """
    纯静态预览：先同步 static 壳，再以 portal/dist 为根目录启动 http.server。

    @param host: 监听地址
    @param port: 端口
    @returns: None
    """
    import os
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from portal.generator.static_shell import sync_static_shell

    result = sync_static_shell()
    if not result.get("ok"):
        print(f"[static] 警告：未找到 site.js（{result.get('site_js')}）")

    dist = DIST_ROOT.resolve()
    os.chdir(dist)
    server = ThreadingHTTPServer((host, port), SimpleHTTPRequestHandler)
    print(f"ReleaseMatch 静态预览：http://{host}:{port}/")
    print(f"  根目录：{dist}")
    print("  双语：页面内联 i18n 引导（不依赖 site.js）")
    print(f"  static 壳：{result.get('static_file_count', 0)} 个文件")
    print("  Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.shutdown()


def run_dev_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """
    启动开发服务器（阻塞）。

    @param host: 监听地址
    @param port: 端口
    @returns: None
    """
    PortalDevHandler.store = MySQLStore()
    PortalDevHandler.site_origin = f"http://{host}:{port}"
    server = ThreadingHTTPServer((host, port), PortalDevHandler)
    print(f"ReleaseMatch Portal 开发服：http://{host}:{port}/")
    print("  DB 页面：/  /breaking-bad/s4e6/  /inception-2010/  …")
    print("  Trust 页：/trust/speed-and-grab/  …（dist 优先，否则动态渲染）")
    print("  静态资源：/static/  /404.html")
    print(f"  IG debug 面板：{'开启' if SHOW_IG_DEBUG else '关闭'}（RM_SHOW_IG_DEBUG）")
    print("  Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.shutdown()
