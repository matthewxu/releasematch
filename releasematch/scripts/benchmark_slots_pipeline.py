#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多槽位 pipeline + 静态页生成耗时基准测试。

@file scripts/benchmark_slots_pipeline.py
@description
  对每个槽位串行执行：
    1. run_slot_pipeline（live + fetch：拉取 → 评分 → 写 MySQL）
    2. write_page_html（MySQL → portal/dist HTML）
  记录各阶段与总耗时，输出 JSON 报告。

  用法：
    cd releasematch
    python scripts/benchmark_slots_pipeline.py
    python scripts/benchmark_slots_pipeline.py --force
    python scripts/benchmark_slots_pipeline.py --slots worklogs/benchmark-slots.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from portal.generator.generate_one import DEFAULT_OUT_ROOT, write_page_html
from workflow.storage.mysql_store import MySQLStore
from workflow.storage.pipeline import run_slot_pipeline

# 默认基准槽位：Breaking Bad S04 部分集 + Inception 电影（均在 mysql_seed_demo 中）
DEFAULT_BENCHMARK_SLOTS: List[Dict[str, Any]] = [
    {"label": "BB S04E01", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 1},
    {"label": "BB S04E02", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 2},
    {"label": "BB S04E04", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 4},
    {"label": "BB S04E06", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 6},
    {"label": "BB S04E07", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 7},
    {"label": "BB S04E08", "tmdb_id": 1396, "media_type": "tv", "season": 4, "episode": 8},
    {"label": "Inception", "tmdb_id": 27205, "media_type": "movie"},
]


@dataclass
class SlotTimingResult:
    """
    单槽位耗时与结果摘要。

    @var label: 人类可读标签
    @var page_id: 页面 ID
    @var pipeline_sec: pipeline 阶段秒数
    @var generate_sec: HTML 生成秒数
    @var total_sec: 总秒数（pipeline + generate）
    @var pipeline_ok: pipeline 是否成功
    @var generate_ok: 页面生成是否成功
    @var magnet_count: 写入 magnet 条数
    @var fetch_note: 拉取说明
    @var output_file: 生成的 HTML 路径
    @var error: 失败时的错误信息
    """

    label: str
    page_id: str
    pipeline_sec: float
    generate_sec: float
    total_sec: float
    pipeline_ok: bool = False
    generate_ok: bool = False
    magnet_count: int = 0
    fetch_note: Optional[str] = None
    output_file: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BenchmarkReport:
    """
    多槽位基准测试汇总。

    @var started_at: UTC ISO 开始时间
    @var finished_at: UTC ISO 结束时间
    @var total_wall_sec: 整批 wall clock 秒数
    @var slot_count: 槽位数
    @var succeeded: 成功数（pipeline + generate 均 ok）
    @var failed: 失败数
    @var results: 各槽明细
    @var force_fetch: 是否强制忽略 torrent 缓存
    """

    started_at: str
    finished_at: str = ""
    total_wall_sec: float = 0.0
    slot_count: int = 0
    succeeded: int = 0
    failed: int = 0
    force_fetch: bool = False
    results: List[SlotTimingResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_wall_sec": round(self.total_wall_sec, 3),
            "slot_count": self.slot_count,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "force_fetch": self.force_fetch,
            "results": [asdict(r) for r in self.results],
        }


