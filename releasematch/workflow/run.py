#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch 工作流总控 CLI。

@module workflow.run
@description
  替代原 tmdbpy/workflow/run.py Step 4c 的独立入口。

  子命令：
    status    — 模块、存储后端、MySQL 连通性
    db init   — 建库 + 初始化 MySQL 表结构
    db create — 仅 CREATE DATABASE（init 已包含，一般无需单独调用）
    db seed   — 导入演示种子数据
    db status — Release MySQL 表状态与行数
    run 4c    — torrent_sources 单槽测试
    run recommended — Recommended 评分 Demo
    pipeline slot — 单槽 pipeline（demo → MySQL）
    query page — 从 MySQL 读取 Jinja2 上下文
    generate page — MySQL → 静态 HTML（portal/dist）
    generate all  — 批量生成已发布页
    serve         — 本地开发服（DB 动态渲染 + 静态资源）
    ops serve      — 本地运营控制台（清单→筛选→生成→上线，仅 127.0.0.1）
    ops tmdb-sync  — 每天全量下载 TMDB Daily Export → MySQL 增量入库（cron）

  示例：
    cd releasematch && cp config.env.example .env  # 按需编辑
    cd releasematch && python -m workflow.run db init
    cd releasematch && python -m workflow.run db seed
    cd releasematch && python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6
    cd releasematch && python -m workflow.run query page --page-id tv:1396:s04e06
    cd releasematch && python -m workflow.run ops tmdb-sync
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# 确保 releasematch 根目录在 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.config import (  # noqa: E402
    D1_DATABASE_NAME,
    EZTV_BASE_URL,
    JACKETT_BASE_URL,
    PROJECT_ROOT,
    RELEASE_MYSQL_DB,
    RELEASE_MYSQL_HOST,
    SITE_ORIGIN,
    STORAGE_BACKEND,
    TMDB_DATA_MODE,
    YTS_BASE_URL,
    ensure_project_dirs,
    release_mysql_configured,
)


