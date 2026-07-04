#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量华语源探测（逐槽进度 + 报告）— cn_probe_sources 包装脚本。

@file scripts/run_cn_probe_full.py
@description
  对 cn-sources-test-slots.json 逐槽调用 CnSourceProber，输出进度并写入 JSON 报告。

用法：
  export TORRENT_PROXY=socks5h://127.0.0.1:1080
  python scripts/run_cn_probe_full.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.cn_probe_sources import probe_slot
from workflow.torrent_sources.cn_sources import CnSourceProber, resolve_cn_source_config

# 默认槽位与报告路径
DEFAULT_SLOTS = _ROOT / "worklogs/2026-07-04/cn-sources-test-slots.json"
DEFAULT_REPORT = _ROOT / "worklogs/2026-07-04/cn-sources-probe-socks-retest-v2.json"


def main() -> int:
    """
    主入口：逐槽探测并写报告。

    @returns: 0 若至少一槽命中，否则 1
    """
    slots_path = DEFAULT_SLOTS
    report_path = DEFAULT_REPORT
    slots_raw = json.loads(slots_path.read_text(encoding="utf-8"))
    prober = CnSourceProber()
    slot_rows = []
    started = time.time()
    print(f"started {datetime.now(timezone.utc).isoformat()}", flush=True)

    for row in slots_raw:
        label = str(row.get("label") or row["tmdb_id"])
        t0 = time.time()
        print(f"=== {label} ===", flush=True)
        result = probe_slot(
            prober,
            int(row["tmdb_id"]),
            str(row.get("media_type") or "tv"),
            row.get("season"),
            row.get("episode"),
            label,
        )
        hits = [s["source_id"] for s in result["sources"] if s.get("filtered_count", 0) > 0]
        print(
            f"done {time.time() - t0:.0f}s any_ok={result['any_ok']} hits={hits}",
            flush=True,
        )
        for s in result["sources"]:
            if s.get("raw_count") or s.get("filtered_count"):
                print(
                    f"  {s['source_id']}: raw={s['raw_count']} filtered={s['filtered_count']}",
                    flush=True,
                )
        slot_rows.append(result)

    report = {
        "meta": {
            "kind": "cn_sources_probe",
            "slots_json": str(slots_path),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_sec": round(time.time() - started),
            "cn_sources": resolve_cn_source_config(),
            "note": "VPS jackett/flaresolverr restarted + base32 + 第N集 queries + SSH SOCKS",
        },
        "slots": slot_rows,
        "summary": {
            "total": len(slot_rows),
            "slots_with_hits": sum(1 for s in slot_rows if s.get("any_ok")),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    print(f"report: {report_path}", flush=True)
    return 0 if report["summary"]["slots_with_hits"] else 1


if __name__ == "__main__":
    sys.exit(main())
