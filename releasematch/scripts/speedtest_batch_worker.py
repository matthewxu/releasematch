#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海外 VPS / 本机 cron 批量测速 Worker（5 并发默认）。

@file scripts/speedtest_batch_worker.py
@description
  封装 speedtest batch 子命令，供 crontab / systemd 定时调用。
  输出 JSON 到 stdout；有 error 槽位时退出码 1。

用法：
  cd releasematch
  python scripts/speedtest_batch_worker.py \\
    --slots-json worklogs/2026-06-30/benchmark-slots.json \\
    --write --workers 5 \\
    --report worklogs/2026-07-02/speedtest-batch-benchmark.json

cron 示例（每 6 小时，见 docs/VPS迁移与部署.md）：
  0 */6 * * * cd /path/releasematch && .venv/bin/python scripts/speedtest_batch_worker.py ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保 releasematch 根在 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.torrent_sources.speedtest.batch_service import (  # noqa: E402
    DEFAULT_BATCH_TARGET_BYTES,
    DEFAULT_SPEEDTEST_TTL_HOURS,
    load_batch_targets,
    run_batch_speedtest,
    write_batch_report,
)


def build_parser() -> argparse.ArgumentParser:
    """
    构造 Worker CLI 解析器。

    @returns: ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="python scripts/speedtest_batch_worker.py",
        description="批量槽位测速 Worker（cron / systemd）",
    )
    parser.add_argument(
        "--page-ids",
        default=None,
        help="逗号分隔 page_id",
    )
    parser.add_argument(
        "--slots-json",
        default=None,
        help="benchmark 槽位 JSON",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="报告 JSON 路径",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="并发进程数（默认 5）",
    )
    parser.add_argument(
        "--target-bytes",
        type=int,
        default=DEFAULT_BATCH_TARGET_BYTES,
        help="Phase 2 目标字节",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Phase 2 超时")
    parser.add_argument("--phase1-timeout", type=int, default=20, help="Phase 1 超时")
    parser.add_argument("--write", action="store_true", help="写 MySQL")
    parser.add_argument("--force", action="store_true", help="忽略 TTL")
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=DEFAULT_SPEEDTEST_TTL_HOURS,
        help="TTL 跳过小时数",
    )
    parser.add_argument("--dry-run", action="store_true", help="dry-run 模式")
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Worker 主入口。

    @param argv: 命令行参数
    @returns: 0 全部成功；1 有 error 或输入无效
    """
    args = build_parser().parse_args(argv)

    page_ids = None
    if args.page_ids:
        page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()]

    try:
        targets = load_batch_targets(page_ids=page_ids, slots_json=args.slots_json)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    report = run_batch_speedtest(
        targets,
        phase1_timeout_sec=args.phase1_timeout,
        phase2_timeout_sec=args.timeout,
        target_bytes=args.target_bytes,
        force_dry_run=args.dry_run,
        write_mysql=args.write,
        ttl_hours=args.ttl_hours,
        force=args.force,
        workers=args.workers,
    )

    if args.report:
        path = write_batch_report(report, args.report)
        report.setdefault("meta", {})["report_file"] = str(path)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("summary", {}).get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
