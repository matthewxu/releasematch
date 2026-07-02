#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并历史 pipeline 报告 → 失败 slot 去重登记册。

@file scripts/failed_slots_merge_reports.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.storage.failed_slots_store import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    export_active_slots,
    load_registry,
    merge_report_files,
)


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器。"""
    parser = argparse.ArgumentParser(description="合并 pipeline 失败 slot 登记册")
    parser.add_argument(
        "--worklog-dir",
        default=str(_ROOT / "worklogs" / "2026-07-03"),
        help="扫描 pipeline-*-report.json 的目录",
    )
    parser.add_argument(
        "--slots",
        nargs="*",
        default=[
            str(_ROOT / "worklogs/2026-07-03/tmdb-benchmark-slots.json"),
            str(_ROOT / "worklogs/2026-07-03/tmdb-benchmark-slots-supplement.json"),
        ],
        help="slot 元数据 JSON（可多个）",
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH), help="登记册输出路径")
    parser.add_argument("--list-active", action="store_true", help="仅列出当前 active 失败项")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    args = build_parser().parse_args(argv)
    registry_path = Path(args.registry)

    if args.list_active:
        registry = load_registry(registry_path)
        active = export_active_slots(registry)
        print(json.dumps({"active_count": len(active), "slots": active}, ensure_ascii=False, indent=2))
        return 0

    worklog_dir = Path(args.worklog_dir)
    report_paths = sorted(worklog_dir.glob("pipeline-*-report.json"))
    if not report_paths:
        report_paths = sorted(worklog_dir.glob("**/pipeline-*-report.json"))

    slots_paths = [Path(p) for p in args.slots]
    summary = merge_report_files(report_paths, slots_paths=slots_paths, registry_path=registry_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
