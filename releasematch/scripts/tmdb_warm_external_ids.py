#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预热 TMDB external_ids 本地缓存（经 CORS Proxy）。

@file scripts/tmdb_warm_external_ids.py
@description
  读取 benchmark slot JSON，批量拉取 imdb_id / tvdb_id 写入
  data/tmdb_exports/external_ids_cache.json，供 pipeline fetch 使用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.metadata.tmdb_api import warm_external_ids_cache  # noqa: E402
from workflow.storage.pipeline import load_slots_json  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 解析器。"""
    parser = argparse.ArgumentParser(description="TMDB external_ids 缓存预热")
    parser.add_argument(
        "--slots-json",
        default=str(_ROOT / "worklogs/2026-07-03/tmdb-benchmark-slots.json"),
        help="slot JSON 路径",
    )
    parser.add_argument(
        "--supplement-json",
        default=str(_ROOT / "worklogs/2026-07-03/tmdb-benchmark-slots-supplement.json"),
        help="补充 slot JSON（可选合并）",
    )
    parser.add_argument("--no-supplement", action="store_true", help="不合并 supplement JSON")
    parser.add_argument("--force", action="store_true", help="忽略已有缓存强制重拉")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    args = build_parser().parse_args(argv)
    slots_path = Path(args.slots_json)
    if not slots_path.is_file():
        print(json.dumps({"ok": False, "error": f"文件不存在: {slots_path}"}, ensure_ascii=False))
        return 1

    slots = load_slots_json(slots_path)
    if not args.no_supplement:
        sup_path = Path(args.supplement_json)
        if sup_path.is_file():
            slots = slots + load_slots_json(sup_path)

    report = warm_external_ids_cache(slots, force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