def cmd_status(_args: argparse.Namespace) -> int:
    """
    打印 ReleaseMatch 工作流状态摘要。

    @param _args: argparse 命名空间（未使用）
    @returns: 进程退出码 0
    """
    ensure_project_dirs()
    db_detail = None
    if STORAGE_BACKEND == "mysql" and release_mysql_configured():
        from workflow.storage.mysql_store import MySQLStore

        store = MySQLStore()
        db_detail = store.ping()
        if db_detail.get("ok"):
            db_detail["row_counts"] = store.count_rows()

    summary = {
        "project_root": str(PROJECT_ROOT),
        "site_origin": SITE_ORIGIN,
        "storage_backend": STORAGE_BACKEND,
        "tmdb_data_mode": TMDB_DATA_MODE,
        "release_mysql": {
            "host": RELEASE_MYSQL_HOST,
            "database": RELEASE_MYSQL_DB,
            "configured": release_mysql_configured(),
        },
        "d1": {
            "database_name": D1_DATABASE_NAME,
            "note": "生产部署；本地测试使用 mysql",
        },
        "endpoints": {
            "jackett": JACKETT_BASE_URL,
            "eztv": EZTV_BASE_URL,
            "yts": YTS_BASE_URL,
        },
        "modules": {
            "torrent_sources": "mvp",
            "recommended": "active",
            "metadata": "scaffold",
            "priority": "scaffold",
            "storage_mysql": "active" if STORAGE_BACKEND == "mysql" else "standby",
            "storage_d1_sync": "planned",
            "portal_generator": "scaffold",
        },
        "database": db_detail,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_db_create(_args: argparse.Namespace) -> int:
    """
    仅创建 Release MySQL 数据库（CREATE DATABASE IF NOT EXISTS）。

    @param _args: argparse 命名空间（未使用）
    @returns: 进程退出码
    """
    from workflow.storage.mysql_store import MySQLStore

    store = MySQLStore()
    result = store.ensure_database()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_db_init(args: argparse.Namespace) -> int:
    """
    建库并初始化 MySQL 表结构。

    @param args: 含 --seed、--skip-create-db
    @returns: 进程退出码
    """
    from workflow.storage.mysql_store import MySQLStore

    store = MySQLStore()
    result = store.init_schema(create_database=not args.skip_create_db)
    print(json.dumps({"step": "db_init", **result}, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        return 1
    if args.seed:
        return cmd_db_seed(args)
    return 0


def cmd_db_seed(_args: argparse.Namespace) -> int:
    """
    导入 MySQL 演示种子数据。

    @param _args: argparse 命名空间（未使用）
    @returns: 进程退出码
    """
    from workflow.storage.mysql_store import MySQLStore

    store = MySQLStore()
    result = store.seed_demo()
    print(json.dumps({"step": "seed_demo", **result}, ensure_ascii=False, indent=2))
    if result.get("ok"):
        print(json.dumps({"row_counts": store.count_rows()}, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_db_status(_args: argparse.Namespace) -> int:
    """
    检查 Release MySQL 连通性与行数。

    @param _args: argparse 命名空间（未使用）
    @returns: 进程退出码
    """
    from workflow.storage.mysql_store import MySQLStore

    store = MySQLStore()
    ping = store.ping()
    out = {"ping": ping}
    if ping.get("ok"):
        out["row_counts"] = store.count_rows()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ping.get("ok") else 1


def cmd_run(args: argparse.Namespace) -> int:
    """
    执行指定工作流步骤（4c / recommended）。

    @param args: 含 step、tmdb、season、episode 等参数
    @returns: 进程退出码
    """
    step = args.step.strip().lower()

    if step in ("4c", "torrent", "sources"):
        from workflow.torrent_sources.run import cmd_test as torrent_test

        if not args.test:
            print("当前仅实现 --test 模式；完整 batch/on-demand 见 R1 路线图。")
            return 1
        ns = argparse.Namespace(
            tmdb=args.tmdb,
            season=args.season,
            episode=args.episode,
            media_type=args.media_type,
            imdb_id=args.imdb_id,
            accounts=None,
            force=getattr(args, "force", False),
        )
        return torrent_test(ns)

    if step in ("recommended", "rec"):
        from workflow.recommended.scorer import score_slot, score_slot_demo

        if args.tmdb is None:
            print("recommended 步骤需要 --tmdb")
            return 1
        if getattr(args, "demo", False):
            result = score_slot_demo(
                tmdb_id=args.tmdb,
                season=args.season,
                episode=args.episode,
            )
        else:
            if args.media_type == "tv" and (args.season is None or args.episode is None):
                print("剧集槽位需要 --season 与 --episode")
                return 1
            result = score_slot(
                tmdb_id=args.tmdb,
                media_type=args.media_type,
                season=args.season,
                episode=args.episode,
                force=getattr(args, "force", False),
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("fetch", {}).get("error"):
            return 1
        if not result.get("ranked"):
            return 1
        return 0

    print(f"未知步骤: {step}。可用: 4c, recommended")
    return 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    """
    执行 pipeline 子命令。

    @param args: 含 action、tmdb、season、episode、mode、fetch、slots_json
    @returns: 进程退出码
    """
    action = args.action.strip().lower()

    if action == "batch":
        from pathlib import Path

        from workflow.storage.pipeline import load_slots_json, run_batch_slot_pipeline

        slots_path = Path(args.slots_json)
        if not slots_path.is_file():
            print(f"slots JSON 不存在: {slots_path}")
            return 1
        slots = load_slots_json(slots_path)
        result = run_batch_slot_pipeline(
            slots,
            mode=args.mode,
            fetch=args.fetch,
            skip_existing=args.skip_existing,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    if action == "refetch-all":
        from workflow.storage.pipeline import run_refetch_all_published_pipeline

        result = run_refetch_all_published_pipeline(force=not getattr(args, "no_force", False))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    if action != "slot":
        print("当前支持: pipeline slot | pipeline batch | pipeline refetch-all")
        return 1

    if args.tmdb is None:
        print("pipeline slot 需要 --tmdb")
        return 1
    if args.media_type == "tv" and (args.season is None or args.episode is None):
        print("剧集槽位需要 --season 与 --episode")
        return 1

    from workflow.storage.pipeline import run_slot_pipeline

    result = run_slot_pipeline(
        tmdb_id=args.tmdb,
        media_kind=args.media_type,
        season=args.season,
        episode=args.episode,
        mode=args.mode,
        fetch=args.fetch,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_query(args: argparse.Namespace) -> int:
    """
    从 MySQL 查询页面 Jinja2 上下文。

    @param args: 含 page_id
    @returns: 进程退出码
    """
    from workflow.storage.pipeline import query_page_context

    page_id = args.page_id
    if not page_id and args.tmdb:
        from workflow.storage.mysql_store import MySQLStore

        store = MySQLStore()
        page_id = store.resolve_page_id(
            args.tmdb, args.media_type, args.season, args.episode
        )

    if not page_id:
        print("query page 需要 --page-id 或 --tmdb + --season + --episode")
        return 1

    result = query_page_context(page_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_generate(args: argparse.Namespace) -> int:
    """
    从 MySQL 生成静态 HTML 到 portal/dist。

    @param args: 含 action、page_id、path、out
    @returns: 进程退出码
    """
    from pathlib import Path

    from portal.generator.generate_one import (
        DEFAULT_OUT_ROOT,
        write_all_published,
        write_by_url_path,
        write_page_html,
    )

    out_root = Path(args.out) if args.out else DEFAULT_OUT_ROOT
    action = args.action.strip().lower()

    show_ig_debug: Optional[bool] = None
    if getattr(args, "show_ig_debug", False):
        show_ig_debug = True
    elif getattr(args, "no_ig_debug", False):
        show_ig_debug = False

    if action == "page":
        if args.page_id:
            result = write_page_html(
                args.page_id,
                out_root=out_root,
                show_ig_debug=show_ig_debug,
            )
        elif args.path:
            result = write_by_url_path(
                args.path,
                out_root=out_root,
                show_ig_debug=show_ig_debug,
            )
        else:
            print("generate page 需要 --page-id 或 --path")
            return 1
    elif action == "all":
        result = write_all_published(out_root=out_root, show_ig_debug=show_ig_debug)
    else:
        print("未知 generate 子命令；可用: page, all")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """
    启动 Portal 开发服务器（MySQL 动态渲染）。

    @param args: 含 host、port
    @returns: 进程退出码（通常阻塞至 Ctrl+C）
    """
    from portal.generator.dev_server import run_dev_server

    run_dev_server(host=args.host, port=args.port)
    return 0


def cmd_serve_static(args: argparse.Namespace) -> int:
    """
    启动 portal/dist 纯静态预览（自动同步 static 壳）。

    @param args: 含 host、port
    @returns: 进程退出码
    """
    from portal.generator.dev_server import run_static_server

    run_static_server(host=args.host, port=args.port)
    return 0


def cmd_ops(args: argparse.Namespace) -> int:
    """
    Ops 运营控制台子命令入口。

    @param args: 含 ops_action、host、port 或 tmdb-sync 参数
    @returns: 进程退出码
    """
    action = getattr(args, "ops_action", None)
    if action == "serve":
        from workflow.ops.server import run_ops_server

        run_ops_server(host=args.host, port=args.port)
        return 0
    if action == "tmdb-sync":
        from workflow.ops import source_service

        print(
            "[ops tmdb-sync] 全量下载 Daily Export → "
            f"{'TRUNCATE 全量重建' if args.full_reload else '增量 UPSERT'}…"
        )
        meta = source_service.daily_sync_export(
            export_date=args.export_date,
            force_reload=bool(args.full_reload),
        )
        print(
            f"[ops tmdb-sync] ok · export_date={meta.get('export_date')} · "
            f"movie={meta.get('movie_count'):,} · tv={meta.get('tv_count'):,} · "
            f"mode={meta.get('ingest_mode')} · "
            f"scanned={meta.get('last_scanned'):,} · deleted={meta.get('last_deleted'):,}"
        )
        return 0 if meta.get("ok") and meta.get("ready") else 1
    print("未知 ops 子命令；可用: serve / tmdb-sync")
    return 1


def build_parser() -> argparse.ArgumentParser:
    """
    构建 argparse 解析器。

    @returns: 配置好的 ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="ReleaseMatch Release 导航站工作流总控（MySQL 测试 → D1 生产）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="查看模块、存储与数据库状态")
    p_status.set_defaults(func=cmd_status)

    p_db = sub.add_parser("db", help="Release MySQL 数据库管理")
    db_sub = p_db.add_subparsers(dest="db_action", required=True)

    p_db_init = db_sub.add_parser("init", help="建库 + 执行 schema/mysql_schema.sql")
    p_db_init.add_argument(
        "--seed", action="store_true", help="初始化后导入 mysql_seed_demo.sql"
    )
    p_db_init.add_argument(
        "--skip-create-db",
        action="store_true",
        help="跳过 CREATE DATABASE（库已存在时使用）",
    )
    p_db_init.set_defaults(func=cmd_db_init)

    p_db_create = db_sub.add_parser("create", help="仅 CREATE DATABASE IF NOT EXISTS")
    p_db_create.set_defaults(func=cmd_db_create)

    p_db_seed = db_sub.add_parser("seed", help="导入演示种子数据")
    p_db_seed.set_defaults(func=cmd_db_seed)

    p_db_status = db_sub.add_parser("status", help="检查连通性与表行数")
    p_db_status.set_defaults(func=cmd_db_status)

    p_run = sub.add_parser("run", help="执行工作流步骤（4c / recommended）")
    p_run.add_argument("step", help="步骤 ID：4c / recommended")
    p_run.add_argument("--test", action="store_true", help="测试模式（4c 单槽拉取）")
    p_run.add_argument("--tmdb", type=int, default=None, help="TMDB 作品 ID")
    p_run.add_argument("--media-type", default="tv", choices=("tv", "movie"))
    p_run.add_argument("--season", type=int, default=None)
    p_run.add_argument("--episode", type=int, default=None)
    p_run.add_argument("--imdb-id", default=None)
    p_run.add_argument("--force", action="store_true", help="忽略 torrent 缓存")
    p_run.add_argument("--demo", action="store_true", help="recommended 使用内置 Demo 数据")
    p_run.set_defaults(func=cmd_run)

    p_pipeline = sub.add_parser("pipeline", help="槽位 pipeline（评分 → 写库）")
    pipe_sub = p_pipeline.add_subparsers(dest="action", required=True)
    p_pipe_slot = pipe_sub.add_parser("slot", help="处理单个槽位")
    p_pipe_slot.add_argument("--tmdb", type=int, required=True)
    p_pipe_slot.add_argument("--media-type", default="tv", choices=("tv", "movie"))
    p_pipe_slot.add_argument("--season", type=int, default=None)
    p_pipe_slot.add_argument("--episode", type=int, default=None)
    p_pipe_slot.add_argument(
        "--mode", default="demo", choices=("demo", "live"), help="demo=内置数据 live=需 --fetch"
    )
    p_pipe_slot.add_argument(
        "--fetch", action="store_true", help="调用 torrent_sources（R1，当前回退 demo）"
    )
    p_pipe_slot.set_defaults(func=cmd_pipeline)

    p_pipe_batch = pipe_sub.add_parser("batch", help="批量处理 benchmark slot JSON")
    p_pipe_batch.add_argument(
        "--slots-json",
        default="worklogs/2026-07-03/tmdb-benchmark-slots.json",
        help="slot 清单 JSON",
    )
    p_pipe_batch.add_argument(
        "--mode", default="live", choices=("demo", "live"), help="demo=内置数据 live=需 fetch"
    )
    p_pipe_batch.add_argument("--fetch", action="store_true", default=True, help="拉取 torrent（默认）")
    p_pipe_batch.add_argument("--no-fetch", action="store_false", dest="fetch")
    p_pipe_batch.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="不跳过已有 >=2 magnet 的页面",
    )
    p_pipe_batch.set_defaults(func=cmd_pipeline, skip_existing=True)

    p_pipe_refetch = pipe_sub.add_parser(
        "refetch-all",
        help="全站 published 槽位强制重拉 torrent（更新跨源分母）",
    )
    p_pipe_refetch.add_argument(
        "--no-force",
        action="store_true",
        help="不忽略 torrent 缓存（默认 force 重拉）",
    )
    p_pipe_refetch.set_defaults(func=cmd_pipeline)

    p_query = sub.add_parser("query", help="从 MySQL 读取页面数据")
    query_sub = p_query.add_subparsers(dest="query_action", required=True)
    p_query_page = query_sub.add_parser("page", help="输出 episode.html 上下文 JSON")
    p_query_page.add_argument("--page-id", default=None, help="如 tv:1396:s04e06")
    p_query_page.add_argument("--tmdb", type=int, default=None)
    p_query_page.add_argument("--media-type", default="tv", choices=("tv", "movie"))
    p_query_page.add_argument("--season", type=int, default=None)
    p_query_page.add_argument("--episode", type=int, default=None)
    p_query_page.set_defaults(func=cmd_query)

    p_generate = sub.add_parser("generate", help="MySQL → 静态 HTML（portal/dist）")
    gen_sub = p_generate.add_subparsers(dest="action", required=True)
    p_gen_page = gen_sub.add_parser("page", help="生成单页")
    p_gen_page.add_argument("--page-id", default=None, help="如 tv:1396:s04e06")
    p_gen_page.add_argument("--path", default=None, help="URL 路径，如 /breaking-bad/s4e6/")
    p_gen_page.add_argument(
        "--out", default=None, help="输出根目录，默认 portal/dist"
    )
    p_gen_page.add_argument(
        "--show-ig-debug",
        action="store_true",
        help="页面嵌入 IG debug 面板（覆盖 RM_SHOW_IG_DEBUG）",
    )
    p_gen_page.add_argument(
        "--no-ig-debug",
        action="store_true",
        help="强制关闭 IG debug 面板",
    )
    p_gen_page.set_defaults(func=cmd_generate)
    p_gen_all = gen_sub.add_parser("all", help="批量生成 published 页面")
    p_gen_all.add_argument("--out", default=None, help="输出根目录")
    p_gen_all.add_argument(
        "--show-ig-debug",
        action="store_true",
        help="页面嵌入 IG debug 面板",
    )
    p_gen_all.add_argument(
        "--no-ig-debug",
        action="store_true",
        help="强制关闭 IG debug 面板",
    )
    p_gen_all.set_defaults(func=cmd_generate)

    p_serve = sub.add_parser("serve", help="本地开发服（DB 动态渲染）")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.set_defaults(func=cmd_serve)

    p_serve_static = sub.add_parser(
        "serve-static",
        help="纯静态预览 portal/dist（自动同步 static，内联 i18n）",
    )
    p_serve_static.add_argument("--host", default="127.0.0.1")
    p_serve_static.add_argument("--port", type=int, default=8080)
    p_serve_static.set_defaults(func=cmd_serve_static)

    p_ops = sub.add_parser("ops", help="本地运营控制台（清单→筛选→生成→上线）")
    ops_sub = p_ops.add_subparsers(dest="ops_action", required=True)
    p_ops_serve = ops_sub.add_parser("serve", help="启动 Ops UI（仅 127.0.0.1）")
    p_ops_serve.add_argument("--host", default="127.0.0.1", help="仅允许本机")
    p_ops_serve.add_argument("--port", type=int, default=8090)
    p_ops_serve.set_defaults(func=cmd_ops)

    p_ops_tmdb = ops_sub.add_parser(
        "tmdb-sync",
        help="每天：全量下载 TMDB Daily Export → MySQL 增量入库（适合 cron）",
    )
    p_ops_tmdb.add_argument(
        "--export-date",
        default=None,
        help="YYYY-MM-DD；默认探测最近可用导出日",
    )
    p_ops_tmdb.add_argument(
        "--full-reload",
        action="store_true",
        help="TRUNCATE 后全量重建（默认增量 UPSERT + prune）",
    )
    p_ops_tmdb.set_defaults(func=cmd_ops)

    return parser


def main(argv: list[str] | None = None) -> int:
    """
    CLI 主入口。

    @param argv: 命令行参数列表，默认 sys.argv[1:]
    @returns: 进程退出码
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
