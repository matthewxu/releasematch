# -*- coding: utf-8 -*-
"""
批量槽位测速编排（策略 A2）与 TTL 跳过。

@module workflow.torrent_sources.speedtest.batch_service
@description
  支持 --page-ids / --slots-json 输入、串行或进程池并发、
  6h TTL 跳过已测 hash，输出 JSON 报告。
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from schema.d1_models import build_page_id

# 策略 A2：256KB 片段测速（cron 默认）
DEFAULT_BATCH_TARGET_BYTES = 262_144
# 增量测速 TTL（小时），与 torrent seeders 缓存对齐
DEFAULT_SPEEDTEST_TTL_HOURS = 6


def _parse_mysql_utc(ts: str) -> Optional[datetime]:
    """
    解析 MySQL DATETIME 字符串为 UTC aware datetime。

    @param ts: 如 2026-07-02 12:00:00.000
    @returns: datetime 或 None（空串）
    """
    text = (ts or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def resolve_page_id_from_slot(slot: Dict[str, Any]) -> str:
    """
    从 benchmark 槽位 JSON 条目解析 page_id。

    @param slot: 含 tmdb_id、media_type、season、episode
    @returns: 如 tv:1396:s04e06 或 movie:27205
    """
    tmdb_id = int(slot["tmdb_id"])
    media_type = str(slot.get("media_type") or "tv").lower()
    if media_type == "movie":
        return build_page_id(tmdb_id, "movie", page_type="movie")
    season = int(slot.get("season") or 0)
    episode = int(slot.get("episode") or 0)
    return build_page_id(tmdb_id, "tv", season=season, episode=episode)


def load_published_page_targets() -> List[Dict[str, Any]]:
    """
    从 MySQL 加载所有可发布页（published 且 magnet≥2）作为 batch 目标。

    @returns: 含 label、page_id 的字典列表
    """
    from workflow.storage.mysql_store import MySQLStore

    store = MySQLStore()
    page_ids = store.list_published_page_ids()
    return [{"label": pid, "page_id": pid} for pid in page_ids]


def load_batch_targets(
    *,
    page_ids: Optional[List[str]] = None,
    slots_json: Optional[str] = None,
    all_published: bool = False,
) -> List[Dict[str, Any]]:
    """
    加载批量测速目标列表。

    @param page_ids: 直接指定的 page_id 列表
    @param slots_json: benchmark 槽位 JSON 文件路径
    @param all_published: True 时从 MySQL 拉取全部 published 页
    @returns: 含 label、page_id 的字典列表
    @raises ValueError: 输入无效或三者皆空
    """
    targets: List[Dict[str, Any]] = []

    if all_published:
        targets.extend(load_published_page_targets())

    if page_ids:
        for pid in page_ids:
            pid = str(pid).strip()
            if pid:
                targets.append({"label": pid, "page_id": pid})

    if slots_json:
        path = Path(slots_json)
        if not path.is_file():
            raise ValueError(f"slots JSON 不存在: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("slots JSON 必须是数组")
        for item in raw:
            if not isinstance(item, dict):
                continue
            page_id = resolve_page_id_from_slot(item)
            targets.append(
                {
                    "label": str(item.get("label") or page_id),
                    "page_id": page_id,
                }
            )

    if not targets:
        raise ValueError("请指定 --page-ids、--slots-json 或 --all-published")

    # 去重，保留首次出现顺序
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for row in targets:
        pid = row["page_id"]
        if pid in seen:
            continue
        seen.add(pid)
        unique.append(row)
    return unique


def check_skip_ttl(
    page_id: str,
    *,
    ttl_hours: int,
    force: bool,
) -> Optional[Dict[str, Any]]:
    """
    若 slot_speed_summary 在 TTL 内且 infohash 未变，返回 skipped_ttl 摘要。

    @param page_id: 页面槽位 ID
    @param ttl_hours: TTL 小时数；≤0 时不跳过
    @param force: True 时强制重测
    @returns: 跳过时的结果 dict；需测速时返回 None
    """
    if force or ttl_hours <= 0:
        return None

    from workflow.config import release_mysql_configured
    from workflow.storage.mysql_store import MySQLStore

    if not release_mysql_configured():
        return None

    store = MySQLStore()
    recommended = store.get_recommended_resource(page_id)
    if not recommended:
        return {
            "page_id": page_id,
            "label": page_id,
            "status": "skipped",
            "reason": "no_recommended",
            "elapsed_sec": 0.0,
        }

    summary = store.get_slot_speed_summary(page_id)
    if not summary or not summary.updated_at:
        return None

    infohash = recommended.infohash.lower()
    if summary.recommended_infohash.lower() != infohash:
        return None

    tested_at = _parse_mysql_utc(summary.updated_at)
    if not tested_at:
        return None

    age_sec = (datetime.now(timezone.utc) - tested_at).total_seconds()
    if age_sec > ttl_hours * 3600:
        return None

    return {
        "page_id": page_id,
        "label": page_id,
        "status": "skipped_ttl",
        "reason": f"fresh_within_{ttl_hours}h",
        "elapsed_sec": 0.0,
        "recommended_speed": summary.recommended_speed,
        "reachability": summary.reachability,
        "summary_updated_at": summary.updated_at,
        "recommended_infohash": infohash,
    }


def run_single_batch_slot(
    page_id: str,
    *,
    label: str = "",
    phase1_timeout_sec: int = 20,
    phase2_timeout_sec: int = 30,
    target_bytes: int = DEFAULT_BATCH_TARGET_BYTES,
    force_dry_run: bool = False,
    write_mysql: bool = False,
    ttl_hours: int = DEFAULT_SPEEDTEST_TTL_HOURS,
    force: bool = False,
) -> Dict[str, Any]:
    """
    对单个 page_id 执行槽位测速（含 TTL 跳过）。

    @param page_id: 如 tv:1396:s04e06
    @param label: 报告展示名
    @param phase1_timeout_sec: Phase 1 超时
    @param phase2_timeout_sec: Phase 2 超时
    @param target_bytes: Phase 2 目标字节
    @param force_dry_run: 不联网 dry-run
    @param write_mysql: 写入 MySQL
    @param ttl_hours: TTL 小时；配合 force 控制跳过
    @param force: 忽略 TTL
    @returns: 单槽结果摘要
    """
    from workflow.torrent_sources.speedtest.store_service import speedtest_recommended_slot

    display = label or page_id
    started = time.monotonic()

    skipped = check_skip_ttl(page_id, ttl_hours=ttl_hours, force=force)
    if skipped:
        skipped["label"] = display
        return skipped

    try:
        payload = speedtest_recommended_slot(
            page_id,
            phase1_timeout_sec=phase1_timeout_sec,
            phase2_timeout_sec=phase2_timeout_sec,
            target_bytes=target_bytes,
            force_dry_run=force_dry_run,
            write_mysql=write_mysql,
        )
    except RuntimeError as exc:
        return {
            "page_id": page_id,
            "label": display,
            "status": "error",
            "error": str(exc),
            "elapsed_sec": round(time.monotonic() - started, 3),
        }

    speedtest = payload.get("speedtest") or {}
    phase1 = speedtest.get("phase1") or {}
    phase2 = speedtest.get("phase2") or {}
    phase2_status = phase2.get("status", "ok")
    overall_status = phase2_status if phase2_status == "error" else phase1.get("status", "ok")

    return {
        "page_id": page_id,
        "label": display,
        "status": overall_status,
        "elapsed_sec": round(time.monotonic() - started, 3),
        "phase1_elapsed_ms": phase1.get("elapsed_ms"),
        "phase2_elapsed_ms": phase2.get("elapsed_ms"),
        "peers_total": phase2.get("peers_total") or phase1.get("peers_total"),
        "avg_kbps": phase2.get("avg_kbps"),
        "max_kbps": phase2.get("max_kbps"),
        "recommended_speed": speedtest.get("recommended_speed"),
        "reachability": speedtest.get("reachability"),
        "write": payload.get("write"),
    }


def _batch_slot_worker(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    进程池 worker 入口（须为模块级函数以便 pickle）。

    @param task: run_single_batch_slot 参数字典
    @returns: 单槽结果
    """
    page_id = task.pop("page_id")
    label = task.pop("label", page_id)
    return run_single_batch_slot(page_id, label=label, **task)


