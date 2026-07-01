#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测速 CLI 入口。

@module workflow.torrent_sources.speedtest.run
@description
  子命令：
    status   — 模块状态与 libtorrent 可用性
    test     — 单条 infohash Phase 1 探测
    dry-run  — 仅校验 infohash 格式（不联网）
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from workflow.torrent_sources.speedtest.phase1_connectivity import test_connectivity


def _libtorrent_available() -> bool:
    """
    检测 libtorrent 是否已安装。

    @returns: True 表示可跑真实 Phase 1
    """
    try:
        import libtorrent  # noqa: F401

        return True
    except ImportError:
        return False


def cmd_status(_args: argparse.Namespace) -> int:
    """
    打印测速模块状态。

    @param _args: CLI 命名空间（未使用）
    @returns: 退出码 0
    """
    payload: Dict[str, Any] = {
        "module": "speedtest",
        "phase": 1,
        "libtorrent_available": _libtorrent_available(),
        "implementation": "scaffold" if not _libtorrent_available() else "phase1",
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """
    对单条 infohash 执行 Phase 1 探测。

    @param args: 含 --infohash、--page-id、--timeout、--dry-run
    @returns: 退出码（error 时 1）
    """
    result = test_connectivity(
        args.infohash,
        page_id=args.page_id,
        timeout_sec=args.timeout,
        force_dry_run=args.dry_run,
        magnet_uri=args.magnet_uri,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.status in ("ok", "dry_run", "timeout") else 1


def build_parser() -> argparse.ArgumentParser:
    """
    构造 argparse 解析器。

    @returns: ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        prog="python -m workflow.torrent_sources.speedtest.run",
        description="磁力测速 Phase 1 CLI",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_status = sub.add_parser("status", help="模块状态")
    p_status.set_defaults(func=cmd_status)

    p_test = sub.add_parser("test", help="单条 infohash Phase 1")
    p_test.add_argument("--infohash", required=True, help="40 位 infohash")
    p_test.add_argument("--page-id", default=None, help="关联 page_id")
    p_test.add_argument("--timeout", type=int, default=10, help="超时秒数")
    p_test.add_argument("--magnet-uri", default=None, help="完整 magnet URI（含 tracker）")
    p_test.add_argument(
        "--dry-run",
        action="store_true",
        help="不联网，仅校验 infohash 格式",
    )
    p_test.set_defaults(func=cmd_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    """
    CLI 主入口。

    @param argv: 命令行参数；None 时用 sys.argv
    @returns: 进程退出码
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
