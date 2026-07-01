#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测速 CLI 入口。

@module workflow.torrent_sources.speedtest.run
@description
  子命令：
    status   — 模块状态与 libtorrent 可用性
    test     — 单条 infohash Phase 1 探测
    speed    — 单条 infohash Phase 2 片段测速（S-06）
    full     — Phase 1 + Phase 2 组合
    slot     — 对 MySQL 槽位 Recommended 测速（可选 --write）
    dry-run  — 同 test --dry-run（兼容别名）
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from workflow.torrent_sources.speedtest.full_speed import run_full_speedtest
from workflow.torrent_sources.speedtest.phase1_connectivity import test_connectivity
from workflow.torrent_sources.speedtest.phase2_speed import DEFAULT_TARGET_BYTES, test_fragment_speed
from workflow.torrent_sources.speedtest.store_service import persist_speedtest_results, speedtest_recommended_slot


def _libtorrent_available() -> bool:
    """
    检测 libtorrent 是否已安装。

    @returns: True 表示可跑真实 Phase 1/2
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
        "phases": [1, 2],
        "libtorrent_available": _libtorrent_available(),
        "implementation": (
            "phase1+phase2" if _libtorrent_available() else "dry_run_only"
        ),
        "s06_fields": ["avg_kbps", "max_kbps", "recommended_speed"],
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


def cmd_speed(args: argparse.Namespace) -> int:
    """
    对单条 infohash 执行 Phase 2 片段测速（S-06）。

    @param args: CLI 参数
    @returns: 退出码
    """
    result = test_fragment_speed(
        args.infohash,
        page_id=args.page_id,
        timeout_sec=args.timeout,
        target_bytes=args.target_bytes,
        force_dry_run=args.dry_run,
        magnet_uri=args.magnet_uri,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.status in ("ok", "dry_run", "timeout") else 1


def cmd_full(args: argparse.Namespace) -> int:
    """
    Phase 1 + Phase 2 组合测速，可选写入 MySQL。

    @param args: CLI 参数
    @returns: 退出码
    """
    full = run_full_speedtest(
        args.infohash,
        page_id=args.page_id,
        phase1_timeout_sec=args.phase1_timeout,
        phase2_timeout_sec=args.timeout,
        target_bytes=args.target_bytes,
        force_dry_run=args.dry_run,
        magnet_uri=args.magnet_uri,
    )
    payload: Dict[str, Any] = full.to_dict()
    if args.write:
        payload["write"] = persist_speedtest_results(full, page_id=args.page_id)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    err_status = full.phase2.status if full.phase2.status == "error" else full.phase1.status
    return 0 if err_status in ("ok", "dry_run", "timeout", "skipped") else 1


def cmd_slot(args: argparse.Namespace) -> int:
    """
    对 MySQL 槽位 Recommended magnet 执行完整测速。

    @param args: 含 --page-id、--write
    @returns: 退出码
    """
    try:
        payload = speedtest_recommended_slot(
            args.page_id,
            phase1_timeout_sec=args.phase1_timeout,
            phase2_timeout_sec=args.timeout,
            target_bytes=args.target_bytes,
            force_dry_run=args.dry_run,
            write_mysql=args.write,
        )
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    phase2_status = payload.get("speedtest", {}).get("phase2", {}).get("status", "ok")
    return 0 if phase2_status in ("ok", "dry_run", "timeout", "skipped") else 1


def _add_common_speed_args(parser: argparse.ArgumentParser, *, include_page_id: bool = True) -> None:
    """
    为 speed / full / slot 子命令添加共用参数。

    @param parser: ArgumentParser 实例
    @param include_page_id: slot 子命令已单独定义 --page-id 时为 False
    @returns: None
    """
    if include_page_id:
        parser.add_argument("--page-id", default=None, help="关联 page_id")
    parser.add_argument("--timeout", type=int, default=30, help="Phase 2 超时秒数")
    parser.add_argument(
        "--phase1-timeout",
        type=int,
        default=20,
        help="Phase 1 超时秒数（full/slot）",
    )
    parser.add_argument(
        "--target-bytes",
        type=int,
        default=DEFAULT_TARGET_BYTES,
        help="Phase 2 目标下载字节（默认 1MB）",
    )
    parser.add_argument("--magnet-uri", default=None, help="完整 magnet URI（含 tracker）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不联网，仅校验 infohash 格式",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="写入 MySQL speedtest_results + slot_speed_summary",
    )


def build_parser() -> argparse.ArgumentParser:
    """
    构造 argparse 解析器。

    @returns: ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        prog="python -m workflow.torrent_sources.speedtest.run",
        description="磁力测速 Phase 1/2 CLI（S-06）",
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

    p_speed = sub.add_parser("speed", help="单条 infohash Phase 2（S-06）")
    p_speed.add_argument("--infohash", required=True, help="40 位 infohash")
    _add_common_speed_args(p_speed)
    p_speed.set_defaults(func=cmd_speed)

    p_full = sub.add_parser("full", help="Phase 1 + Phase 2 组合")
    p_full.add_argument("--infohash", required=True, help="40 位 infohash")
    _add_common_speed_args(p_full)
    p_full.set_defaults(func=cmd_full)

    p_slot = sub.add_parser("slot", help="MySQL 槽位 Recommended 测速")
    p_slot.add_argument("--page-id", required=True, help="如 tv:1396:s04e06")
    _add_common_speed_args(p_slot, include_page_id=False)
    p_slot.set_defaults(func=cmd_slot)

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
