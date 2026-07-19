# -*- coding: utf-8 -*-
"""
Ops 本地 HTTP 服务 — 四段式运营控制台。

@module workflow.ops.server
@description
  仅绑定 127.0.0.1。提供 JSON API + 单页 UI（含配置加载/修改/热加载）。
  CLI: python -m workflow.run ops serve [--port 8090]
"""

from __future__ import annotations

import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from workflow.config import PROJECT_ROOT
from workflow.ops import DEFAULT_OPS_PORT
from workflow.ops import actions
from workflow.ops import config_service
from workflow.ops import source_service
from workflow.ops.track_store import (
    ensure_tables,
    get_active_batch_id,
    list_batches,
    load_active_batch,
    load_batch,
    set_active_batch_id,
    summarize_batch,
)
from workflow.ops.workspace import WORKSPACE

# 静态资源目录
OPS_STATIC_DIR: Path = Path(__file__).resolve().parent / "static"


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    """写入 JSON 响应。"""
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    """解析 POST JSON body。"""
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _handle_api(method: str, path: str, body: Dict[str, Any], query: Dict[str, list]) -> Tuple[int, Any]:
    """
    路由 API。

    @param method: GET|POST
    @param path: 如 /api/state
    @param body: POST JSON
    @param query: querystring
    @returns: (status, payload)
    """
    if path == "/api/state" and method == "GET":
        batch = load_active_batch()
        return 200, {
            "ok": True,
            "workspace": WORKSPACE.snapshot(),
            "batch": batch,
            "summary": summarize_batch(batch) if batch else None,
            "batches": list_batches(),
            "source_logic": source_service.describe_source_logic(),
            "active_batch_id": get_active_batch_id(),
        }

    if path == "/api/source/logic" and method == "GET":
        return 200, {"ok": True, **source_service.describe_source_logic()}

    if path == "/api/source/files" and method == "GET":
        return 200, {"ok": True, "files": source_service.list_candidate_slot_files()}

    if path == "/api/source/load" and method == "POST":
        rel = body.get("path") or body.get("abs_path")
        if not rel:
            return 400, {"ok": False, "error": "缺少 path"}
        path_obj = Path(rel)
        if not path_obj.is_absolute():
            path_obj = PROJECT_ROOT / rel
        result = source_service.load_slots_json(path_obj)
        if not result.get("ok"):
            return 400, result
        snap = WORKSPACE.set_source(result)
        return 200, {"ok": True, "loaded": result.get("count"), "workspace": snap, "tier_counts": result.get("tier_counts")}

    if path == "/api/source/build-tmdb" and method == "POST":
        result = source_service.build_from_tmdb_export(
            total=int(body.get("total") or 20),
            movie_count=body.get("movies"),
            tv_count=body.get("tv"),
            download=bool(body.get("download", True)),
            force_download=bool(body.get("force_download", False)),
            export_date=body.get("export_date"),
        )
        if not result.get("ok"):
            return 400, result
        snap = WORKSPACE.set_source(result)
        return 200, {"ok": True, "result": {k: v for k, v in result.items() if k != "slots"}, "workspace": snap}

    if path == "/api/source/export/ensure" and method == "POST":
        # 默认异步：全量下载 + 增量入库；前端轮询 /api/source/export/progress
        async_mode = bool(body.get("async", True))
        daily = bool(body.get("daily", False))
        if async_mode:
            result = source_service.start_export_index_load(
                download=bool(body.get("download", True)),
                force_download=bool(body.get("force_download", False)),
                force_reload=bool(body.get("force_reload", False)),
                export_date=body.get("export_date"),
                daily=daily,
            )
            return 200, result
        result = source_service.ensure_export_index(
            download=bool(body.get("download", True)),
            force_download=bool(body.get("force_download", False)),
            force_reload=bool(body.get("force_reload", False)),
            export_date=body.get("export_date"),
            daily=daily,
        )
        return 200, result

    if path == "/api/source/export/progress" and method == "GET":
        return 200, source_service.get_export_load_progress()

    if path == "/api/source/export/search" and method == "POST":
        result = source_service.search_tmdb_export(
            q=body.get("q"),
            media_types=body.get("media_types"),
            pop_min=body.get("pop_min"),
            pop_max=body.get("pop_max"),
            exclude_adult=bool(body.get("exclude_adult", True)),
            exclude_video=bool(body.get("exclude_video", True)),
            limit=int(body.get("limit") or 50),
            offset=int(body.get("offset") or 0),
            download=bool(body.get("download", False)),
            export_date=body.get("export_date"),
        )
        return 200, result

    if path == "/api/source/export/add" and method == "POST":
        built = source_service.slots_from_manual_selections(body.get("selections") or [])
        if not built.get("ok"):
            return 400, built
        mode = str(body.get("mode") or "append")
        if mode not in ("append", "replace"):
            return 400, {"ok": False, "error": "mode 须为 append 或 replace"}
        snap = WORKSPACE.add_slots(
            built["slots"],
            mode=mode,
            source_meta={
                "kind": built.get("kind"),
                "meta": built.get("meta") or {},
                "tier_counts": built.get("tier_counts") or {},
            },
        )
        return 200, {
            "ok": True,
            "mode": mode,
            "added": built.get("count"),
            "slots": built.get("slots"),
            "workspace": snap.get("workspace"),
        }

    # TV 季列表：crawler_tmdb.tv_details → 本地 data/tmdb_tv
    if path == "/api/source/tv/seasons" and method == "POST":
        tid = body.get("tmdb_id")
        if tid is None:
            return 400, {"ok": False, "error": "缺少 tmdb_id"}
        result = source_service.fetch_tv_seasons(
            int(tid),
            force_refresh=bool(body.get("force_refresh", False)),
            include_specials=bool(body.get("include_specials", False)),
            language=body.get("language"),
        )
        status = 200 if result.get("ok") else 400
        return status, result

    # TV 某季分集：crawler_tmdb.tv_season_details → 本地 data/tmdb_tv
    if path == "/api/source/tv/episodes" and method == "POST":
        tid = body.get("tmdb_id")
        season = body.get("season")
        if tid is None or season is None:
            return 400, {"ok": False, "error": "缺少 tmdb_id 或 season"}
        result = source_service.fetch_tv_episodes(
            int(tid),
            int(season),
            force_refresh=bool(body.get("force_refresh", False)),
            language=body.get("language"),
        )
        status = 200 if result.get("ok") else 400
        return status, result

    # 一次拉齐：季列表 + 可选某季分集
    if path == "/api/source/tv/catalog" and method == "POST":
        tid = body.get("tmdb_id")
        if tid is None:
            return 400, {"ok": False, "error": "缺少 tmdb_id"}
        season = body.get("season")
        result = source_service.fetch_tv_catalog(
            int(tid),
            season=int(season) if season is not None else None,
            force_refresh=bool(body.get("force_refresh", False)),
            include_specials=bool(body.get("include_specials", False)),
            language=body.get("language"),
        )
        status = 200 if result.get("ok") else 400
        return status, result

    if path == "/api/filter" and method == "POST":
        if not WORKSPACE.candidates:
            return 400, {"ok": False, "error": "请先在「清单从哪来」加载或生成清单"}
        result = WORKSPACE.apply_filter(
            media_types=body.get("media_types"),
            tiers=body.get("tiers"),
            q=body.get("q"),
            pop_min=body.get("pop_min"),
            pop_max=body.get("pop_max"),
            exclude_published=bool(body.get("exclude_published")),
            exclude_failed=bool(body.get("exclude_failed")),
            only_failed=bool(body.get("only_failed")),
            selected_page_ids=body.get("selected_page_ids"),
        )
        return 200, result

    if path == "/api/track/import" and method == "POST":
        result = WORKSPACE.import_to_track(selected_page_ids=body.get("selected_page_ids"))
        status = 200 if result.get("ok") else 400
        return status, result

    if path == "/api/track/activate" and method == "POST":
        batch_id = body.get("batch_id")
        if not batch_id:
            return 400, {"ok": False, "error": "缺少 batch_id"}
        batch = load_batch(str(batch_id))
        if not batch:
            return 404, {"ok": False, "error": "批次不存在"}
        set_active_batch_id(str(batch_id))
        return 200, {"ok": True, "batch": batch, "summary": summarize_batch(batch)}

    if path == "/api/track/refresh-gates" and method == "POST":
        return 200, actions.refresh_gates(body.get("batch_id"))

    if path == "/api/actions/pipeline" and method == "POST":
        return 200, actions.run_pipeline(
            batch_id=body.get("batch_id"),
            page_ids=body.get("page_ids"),
            fetch=bool(body.get("fetch", True)),
            skip_existing=bool(body.get("skip_existing", True)),
            mode=str(body.get("mode") or "live"),
        )

    if path == "/api/actions/generate" and method == "POST":
        return 200, actions.run_generate(
            batch_id=body.get("batch_id"),
            page_ids=body.get("page_ids"),
            generate_all=bool(body.get("generate_all", False)),
        )

    if path == "/api/actions/speedtest" and method == "POST":
        return 200, actions.run_speedtest(
            batch_id=body.get("batch_id"),
            page_ids=body.get("page_ids"),
        )

    if path == "/api/actions/seo" and method == "POST":
        return 200, actions.run_seo_c2(batch_id=body.get("batch_id"))

    if path == "/api/actions/deploy" and method == "POST":
        return 200, actions.run_deploy(
            batch_id=body.get("batch_id"),
            prepare_only=bool(body.get("prepare_only", True)),
        )

    # ── 配置：加载 / 修改 / 热加载（.env + accounts.local.json）────────
    if path == "/api/config" and method == "GET":
        return 200, config_service.get_config_bundle()

    if path == "/api/config/env" and method == "POST":
        # body.values: 表单键值；或 body.raw: 全文覆盖
        if body.get("raw") is not None:
            result = config_service.save_env_raw(
                str(body.get("raw") or ""),
                reload=bool(body.get("reload", True)),
            )
        else:
            result = config_service.save_env_values(
                body.get("values") or {},
                reload=bool(body.get("reload", True)),
            )
        status = 200 if result.get("ok") else 400
        if result.get("ok"):
            result["config"] = config_service.get_config_bundle()
        return status, result

    if path == "/api/config/accounts" and method == "POST":
        if "data" not in body:
            return 400, {"ok": False, "error": "缺少 data（accounts JSON 对象）"}
        result = config_service.save_accounts_data(
            body.get("data"),
            reload=bool(body.get("reload", True)),
        )
        status = 200 if result.get("ok") else 400
        if result.get("ok"):
            result["config"] = config_service.get_config_bundle()
        return status, result

    if path == "/api/config/reload" and method == "POST":
        runtime = config_service.apply_runtime_reload()
        return 200, {
            "ok": True,
            "runtime": runtime,
            "config": config_service.get_config_bundle(),
        }

    if path == "/api/config/init" and method == "POST":
        # 从模板复制缺失的 .env / accounts.local.json
        which = str(body.get("which") or "both")
        out: Dict[str, Any] = {"ok": True, "env": None, "accounts": None}
        if which in ("both", "env"):
            out["env"] = config_service.ensure_env_file_from_example()
            if not out["env"].get("ok"):
                return 400, {"ok": False, "error": out["env"].get("error"), **out}
        if which in ("both", "accounts"):
            out["accounts"] = config_service.ensure_accounts_local_from_example()
            if not out["accounts"].get("ok"):
                return 400, {"ok": False, "error": out["accounts"].get("error"), **out}
        out["config"] = config_service.get_config_bundle()
        return 200, out

    return 404, {"ok": False, "error": f"未知 API: {method} {path}"}


