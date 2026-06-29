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

  示例：
    cd releasematch && cp config.env.example .env  # 按需编辑
    cd releasematch && python -m workflow.run db init
    cd releasematch && python -m workflow.run db seed
    cd releasematch && python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6
    cd releasematch && python -m workflow.run query page --page-id tv:1396:s04e06
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
            "torrent_sources": "scaffold",
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
        )
        return torrent_test(ns)

    if step in ("recommended", "rec"):
        from workflow.recommended.scorer import score_slot_demo

        if args.tmdb is None:
            print("recommended 步骤需要 --tmdb")
            return 1
        result = score_slot_demo(
            tmdb_id=args.tmdb,
            season=args.season,
            episode=args.episode,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"未知步骤: {step}。可用: 4c, recommended")
    return 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    """
    执行 pipeline 子命令。

    @param args: 含 action、tmdb、season、episode、mode、fetch
    @returns: 进程退出码
    """
    action = args.action.strip().lower()
    if action != "slot":
        print("当前仅支持: pipeline slot")
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

    p_query = sub.add_parser("query", help="从 MySQL 读取页面数据")
    query_sub = p_query.add_subparsers(dest="query_action", required=True)
    p_query_page = query_sub.add_parser("page", help="输出 episode.html 上下文 JSON")
    p_query_page.add_argument("--page-id", default=None, help="如 tv:1396:s04e06")
    p_query_page.add_argument("--tmdb", type=int, default=None)
    p_query_page.add_argument("--media-type", default="tv", choices=("tv", "movie"))
    p_query_page.add_argument("--season", type=int, default=None)
    p_query_page.add_argument("--episode", type=int, default=None)
    p_query_page.set_defaults(func=cmd_query)

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
