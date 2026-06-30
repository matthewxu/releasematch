#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
torrent_sources CLI 入口。

@module workflow.torrent_sources.run
@description
  子命令（逐步实现，当前为 scaffold）：
    status    — 缓存与配置状态
    test      — 单槽测试拉取（R0 MVP 目标）

  示例：
    cd releasematch && python -m workflow.torrent_sources.run status
    cd releasematch && python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.config import TMDB_DATA_MODE
from workflow.metadata.external_ids import resolve_external_ids
from workflow.torrent_sources.cache_index import CacheIndex
from workflow.torrent_sources.config import (
    is_jackett_api_key_configured,
    load_accounts_config,
    probe_jackett_http,
    resolve_accounts_config_path,
)
from workflow.torrent_sources.fetch_service import FetchService
from workflow.torrent_sources.models import FetchMode, FetchRequest, FetchResult, MediaType


def cmd_status(args: argparse.Namespace) -> int:
    """
    打印 torrent_sources 模块状态。

    @param args: argparse 命名空间
    @returns: 退出码 0
    """
    cache = CacheIndex()
    cfg_path = resolve_accounts_config_path(
        Path(args.accounts) if args.accounts else None
    )
    cfg = load_accounts_config(cfg_path)
    jackett = cfg.get("jackett", {})
    api_key = str(jackett.get("api_key") or "")
    base_url = str(jackett.get("base_url") or "")
    summary = {
        "cache_entries": cache.count(),
        "accounts_config": str(cfg_path),
        "accounts_local_exists": cfg_path.name == "accounts.local.json",
        "jackett_base_url": base_url,
        "has_api_key": bool(api_key),
        "has_valid_api_key": is_jackett_api_key_configured(api_key),
        "jackett_probe": probe_jackett_http(base_url) if base_url else None,
        "tmdb_data_mode": TMDB_DATA_MODE,
        "implementation": "mvp",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """
    测试单槽资源拉取（当前返回 external_ids + 占位结果）。

    @param args: 含 tmdb、season、episode
    @returns: 退出码
    """
    media_type = MediaType.MOVIE if args.media_type == "movie" else MediaType.TV
    ext = resolve_external_ids(
        tmdb_id=args.tmdb,
        media_type=args.media_type,
        imdb_id=args.imdb_id,
    )

    request = FetchRequest(
        tmdb_id=args.tmdb,
        media_type=media_type,
        season=args.season,
        episode=args.episode,
        imdb_id=ext.get("imdb_id") or args.imdb_id,
        tvdb_id=ext.get("tvdb_id"),
        mode=FetchMode.ON_DEMAND,
        force=args.force,
    )

    service = FetchService(
        accounts_path=args.accounts,
    )
    result = service.fetch_slot(request)

    output = {
        "external_ids": ext,
        "fetch": result.to_dict(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if result.error:
        return 1
    if len(result.items) < 2:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 解析器。"""
    parser = argparse.ArgumentParser(description="ReleaseMatch torrent 多源清单模块")
    parser.add_argument("--accounts", default=None, help="accounts.local.json 路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="模块状态")
    p_status.set_defaults(func=cmd_status)

    p_test = sub.add_parser("test", help="单槽测试拉取")
    p_test.add_argument("--tmdb", type=int, required=True)
    p_test.add_argument("--media-type", default="tv", choices=("tv", "movie"))
    p_test.add_argument("--season", type=int, default=None)
    p_test.add_argument("--episode", type=int, default=None)
    p_test.add_argument("--imdb-id", default=None)
    p_test.add_argument("--force", action="store_true", help="忽略缓存强制重拉")
    p_test.set_defaults(func=cmd_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
