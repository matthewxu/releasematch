#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量 slot pipeline — 读取 benchmark JSON 并扩槽写 MySQL。

@file scripts/pipeline_batch_slots.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.storage.pipeline import load_slots_json, run_batch_slot_pipeline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器。"""
    parser = argparse.ArgumentParser(description="批量 slot pipeline（扩槽）")
    parser.add_argument(
        "--slots-json",
        default=str(_ROOT / "worklogs/2026-07-03/tmdb-benchmark-slots.json"),
        help="benchmark slot JSON 路径",
    )
    parser.add_argument("--mode", default="live", choices=("demo", "live"))
    parser.add_argument("--fetch", action="store_true", default=True, help="拉取 torrent（默认开启）")
    parser.add_argument("--no-fetch", action="store_false", dest="fetch")
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="不跳过已有 >=2 magnet 的页面",
    )
    parser.add_argument("--out", default=None, help="结果 JSON 输出路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    args = build_parser().parse_args(argv)
    slots_path = Path(args.slots_json)
    if not slots_path.is_file():
        print(json.dumps({"ok": False, "error": f"文件不存在: {slots_path}"}, ensure_ascii=False))
        return 1

    slots = load_slots_json(slots_path)
    report = run_batch_slot_pipeline(
        slots,
        mode=args.mode,
        fetch=args.fetch,
        skip_existing=args.skip_existing,
    )

    out_path = Path(args.out) if args.out else slots_path.parent / "pipeline-batch-report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if report.get("failed_slots_registry") is None and fetch:
        from workflow.storage.failed_slots_store import merge_batch_report

        reg = merge_batch_report(
            slots,
            report,
            report_path=str(out_path),
            source=out_path.stem,
        )
        report["failed_slots_registry"] = reg
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {k: report[k] for k in ("ok", "total", "ok_count", "skip_count", "fail_count", "sync_run_id")}
    if report.get("failed_slots_registry"):
        summary["failed_slots_active"] = report["failed_slots_registry"].get("active_count")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {out_path}")
    if report.get("failed_slots_registry"):
        print(f"failed registry: {report['failed_slots_registry'].get('registry_path')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
