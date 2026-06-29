#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch 工作流总控 CLI。

@module workflow.run
@description
  替代原 tmdbpy/workflow/run.py Step 4c 的独立入口。
  子命令：
    status  — 模块与配置状态
    run     — 执行指定步骤（4c / recommended / sync 等，逐步扩展）

  示例：
    cd releasematch && python -m workflow.run status
    cd releasematch && python -m workflow.run run 4c --test --tmdb 1396 --season 4 --episode 6
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

from workflow.config import (
    EZTV_BASE_URL,
    JACKETT_BASE_URL,
    PROJECT_ROOT,
    TMDB_DATA_MODE,
    YTS_BASE_URL,
    ensure_project_dirs,
)


def cmd_status(_args: argparse.Namespace) -> int:
    """
    打印 ReleaseMatch 工作流状态摘要。

    @param _args: argparse 命名空间（未使用）
    @returns: 进程退出码 0
    """
    ensure_project_dirs()
    summary = {
        "project_root": str(PROJECT_ROOT),
        "tmdb_data_mode": TMDB_DATA_MODE,
        "endpoints": {
            "jackett": JACKETT_BASE_URL,
            "eztv": EZTV_BASE_URL,
            "yts": YTS_BASE_URL,
        },
        "modules": {
            "torrent_sources": "scaffold",
            "recommended": "scaffold",
            "metadata": "scaffold",
            "priority": "scaffold",
        },
        "portal": "not_started",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """
    执行指定工作流步骤。

    @param args: 含 step、tmdb、season、episode 等参数
    @returns: 进程退出码
    """
    step = args.step.strip().lower()

    if step in ("4c", "torrent", "sources"):
        from workflow.torrent_sources.run import cmd_test as torrent_test

        if not args.test:
            print("当前仅实现 --test 模式；完整 batch/on-demand 见 R0 路线图。")
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


def build_parser() -> argparse.ArgumentParser:
    """
    构建 argparse 解析器。

    @returns: 配置好的 ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="ReleaseMatch Release 导航站工作流总控（独立于字幕站）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="查看模块与配置状态")
    p_status.set_defaults(func=cmd_status)

    p_run = sub.add_parser("run", help="执行工作流步骤")
    p_run.add_argument("step", help="步骤 ID：4c / recommended")
    p_run.add_argument("--test", action="store_true", help="测试模式（4c 单槽拉取）")
    p_run.add_argument("--tmdb", type=int, default=None, help="TMDB 作品 ID")
    p_run.add_argument("--media-type", default="tv", choices=("tv", "movie"))
    p_run.add_argument("--season", type=int, default=None)
    p_run.add_argument("--episode", type=int, default=None)
    p_run.add_argument("--imdb-id", default=None)
    p_run.set_defaults(func=cmd_run)

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
