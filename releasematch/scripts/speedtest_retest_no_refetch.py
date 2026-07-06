#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
不重拉 indexer，仅重跑测速（Phase 1+2 + torrent_metadata）。

@file scripts/speedtest_retest_no_refetch.py
@description
  只读 MySQL 已有 Recommended / magnet，不调用 pipeline fetch / refetch-all。
  默认 ``--force`` 忽略 6h TTL，便于 torrent_metadata 回填或全量重测。

用法（VPS / 已配置 MySQL + libtorrent）::

  cd releasematch
  python scripts/speedtest_retest_no_refetch.py --write \\
    --report worklogs/2026-07-06/speedtest-retest-no-refetch.json

  # 仅测指定槽
  python scripts/speedtest_retest_no_refetch.py --write \\
    --page-ids tv:1396:s04e06,movie:27205

  # 测速后 regenerate 全站
  python scripts/speedtest_retest_no_refetch.py --write --generate-all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

MIGRATE_SQL = _ROOT / "schema" / "mysql_migrate_torrent_metadata.sql"


def ensure_torrent_metadata_table() -> dict:
    """
    若缺少 torrent_metadata 表则执行增量迁移 SQL。

    @returns: {applied: bool, ok: bool, detail: str}
    """
    from workflow.config import release_mysql_configured
    from workflow.storage.mysql_store import MySQLStore

    if not release_mysql_configured():
        return {"applied": False, "ok": False, "detail": "MySQL 未配置"}

    store = MySQLStore()
    ping = store.ping()
    if ping.get("ok"):
        return {"applied": False, "ok": True, "detail": "schema ok"}

    missing = ping.get("tables_missing") or []
    if "torrent_metadata" not in missing:
        return {
            "applied": False,
            "ok": False,
            "detail": f"其他表缺失: {missing}",
        }

    if not MIGRATE_SQL.is_file():
        return {"applied": False, "ok": False, "detail": f"缺少 {MIGRATE_SQL}"}

    sql_text = MIGRATE_SQL.read_text(encoding="utf-8")
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            for stmt in sql_text.split(";"):
                chunk = stmt.strip()
                if chunk and not chunk.startswith("--"):
                    cur.execute(chunk)
    finally:
        conn.close()

    ping2 = store.ping()
    ok = ping2.get("ok") or "torrent_metadata" not in (ping2.get("tables_missing") or [])
    return {"applied": True, "ok": ok, "detail": "torrent_metadata migrated" if ok else ping2}


def build_parser() -> argparse.ArgumentParser:
    """
    构造 CLI 解析器。

    @returns: ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="不重拉，仅重跑测速（--all-published 或 --page-ids）",
    )
    parser.add_argument(
        "--all-published",
        action="store_true",
        default=True,
        help="测 MySQL 全部 published 页（默认）",
    )
    parser.add_argument(
        "--page-ids",
        default=None,
        help="逗号分隔 page_id（指定时覆盖 --all-published）",
    )
    parser.add_argument("--write", action="store_true", help="写入 MySQL")
    parser.add_argument(
        "--force",
        action="store_true",
        default=True,
        help="忽略 TTL（默认开启）",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="尊重 6h TTL",
    )
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--target-bytes", type=int, default=262_144)
    parser.add_argument("--phase1-timeout", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=30, help="Phase 2 超时")
    parser.add_argument("--report", default=None, help="JSON 报告路径")
    parser.add_argument("--dry-run", action="store_true", help="无 libtorrent 占位")
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="跳过 torrent_metadata 表检查",
    )
    parser.add_argument(
        "--generate-all",
        action="store_true",
        help="测速完成后 python -m portal.generator.run generate all",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    主入口：迁移表 → 批量测速 → 可选 generate all。

    @param argv: CLI 参数
    @returns: 0 成功；1 失败
    """
    from workflow.config import release_mysql_configured
    from workflow.torrent_sources.speedtest.batch_service import (
        load_batch_targets,
        run_batch_speedtest,
        write_batch_report,
    )
    from workflow.torrent_sources.speedtest.run import _libtorrent_available

    args = build_parser().parse_args(argv)
    force = args.force and not args.no_force

    if not _libtorrent_available() and not args.dry_run:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "libtorrent 不可用；请在 VPS 运行或加 --dry-run",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    if not release_mysql_configured():
        print(
            json.dumps(
                {"ok": False, "error": "MySQL 未配置；请设置 RM_RELEASE_MYSQL_* 或 config.env"},
                ensure_ascii=False,
            )
        )
        return 1

    meta: dict = {"refetch": False, "mode": "speedtest_retest_only"}
    if not args.skip_migrate:
        mig = ensure_torrent_metadata_table()
        meta["migration"] = mig
        if not mig.get("ok") and mig.get("applied"):
            print(json.dumps({"ok": False, "meta": meta}, ensure_ascii=False, indent=2))
            return 1

    page_ids = None
    all_published = args.all_published
    if args.page_ids:
        page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()]
        all_published = False

    try:
        targets = load_batch_targets(
            page_ids=page_ids,
            all_published=all_published,
        )
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
        force=force,
        workers=args.workers,
    )
    report.setdefault("meta", {}).update(meta)
    report["meta"]["target_count"] = len(targets)
    report["meta"]["force"] = force

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        path = write_batch_report(report, str(out))
        report["meta"]["report_file"] = str(path)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    errors = report.get("summary", {}).get("errors", 0)
    if errors:
        return 1

    if args.generate_all and args.write:
        import subprocess

        gen = subprocess.run(
            [sys.executable, "-m", "portal.generator.run", "generate", "all"],
            cwd=str(_ROOT),
            check=False,
        )
        if gen.returncode != 0:
            return gen.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