class OpsHandler(BaseHTTPRequestHandler):
    """
    Ops HTTP 处理器：静态页 + /api/*。

    @description 仅供 localhost 使用。
    """

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        """简化访问日志。"""
        print(f"[ops] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:  # noqa: N802
        """处理 GET。"""
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            try:
                status, payload = _handle_api("GET", path, {}, parse_qs(parsed.query))
                _json_response(self, status, payload)
            except Exception as exc:  # noqa: BLE001
                _json_response(
                    self,
                    500,
                    {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-800:]},
                )
            return

        if path in ("/", "/index.html"):
            self._serve_file(OPS_STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        # /static/ops.css → ops/static/
        rel = path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/") :]
        file_path = OPS_STATIC_DIR / rel
        if file_path.is_file() and OPS_STATIC_DIR in file_path.resolve().parents:
            ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self._serve_file(file_path, ctype)
            return

        _json_response(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        """处理 POST API。"""
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            _json_response(self, 404, {"ok": False, "error": "not found"})
            return
        try:
            body = _read_json_body(self)
            status, payload = _handle_api("POST", path, body, parse_qs(parsed.query))
            _json_response(self, status, payload)
        except Exception as exc:  # noqa: BLE001
            _json_response(
                self,
                500,
                {"ok": False, "error": str(exc), "trace": traceback.format_exc()[-800:]},
            )

    def _serve_file(self, path: Path, content_type: str) -> None:
        """输出静态文件。"""
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def run_ops_server(*, host: str = "127.0.0.1", port: int = DEFAULT_OPS_PORT) -> None:
    """
    启动 Ops 控制台 HTTP 服务。

    @param host: 绑定地址（默认仅本机）
    @param port: 端口
    """
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Ops 控制台仅允许绑定本机（127.0.0.1），禁止公网暴露")

    # 启动时确保 Ops / TMDB 导出相关表存在
    try:
        from workflow.ops import tmdb_export_store
        from workflow.ops import tmdb_tv_store

        ensured = ensure_tables()
        tmdb_ok = tmdb_export_store.ensure_tables()
        tv_ok = tmdb_tv_store.ensure_tables()
        print(
            f"[ops] MySQL 就绪: ops_track_* {ensured} · tmdb_export_* {tmdb_ok} · tmdb_tv_* {tv_ok}"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ops] 警告: 无法初始化 Ops/TMDB 表（请检查 MySQL / .env）: {exc}")

    httpd = ThreadingHTTPServer((host, port), OpsHandler)
    print(f"[ops] ReleaseMatch Ops Console → http://{host}:{port}/")
    print("[ops] 五段：清单 → 筛选 → 生成 → 上线 → 配置（.env / accounts 可热加载）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ops] stopped")
    finally:
        httpd.server_close()


def main(argv: Optional[list] = None) -> int:
    """CLI 入口（亦可 python -m workflow.ops.server）。"""
    import argparse

    parser = argparse.ArgumentParser(description="ReleaseMatch Ops Console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_OPS_PORT)
    args = parser.parse_args(argv)
    run_ops_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