def _utc_now_iso() -> str:
    """返回当前 UTC ISO8601 字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_slots(path: Optional[Path]) -> List[Dict[str, Any]]:
    """
    加载槽位列表。

    @param path: JSON 文件路径；None 时使用 DEFAULT_BENCHMARK_SLOTS
    @returns: 槽位字典列表
    """
    if path is None:
        return list(DEFAULT_BENCHMARK_SLOTS)
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("slots JSON 必须是数组")
    return raw


def _run_one_slot(
    slot: Dict[str, Any],
    out_root: Path,
    force_fetch: bool,
) -> SlotTimingResult:
    """
    执行单槽 pipeline + generate 并计时。

    @param slot: 含 tmdb_id、media_type、season、episode、label
    @param out_root: HTML 输出根目录
    @param force_fetch: 是否强制重新拉取 torrent（忽略缓存）
    @returns: SlotTimingResult
    """
    label = str(slot.get("label") or slot.get("page_id") or slot["tmdb_id"])
    tmdb_id = int(slot["tmdb_id"])
    media_type = str(slot.get("media_type") or "tv")
    season = slot.get("season")
    episode = slot.get("episode")

    store = MySQLStore()
    page_id = store.resolve_page_id(tmdb_id, media_type, season, episode)

    t0 = time.perf_counter()

    # --- pipeline：fetch + rank + MySQL ---
    t_pipe_start = time.perf_counter()
    if force_fetch:
        pipe_result = _run_pipeline_with_force(
            tmdb_id=tmdb_id,
            media_kind=media_type,
            season=season,
            episode=episode,
        )
    else:
        pipe_result = run_slot_pipeline(
            tmdb_id=tmdb_id,
            media_kind=media_type,
            season=season,
            episode=episode,
            mode="live",
            fetch=True,
        )
    pipeline_sec = time.perf_counter() - t_pipe_start

    if not pipe_result.get("ok"):
        total_sec = time.perf_counter() - t0
        return SlotTimingResult(
            label=label,
            page_id=page_id,
            pipeline_sec=round(pipeline_sec, 3),
            generate_sec=0.0,
            total_sec=round(total_sec, 3),
            error=str(pipe_result.get("error") or pipe_result),
        )

    magnet_count = int((pipe_result.get("write") or {}).get("magnet_count") or 0)
    fetch_note = pipe_result.get("fetch_note")

    # --- generate：MySQL → HTML ---
    t_gen_start = time.perf_counter()
    gen_result = write_page_html(page_id, out_root=out_root)
    generate_sec = time.perf_counter() - t_gen_start
    total_sec = time.perf_counter() - t0

    generate_ok = bool(gen_result.get("ok"))
    error = None if generate_ok else str(gen_result.get("error"))

    return SlotTimingResult(
        label=label,
        page_id=page_id,
        pipeline_sec=round(pipeline_sec, 3),
        generate_sec=round(generate_sec, 3),
        total_sec=round(total_sec, 3),
        pipeline_ok=True,
        generate_ok=generate_ok,
        magnet_count=magnet_count,
        fetch_note=fetch_note,
        output_file=gen_result.get("output_file") if generate_ok else None,
        error=error,
    )


def _run_pipeline_with_force(
    tmdb_id: int,
    media_kind: str,
    season: Optional[int],
    episode: Optional[int],
) -> Dict[str, Any]:
    """
    与 run_slot_pipeline 相同，但 FetchRequest.force=True 忽略缓存。

    @param tmdb_id: TMDB ID
    @param media_kind: tv | movie
    @param season: 季号
    @param episode: 集号
    @returns: pipeline 结果字典
    """
    import uuid

    from workflow.config import STORAGE_BACKEND
    from workflow.metadata.external_ids import resolve_external_ids
    from workflow.recommended.scorer import rank_items
    from workflow.storage.pipeline import _demo_items_for_slot
    from workflow.torrent_sources.fetch_service import FetchService
    from workflow.torrent_sources.models import FetchMode, FetchRequest, MediaType

    if STORAGE_BACKEND != "mysql":
        return {"ok": False, "error": f"STORAGE_BACKEND={STORAGE_BACKEND}"}

    store = MySQLStore()
    ping = store.ping()
    if not ping.get("ok"):
        return {"ok": False, "step": "db_ping", "detail": ping}

    media_type = "tv_episode" if media_kind == "tv" else "movie"
    page_id = store.resolve_page_id(tmdb_id, media_kind, season, episode)

    ext = resolve_external_ids(tmdb_id=tmdb_id, media_type=media_kind)
    mt = MediaType.MOVIE if media_kind == "movie" else MediaType.TV
    request = FetchRequest(
        tmdb_id=tmdb_id,
        media_type=mt,
        season=season,
        episode=episode,
        imdb_id=ext.get("imdb_id"),
        tvdb_id=ext.get("tvdb_id"),
        mode=FetchMode.ON_DEMAND,
        force=True,
    )
    fetch_result = FetchService().fetch_slot(request)
    cross_source_page_count = fetch_result.cross_source_page_count
    cross_source_page_total = fetch_result.cross_source_page_total
    fetch_note = ""

    if fetch_result.error:
        fetch_note = f"torrent 拉取失败: {fetch_result.error}；回退 demo"
        items = _demo_items_for_slot(tmdb_id, season, episode)
        cross_source_page_count = None
        cross_source_page_total = None
    elif not fetch_result.items:
        fetch_note = "torrent 拉取 0 条；回退 demo"
        items = _demo_items_for_slot(tmdb_id, season, episode)
        cross_source_page_count = None
        cross_source_page_total = None
    else:
        fetch_note = (
            f"torrent 拉取 {len(fetch_result.items)} 条"
            f"（cached={fetch_result.cached}，"
            f"跨源 {fetch_result.cross_source_page_count}/"
            f"{fetch_result.cross_source_page_total}）"
        )
        items = [i.to_dict() for i in fetch_result.items]

    if not items:
        return {
            "ok": False,
            "page_id": page_id,
            "error": "无可用 items",
        }

    ranked = rank_items(items)
    write_result = store.upsert_slot_resources(
        page_id=page_id,
        tmdb_id=tmdb_id,
        media_type=media_type,
        season=season,
        episode=episode,
        items=items,
        ranked=ranked,
        cross_source_page_count=cross_source_page_count,
        cross_source_page_total=cross_source_page_total,
    )

    run_id = str(uuid.uuid4())
    store.record_sync_run(
        run_id=run_id,
        source="pipeline_fetch",
        slots_processed=1,
        resources_upserted=write_result["resources_upserted"],
        pages_published=1 if write_result["magnet_count"] >= 2 else 0,
    )

    return {
        "ok": True,
        "page_id": page_id,
        "fetch_note": fetch_note,
        "write": write_result,
        "sync_run_id": run_id,
    }


def run_benchmark(
    slots: List[Dict[str, Any]],
    out_root: Path,
    force_fetch: bool,
) -> BenchmarkReport:
    """
    串行跑多槽基准测试。

    @param slots: 槽位列表
    @param out_root: HTML 输出目录
    @param force_fetch: 是否 force 拉取
    @returns: BenchmarkReport
    """
    report = BenchmarkReport(
        started_at=_utc_now_iso(),
        slot_count=len(slots),
        force_fetch=force_fetch,
    )
    wall_start = time.perf_counter()

    for slot in slots:
        result = _run_one_slot(slot, out_root=out_root, force_fetch=force_fetch)
        report.results.append(result)
        if result.pipeline_ok and result.generate_ok:
            report.succeeded += 1
        else:
            report.failed += 1

    report.total_wall_sec = time.perf_counter() - wall_start
    report.finished_at = _utc_now_iso()
    return report


def _print_table(report: BenchmarkReport) -> None:
    """
    打印人类可读耗时表。

    @param report: BenchmarkReport
    """
    print("\n=== 槽位 pipeline → 页面生成 耗时 ===\n")
    header = f"{'槽位':<14} {'page_id':<22} {'pipeline':>10} {'generate':>10} {'total':>10} {'magnets':>8} {'状态':>6}"
    print(header)
    print("-" * len(header))
    for r in report.results:
        status = "OK" if r.pipeline_ok and r.generate_ok else "FAIL"
        print(
            f"{r.label:<14} {r.page_id:<22} {r.pipeline_sec:>8.1f}s {r.generate_sec:>8.1f}s "
            f"{r.total_sec:>8.1f}s {r.magnet_count:>8} {status:>6}"
        )
    print("-" * len(header))
    print(
        f"合计 {report.slot_count} 槽 | 成功 {report.succeeded} | 失败 {report.failed} | "
        f"总 wall {report.total_wall_sec:.1f}s | force={report.force_fetch}"
    )


def main(argv: Optional[List[str]] = None) -> int:
    """
    CLI 入口。

    @param argv: 命令行参数
    @returns: 退出码
    """
    parser = argparse.ArgumentParser(description="多槽位 pipeline + 页面生成耗时基准")
    parser.add_argument(
        "--slots",
        default=None,
        help="槽位 JSON 数组路径；默认内置 BB S04 + Inception",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新拉取 torrent（忽略 6h 缓存）",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="HTML 输出根目录，默认 portal/dist",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="JSON 报告输出路径；默认 worklogs/YYYY-MM-DD/slot-pipeline-benchmark.json",
    )
    args = parser.parse_args(argv)

    slots_path = Path(args.slots) if args.slots else None
    slots = _load_slots(slots_path)
    out_root = Path(args.out) if args.out else DEFAULT_OUT_ROOT

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = (
        Path(args.report)
        if args.report
        else _ROOT / "worklogs" / today / "slot-pipeline-benchmark.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = run_benchmark(slots, out_root=out_root, force_fetch=args.force)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _print_table(report)
    print(f"\n报告已写入: {report_path}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
