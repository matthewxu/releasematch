#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S-04 fuzzy 跨源对齐批处理（不重拉 indexer）。

@module scripts.recompute_cross_source_fuzzy
@description 读取 MySQL download_resources → apply_fuzzy_cross_source → rescore 写回
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 允许从仓库根目录执行
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.storage.pipeline import (  # noqa: E402
    recompute_page_cross_source_fuzzy,
    recompute_published_cross_source_fuzzy,
    rescore_published_pages,
)


def main() -> int:
    """
    CLI 入口：单页或全 published 批量 fuzzy 对齐。

    @returns: 0 成功 · 1 失败
    """
    parser = argparse.ArgumentParser(description="S-04 release 指纹 fuzzy 跨源重算（不重拉）")
    parser.add_argument("--page-id", help="单页 page_id，如 tv:1396:s04e04")
    parser.add_argument(
        "--all-published",
        action="store_true",
        help="批量处理 list_published_page_ids()",
    )
    parser.add_argument(
        "--media-kind",
        choices=("tv", "movie"),
        help="与 --all-published 联用，过滤媒体类型",
    )
    parser.add_argument(
        "--rescore-after",
        action="store_true",
        help="fuzzy 后额外跑 rescore_published_pages（yaml 变更时可用）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if args.page_id:
        report = recompute_page_cross_source_fuzzy(args.page_id)
    elif args.all_published:
        report = recompute_published_cross_source_fuzzy(media_kind=args.media_kind)
    else:
        parser.error("请指定 --page-id 或 --all-published")

    if args.rescore_after and args.all_published:
        rescore = rescore_published_pages(media_kind=args.media_kind)
        report["rescore"] = rescore

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report.get("ok") is False and report.get("error"):
            print(f"FAIL {report.get('page_id')}: {report.get('error')}")
        elif args.all_published:
            print(
                f"OK total={report.get('total')} "
                f"improved={report.get('improved_count')} "
                f"fail={report.get('fail_count')}"
            )
        else:
            print(
                f"OK {report.get('page_id')} "
                f"cross {report.get('cross_max_before')}→{report.get('cross_max_after')}"
            )

    return 0 if report.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
