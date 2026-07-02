#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载 TMDB 日导出并生成 benchmark 测试 slot JSON。

@file scripts/tmdb_select_benchmark_slots.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.metadata.tmdb_export_slots import (  # noqa: E402
    DEFAULT_EXPORT_DIR,
    ExportFileSet,
    _export_date_suffix,
    build_benchmark_slot_list,
    download_tmdb_exports,
    resolve_latest_export_date,
    write_report_json,
    write_slots_json,
)


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器。"""
    parser = argparse.ArgumentParser(description="TMDB Daily Export → benchmark slot")
    parser.add_argument("--download", action="store_true", help="下载 movie/tv .json.gz")
    parser.add_argument("--force-download", action="store_true", help="强制重新下载")
    parser.add_argument("--export-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--total", type=int, default=20, help="目标 slot 总数")
    parser.add_argument("--movies", type=int, default=None, help="新增电影数")
    parser.add_argument("--tv", type=int, default=None, help="新增 TV 数")
    parser.add_argument("--out-dir", default=None, help="worklog 输出目录")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    args = build_parser().parse_args(argv)
    export_date = date.fromisoformat(args.export_date) if args.export_date else None

    if args.download or args.force_download:
        files = download_tmdb_exports(export_date, force=args.force_download)
    else:
        resolved = export_date or resolve_latest_export_date()
        suffix = _export_date_suffix(resolved)
        movie_gz = DEFAULT_EXPORT_DIR / f"movie_ids_{suffix}.json.gz"
        tv_gz = DEFAULT_EXPORT_DIR / f"tv_series_ids_{suffix}.json.gz"
        if not movie_gz.is_file() or not tv_gz.is_file():
            print(json.dumps({"ok": False, "error": "导出不存在，请加 --download"}, ensure_ascii=False))
            return 1
        files = ExportFileSet(export_date=resolved, movie_gz=movie_gz, tv_gz=tv_gz)

    report = build_benchmark_slot_list(
        files, total=args.total, movie_count=args.movies, tv_count=args.tv
    )
    day = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(args.out_dir) if args.out_dir else _ROOT / "worklogs" / day
    slots_path = out_dir / "tmdb-benchmark-slots.json"
    report_path = out_dir / "tmdb-benchmark-slots-report.json"
    write_slots_json(report, slots_path)
    write_report_json(report, report_path)
    print(
        json.dumps(
            {
                "ok": True,
                "export_date": report["meta"]["export_date"],
                "total_slots": report["meta"]["total_slots"],
                "slots_file": str(slots_path),
                "report_file": str(report_path),
                "slots": report["slots"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