def run_batch_speedtest(
    targets: List[Dict[str, Any]],
    *,
    phase1_timeout_sec: int = 20,
    phase2_timeout_sec: int = 30,
    target_bytes: int = DEFAULT_BATCH_TARGET_BYTES,
    force_dry_run: bool = False,
    write_mysql: bool = False,
    ttl_hours: int = DEFAULT_SPEEDTEST_TTL_HOURS,
    force: bool = False,
    workers: int = 1,
) -> Dict[str, Any]:
    """
    批量槽位测速，串行或进程池并发。

    @param targets: load_batch_targets 返回的列表
    @param phase1_timeout_sec: Phase 1 超时
    @param phase2_timeout_sec: Phase 2 超时
    @param target_bytes: Phase 2 目标字节
    @param force_dry_run: dry-run 模式
    @param write_mysql: 批量写库
    @param ttl_hours: TTL 跳过小时数
    @param force: 强制重测
    @param workers: 并发进程数（1=串行）
    @returns: 完整 JSON 报告
    """
    started_at = datetime.now(timezone.utc).isoformat()
    wall_start = time.monotonic()

    common_kwargs = {
        "phase1_timeout_sec": phase1_timeout_sec,
        "phase2_timeout_sec": phase2_timeout_sec,
        "target_bytes": target_bytes,
        "force_dry_run": force_dry_run,
        "write_mysql": write_mysql,
        "ttl_hours": ttl_hours,
        "force": force,
    }

    results: List[Dict[str, Any]] = []

    if workers <= 1:
        for row in targets:
            results.append(
                run_single_batch_slot(
                    row["page_id"],
                    label=row.get("label") or row["page_id"],
                    **common_kwargs,
                )
            )
    else:
        tasks = [
            {
                "page_id": row["page_id"],
                "label": row.get("label") or row["page_id"],
                **common_kwargs,
            }
            for row in targets
        ]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_batch_slot_worker, dict(t)): t for t in tasks}
            for fut in as_completed(futures):
                results.append(fut.result())

        # 按原始 targets 顺序排序
        order = {row["page_id"]: idx for idx, row in enumerate(targets)}
        results.sort(key=lambda r: order.get(r.get("page_id", ""), 999))

    wall_sec = round(time.monotonic() - wall_start, 3)
    ok_statuses = {"ok", "dry_run", "timeout", "skipped", "skipped_ttl"}
    error_count = sum(1 for r in results if r.get("status") not in ok_statuses)
    skipped_ttl_count = sum(1 for r in results if r.get("status") == "skipped_ttl")

    return {
        "meta": {
            "strategy": "A2",
            "target_bytes": target_bytes,
            "phase1_timeout_sec": phase1_timeout_sec,
            "phase2_timeout_sec": phase2_timeout_sec,
            "workers": workers,
            "write_mysql": write_mysql,
            "ttl_hours": ttl_hours,
            "force": force,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "total_wall_sec": wall_sec,
            "slot_count": len(targets),
            "estimated_serial_a2_sec": round(len(targets) * 25, 1),
        },
        "summary": {
            "succeeded": len(results) - error_count,
            "errors": error_count,
            "skipped_ttl": skipped_ttl_count,
        },
        "results": results,
    }


def write_batch_report(report: Dict[str, Any], report_path: str) -> Path:
    """
    将批量报告写入 JSON 文件。

    @param report: run_batch_speedtest 返回值
    @param report_path: 输出路径
    @returns: 写入的 Path
    """
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
