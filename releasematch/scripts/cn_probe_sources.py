#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华语专用源逐源探测 — 仅测试 cn_sources（不含 TPB/1337x 等国际源）。

@file scripts/cn_probe_sources.py
@description
  对 benchmark 槽位逐源探测 dmhy / mikan / acgrip / Nyaa LA / Nyaa 动漫区，
  输出各源 raw/filtered 条数与样例标题。

用法：
  cd releasematch
  python scripts/cn_probe_sources.py
  python scripts/cn_probe_sources.py --slots-json worklogs/2026-07-04/cn-retest-slots.json \\
    --report worklogs/2026-07-04/cn-sources-probe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.metadata.tmdb_api import enrich_external_ids
from workflow.torrent_sources.batch_fetch import load_slots_from_json
from workflow.torrent_sources.cn_sources import CnSourceProber, resolve_cn_source_config


def build_parser() -> argparse.ArgumentParser:
    """
    构造 CLI 解析器。

    @returns: ArgumentParser
    """
    parser = argparse.ArgumentParser(description="华语专用源逐源探测（不含国际 Jackett）")
    parser.add_argument(
        "--slots-json",
        default=str(_ROOT / "worklogs/2026-07-04/cn-benchmark-slots.json"),
        help="测试槽位 JSON",
    )
    parser.add_argument("--report", default=None, help="报告输出路径")
    return parser


def probe_slot(
    prober: CnSourceProber,
    tmdb_id: int,
    media_type: str,
    season: int | None,
    episode: int | None,
    label: str,
) -> Dict[str, Any]:
    """
    探测单槽位各华语源。

    @param prober: CnSourceProber 实例
    @param tmdb_id: TMDB ID
    @param media_type: tv | movie
    @param season: 季号
    @param episode: 集号
    @param label: 人类可读标签
    @returns: 槽位探测报告字典
    """
    meta = enrich_external_ids(tmdb_id, media_type)
    row: Dict[str, Any] = {
        "label": label,
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "season": season,
        "episode": episode,
        "search_titles": [],
        "sources": [],
        "any_ok": False,
    }
    if media_type != "tv" or season is None or episode is None:
        row["error"] = "cn_probe_sources 当前仅支持 tv 季集槽"
        return row

    from workflow.torrent_sources.asia_region import build_search_titles

    row["search_titles"] = build_search_titles(meta, "cn")
    results = prober.probe_tv_slot(meta, season, episode)
    row["sources"] = [r.to_dict() for r in results]
    row["any_ok"] = any(r.filtered_count > 0 for r in results)
    return row


def main(argv: List[str] | None = None) -> int:
    """
    主入口。

    @param argv: 命令行参数
    @returns: 0 全部槽至少一源命中；1 否则
    """
    args = build_parser().parse_args(argv)
    slots_path = Path(args.slots_json)
    if not slots_path.is_file():
        print(json.dumps({"ok": False, "error": f"文件不存在: {slots_path}"}, ensure_ascii=False))
        return 1

    prober = CnSourceProber()
    source_cfg = resolve_cn_source_config()

    slots_raw = json.loads(slots_path.read_text(encoding="utf-8"))
    slot_rows: List[Dict[str, Any]] = []
    for row in slots_raw:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("tmdb_id"))
        slot_rows.append(
            probe_slot(
                prober,
                int(row["tmdb_id"]),
                str(row.get("media_type") or "tv"),
                row.get("season"),
                row.get("episode"),
                label,
            )
        )

    report = {
        "meta": {
            "kind": "cn_sources_probe",
            "slots_json": str(slots_path),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "cn_sources": source_cfg,
        },
        "slots": slot_rows,
        "summary": {
            "total": len(slot_rows),
            "slots_with_hits": sum(1 for s in slot_rows if s.get("any_ok")),
        },
    }

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["meta"]["report_file"] = str(out)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["summary"]["slots_with_hits"] == report["summary"]["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
