#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测 MySQL 相对 generated_at 的脏页，增量 bake dist，并可选 wrangler 上传。

@file scripts/incremental_publish_worker.py
@description
  补齐「测速 cron 只写库、静态页不更新」的缺口：
  1) 检出 stale page_ids（speed_summary / metadata / magnet / catalog / 页面自身）
  2) 增量 generate（含 Hub + home + sitemap + 壳）
  3) 默认 wrangler deploy；``--prepare-only`` 仅构建 dist（CF 正式上线暂缓时用）

数据流（读 / 写）：
  ┌─ 上游写入方（本脚本不负责）──────────────────────────────┐
  │  speedtest cron → slot_speed_summary / torrent_metadata   │
  │  pipeline / fuzzy   → download_resources / media_pages    │
  │  meta enrich        → media_catalog                       │
  └───────────────────────────────────────────────────────────┘
           │ 时间戳晚于 media_pages.generated_at → 脏页
           ▼
  【读】MySQL（只读检测，不改业务内容）
    - media_pages：page_id / page_status / magnet_count /
                   generated_at / updated_at / catalog_id
    - slot_speed_summary.updated_at
    - torrent_metadata.extracted_at（按 page_id）
    - download_resources.indexed_at
    - media_catalog.updated_at（经 catalog_id）
    - generate 阶段再读：上述表 + Recommended 等，供 Jinja bake
  【写】成功 bake 后
    - media_pages.generated_at / updated_at（mark_page_generated）
    - portal/dist/**（单页 HTML、Hub、home、sitemap、static 壳）
    - --report JSON（可选；检测摘要 / prepare / deploy 结果）
    - 默认 wrangler deploy → Cloudflare（--prepare-only 跳过）
  【不写】
    - 不写 slot_speed_summary / torrent_metadata / download_resources
    - 不跑 pipeline fetch / 测速；不 bump 子表时间戳

  旗标对读写的影响：
    --dry-run       只读检测；不 bake、不 mark、不上传
    --prepare-only  读 + bake（写 dist + generated_at）；不 wrangler
    （默认）        读 + bake + wrangler 上传
    --page-ids      跳过 stale 扫描，强制对指定页 bake

用法：
  cd releasematch
  # 仅检测
  python scripts/incremental_publish_worker.py --dry-run
  # 有变化则 bake + 上传
  python scripts/incremental_publish_worker.py --report worklogs/$(date +%Y-%m-%d)/incremental-publish.json
  # 当前阶段：只 bake 不上线
  python scripts/incremental_publish_worker.py --prepare-only \\
    --report /var/log/releasematch/incremental-publish.json

cron（建议紧随测速 6h，错开 30 分钟）：
  30 */6 * * * cd /opt/releasematch/releasematch && .venv/bin/python \\
    scripts/incremental_publish_worker.py --prepare-only \\
    --report /var/log/releasematch/incremental-publish.json \\
    >> /var/log/releasematch/incremental-publish-cron.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保 releasematch 根在 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow.ops.actions import (  # noqa: E402
    _run_wrangler_upload,
    prepare_dist_by_page_ids,
)
from workflow.storage.mysql_store import MySQLStore  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """
    构造增量发布 Worker CLI。

    @returns: ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="python scripts/incremental_publish_worker.py",
        description="检测脏页 → 增量 bake → 可选 wrangler 上传（cron）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="单轮最多处理槽位数；0=不截断",
    )
    parser.add_argument(
        "--page-ids",
        default=None,
        help="跳过检测，强制增量这些 page_id（逗号分隔）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只检测/列出脏页，不 bake、不上传",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="只 bake dist，不执行 wrangler deploy（CF 正式上线暂缓时推荐）",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="报告 JSON 路径",
    )
    return parser


def _parse_page_ids(raw: Optional[str]) -> List[str]:
    """
    解析逗号分隔 page_id。

    @param raw: CLI 字符串
    @returns: page_id 列表
    """
    if not raw:
        return []
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _write_report(path: Optional[str], payload: Dict[str, Any]) -> None:
    """
    将报告写入文件（可选）。

    @param path: 目标路径；空则跳过
    @param payload: JSON 可序列化 dict
    """
    if not path:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[List[str]] = None) -> int:
    """
    Worker 主入口。

    @param argv: 命令行参数
    @returns: 0 成功或无脏页；1 检测/bake/上传失败
    """
    args = build_parser().parse_args(argv)
    started = datetime.now(timezone.utc).isoformat()

    forced = _parse_page_ids(args.page_ids)
    reasons: Dict[str, str] = {}
    truncated = False
    limit = int(args.limit) if args.limit and int(args.limit) > 0 else None

    try:
        if forced:
            page_ids = forced
            for pid in page_ids:
                reasons[pid] = "forced"
            detect: Dict[str, Any] = {
                "page_ids": page_ids,
                "reasons": reasons,
                "count": len(page_ids),
                "truncated": False,
                "limit": limit,
                "mode": "forced",
            }
        else:
            store = MySQLStore()
            detect = store.list_stale_page_ids_for_regenerate(limit=limit)
            page_ids = list(detect.get("page_ids") or [])
            reasons = dict(detect.get("reasons") or {})
            truncated = bool(detect.get("truncated"))
            detect["mode"] = "stale_scan"
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "error": f"detect_failed: {exc}",
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 1

    payload: Dict[str, Any] = {
        "ok": True,
        "started_at": started,
        "detect": detect,
        "stale_count": len(page_ids),
        "page_ids": page_ids,
        "reasons": reasons,
        "truncated": truncated,
        "dry_run": bool(args.dry_run),
        "prepare_only": bool(args.prepare_only),
    }

    if not page_ids:
        payload["skipped"] = True
        payload["message"] = "无脏页，跳过 bake/deploy"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 0

    if args.dry_run:
        payload["skipped"] = True
        payload["message"] = "dry-run：仅列出脏页"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 0

    try:
        prepare = prepare_dist_by_page_ids(page_ids)
    except Exception as exc:  # noqa: BLE001
        payload["ok"] = False
        payload["error"] = f"prepare_failed: {exc}"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 1

    payload["prepare"] = {
        "ok": bool(prepare.get("ok")),
        "generate": prepare.get("generate"),
        "error": prepare.get("error"),
    }
    if not prepare.get("ok"):
        payload["ok"] = False
        payload["error"] = prepare.get("error") or "prepare failed"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 1

    if args.prepare_only:
        payload["deploy"] = {
            "skipped": True,
            "reason": "prepare_only",
        }
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 0

    deploy = _run_wrangler_upload()
    payload["deploy"] = deploy
    if not deploy.get("ok"):
        payload["ok"] = False
        payload["error"] = deploy.get("error") or "wrangler deploy failed"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(payload, ensure_ascii=False))
        _write_report(args.report, payload)
        return 1

    payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(payload, ensure_ascii=False))
    _write_report(args.report, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
