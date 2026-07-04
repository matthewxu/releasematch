#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华语剧 PoC 批量拉取与报告 — cn 路由 + DMHy/Nyaa/Jackett 验证。

@file scripts/cn_poc_fetch.py
@description
  读取 cn-benchmark-slots.json，逐槽 test 拉取并汇总 region / source_enabled / 条数。

用法：
  cd releasematch
  python scripts/cn_poc_fetch.py
  python scripts/cn_poc_fetch.py --force --report worklogs/2026-07-04/cn-dmhy-poc.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.torrent_sources.batch_fetch import load_slots_from_json, run_batch_fetch


def build_parser() -> argparse.ArgumentParser:
    """
    构造 CLI 解析器。

    @returns: ArgumentParser
    """
    parser = argparse.ArgumentParser(description="华语剧 cn 路由 PoC 批量拉取")
    parser.add_argument(
        "--slots-json",
        default=str(_ROOT / "worklogs/2026-07-04/cn-benchmark-slots.json"),
        help="华语 benchmark 槽位 JSON",
    )
    parser.add_argument("--force", action="store_true", help="忽略缓存强制重拉")
    parser.add_argument("--min-count", type=int, default=1, help="单槽最少 magnet 条数")
    parser.add_argument("--report", default=None, help="报告输出路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    主入口：批量拉取华语槽并写 JSON 报告。

    @param argv: 命令行参数
    @returns: 0 全部成功；1 有失败槽
    """
    args = build_parser().parse_args(argv)
    slots_path = Path(args.slots_json)
    if not slots_path.is_file():
        print(json.dumps({"ok": False, "error": f"文件不存在: {slots_path}"}, ensure_ascii=False))
        return 1

    slots = load_slots_from_json(slots_path)
    if args.force:
        for slot in slots:
            slot.force = True

    summary = run_batch_fetch(slots, min_count=args.min_count)
    report = {
        "meta": {
            "kind": "cn_poc",
            "slots_json": str(slots_path),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "min_count": args.min_count,
            "force": args.force,
        },
        "summary": summary.to_dict(),
    }

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["meta"]["report_file"] = str(out)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
