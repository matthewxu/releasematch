# -*- coding: utf-8 -*-
"""
Ops 日常运营 — 巡检汇总与按需动作。

@module workflow.ops.daily_service
@description
  对齐《12-日常运营执行手册》§四：数据源连通、DB 快照、测速覆盖、
  TMDB 日同步新鲜度、失败槽登记。供 Ops「⑥ 日常运营」面板与
  ``GET /api/daily/status`` 使用；动作入口复用 tmdb-sync / speedtest CLI。
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import PROJECT_ROOT
from workflow.ops import tmdb_export_store
from workflow.storage.failed_slots_store import (
    DEFAULT_REGISTRY_PATH,
    DEFAULT_WORKLOG_MIRROR_PATH,
    load_registry,
)
from workflow.storage.mysql_store import MySQLStore
from workflow.torrent_sources.config import (
    is_jackett_api_key_configured,
    load_accounts_config,
    probe_jackett_http,
    resolve_accounts_config_path,
)

# 本机 / VPS 常见测速 cron 日志路径（存在则展示 mtime）
_CRON_LOG_CANDIDATES: List[Path] = [
    Path("/var/log/releasematch/speedtest-cron.log"),
    Path("/var/log/releasematch/speedtest-batch.json"),
    PROJECT_ROOT / "worklogs" / "ops" / "speedtest-cron.log",
]

# worklogs 下最近测速报告 glob
_SPEEDTEST_REPORT_GLOB: str = "**/speedtest*.json"


def _utc_now_iso() -> str:
    """
    当前 UTC ISO8601 时间戳。

    @returns: 如 2026-07-21T12:00:00Z
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_mtime_iso(path: Path) -> Optional[str]:
    """
    文件修改时间转 UTC ISO 字符串。

    @param path: 文件路径
    @returns: ISO 字符串；不存在则 None
    """
    if not path.is_file():
        return None
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return None


def _check_item(
    *,
    id: str,
    label: str,
    ok: bool,
    detail: str,
    required: bool = True,
) -> Dict[str, Any]:
    """
    构造一条可勾选巡检项。

    @param id: 稳定键（如 jackett_reachable）
    @param label: 展示文案
    @param ok: 是否通过
    @param detail: 说明 / 当前值
    @param required: 是否计入「必过」汇总
    @returns: 巡检项字典
    """
    return {
        "id": id,
        "label": label,
        "ok": bool(ok),
        "detail": detail,
        "required": bool(required),
    }


def _torrent_status() -> Dict[str, Any]:
    """
    汇总 Jackett / accounts 连通状态（等同 ``torrent_sources.run status`` 核心字段）。

    @returns: jackett_base_url / has_valid_api_key / jackett_probe 等
    """
    cfg_path = resolve_accounts_config_path(None)
    cfg = load_accounts_config(cfg_path)
    jackett = cfg.get("jackett") or {}
    api_key = str(jackett.get("api_key") or "")
    base_url = str(jackett.get("base_url") or "")
    probe: Optional[Dict[str, Any]] = None
    if base_url:
        try:
            probe = probe_jackett_http(base_url)
        except Exception as exc:  # noqa: BLE001 — 巡检不因探针异常中断
            probe = {"reachable": False, "error": str(exc)}
    return {
        "accounts_config": str(cfg_path),
        "accounts_local_exists": cfg_path.name == "accounts.local.json",
        "jackett_base_url": base_url,
        "has_api_key": bool(api_key),
        "has_valid_api_key": is_jackett_api_key_configured(api_key),
        "jackett_probe": probe,
    }


def _db_snapshot(store: MySQLStore) -> Dict[str, Any]:
    """
    MySQL ping + 行数 + 台账统计。

    @param store: MySQLStore
    @returns: ping / row_counts / inventory
    """
    ping = store.ping()
    out: Dict[str, Any] = {"ping": ping}
    if not ping.get("ok"):
        out["row_counts"] = {}
        out["inventory"] = {"ok": False}
        return out
    try:
        out["row_counts"] = store.count_rows()
    except Exception as exc:  # noqa: BLE001
        out["row_counts"] = {}
        out["row_counts_error"] = str(exc)
    try:
        out["inventory"] = {"ok": True, **store.page_inventory_stats()}
    except Exception as exc:  # noqa: BLE001
        out["inventory"] = {"ok": False, "error": str(exc)}
    return out


def _speed_coverage(store: MySQLStore) -> Dict[str, Any]:
    """
    有 Recommended 的 published 页中，已写入 ``slot_speed_summary`` 的覆盖率。

    @param store: MySQLStore
    @returns: with_rec / with_summary / gaps_sample / coverage_ratio
    @description
      对齐手册 §4.2「有 Rec 页均有 summary」。Hub 页不计入分母。
    """
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.page_id,
                       EXISTS (
                         SELECT 1 FROM slot_speed_summary s
                         WHERE s.page_id = p.page_id
                       ) AS has_summary
                FROM media_pages p
                WHERE p.page_status = 'published'
                  AND p.magnet_count >= 2
                  AND p.page_type IN ('episode', 'movie')
                  AND EXISTS (
                    SELECT 1 FROM download_resources d
                    WHERE d.page_id = p.page_id AND d.is_recommended = 1
                  )
                ORDER BY p.page_id
                """
            )
            rows = cur.fetchall() or []
    finally:
        conn.close()

    with_rec = len(rows)
    with_summary = sum(1 for r in rows if int(r.get("has_summary") or 0))
    gaps = [str(r["page_id"]) for r in rows if not int(r.get("has_summary") or 0)]
    ratio = (with_summary / with_rec) if with_rec else 1.0
    return {
        "with_recommended": with_rec,
        "with_summary": with_summary,
        "gap_count": len(gaps),
        "gaps_sample": gaps[:20],
        "coverage_ratio": round(ratio, 4),
        "ok": with_rec == 0 or with_summary == with_rec,
    }


def _failed_slots_snapshot() -> Dict[str, Any]:
    """
    失败槽登记册摘要（优先 data/，回退 worklogs 镜像）。

    @returns: active_count / resolved_count / path
    """
    path = DEFAULT_REGISTRY_PATH
    if not path.is_file() and DEFAULT_WORKLOG_MIRROR_PATH.is_file():
        path = DEFAULT_WORKLOG_MIRROR_PATH
    registry = load_registry(path)
    meta = registry.get("meta") or {}
    active = registry.get("active") or {}
    return {
        "ok": True,
        "path": str(path),
        "active_count": int(meta.get("active_count") or len(active)),
        "resolved_count": int(meta.get("resolved_count") or len(registry.get("resolved") or {})),
        "sample_keys": list(active.keys())[:10],
    }


def _tmdb_export_snapshot() -> Dict[str, Any]:
    """
    TMDB Daily Export 入库新鲜度（``tmdb_export_titles`` meta）。

    @returns: ready / export_date / movie_count / tv_count / stale_hint
    """
    try:
        meta = tmdb_export_store.meta_summary()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "ready": False, "error": str(exc)}

    export_date = str(meta.get("export_date") or "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # 日导出通常滞后 1 天；超过 3 天视为偏旧
    stale = False
    age_days: Optional[int] = None
    if export_date:
        try:
            ed = datetime.strptime(export_date[:10], "%Y-%m-%d").date()
            age_days = (datetime.now(timezone.utc).date() - ed).days
            stale = age_days > 3
        except ValueError:
            stale = True
    else:
        stale = True

    return {
        "ok": bool(meta.get("ready")) and not stale,
        "ready": bool(meta.get("ready")),
        "export_date": export_date or None,
        "movie_count": int(meta.get("movie_count") or 0),
        "tv_count": int(meta.get("tv_count") or 0),
        "loaded_at": meta.get("loaded_at"),
        "ingest_mode": meta.get("ingest_mode"),
        "age_days": age_days,
        "stale": stale,
        "today_utc": today,
    }


def _cron_log_snapshot() -> Dict[str, Any]:
    """
    探测本机可见的测速 cron 日志 / 最近报告（VPS 路径在本机常不存在）。

    @returns: found / candidates / latest_report
    """
    found: List[Dict[str, Any]] = []
    for path in _CRON_LOG_CANDIDATES:
        mtime = _file_mtime_iso(path)
        if mtime:
            found.append(
                {
                    "path": str(path),
                    "mtime": mtime,
                    "size": path.stat().st_size,
                }
            )

    latest_report: Optional[Dict[str, Any]] = None
    worklogs = PROJECT_ROOT / "worklogs"
    if worklogs.is_dir():
        reports = sorted(
            worklogs.glob(_SPEEDTEST_REPORT_GLOB),
            key=lambda p: p.stat().st_mtime if p.is_file() else 0,
            reverse=True,
        )
        for rep in reports[:1]:
            latest_report = {
                "path": str(rep.relative_to(PROJECT_ROOT)),
                "mtime": _file_mtime_iso(rep),
                "size": rep.stat().st_size,
            }
            # 尝试读 ok/total
            try:
                data = json.loads(rep.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    latest_report["ok_count"] = data.get("ok") or data.get("ok_count")
                    latest_report["total"] = data.get("total") or data.get("slot_count")
            except (OSError, json.JSONDecodeError, TypeError):
                pass

    return {
        "ok": bool(found) or bool(latest_report),
        "note": (
            "本机未找到 /var/log/releasematch 日志时属正常；"
            "VPS cron 请 SSH 查 tail -50 /var/log/releasematch/speedtest-cron.log"
            if not found
            else "已找到本机 cron 相关文件"
        ),
        "candidates_found": found,
        "latest_report": latest_report,
    }


def collect_daily_patrol() -> Dict[str, Any]:
    """
    一键汇总日常巡检（手册 §四 + TMDB 日同步）。

    @returns: ok / checks / sections / collected_at
    """
    torrent = _torrent_status()
    probe = torrent.get("jackett_probe") or {}
    jackett_ok = bool(torrent.get("has_valid_api_key")) and bool(
        probe.get("reachable")
    )

    db: Dict[str, Any] = {"ping": {"ok": False}}
    speed: Dict[str, Any] = {
        "ok": False,
        "with_recommended": 0,
        "with_summary": 0,
        "gap_count": 0,
        "gaps_sample": [],
        "coverage_ratio": 0,
    }
    store_error: Optional[str] = None
    try:
        store = MySQLStore()
        db = _db_snapshot(store)
        if db.get("ping", {}).get("ok"):
            speed = _speed_coverage(store)
    except Exception as exc:  # noqa: BLE001
        store_error = str(exc)
        db = {"ping": {"ok": False, "error": store_error}, "row_counts": {}, "inventory": {}}

    failed = _failed_slots_snapshot()
    tmdb = _tmdb_export_snapshot()
    cron = _cron_log_snapshot()

    ping_ok = bool((db.get("ping") or {}).get("ok"))
    checks = [
        _check_item(
            id="jackett_reachable",
            label="Jackett 可达（jackett_probe.reachable）",
            ok=jackett_ok,
            detail=(
                f"url={torrent.get('jackett_base_url') or '—'} · "
                f"key={'valid' if torrent.get('has_valid_api_key') else 'missing'} · "
                f"probe={probe}"
            ),
        ),
        _check_item(
            id="db_ping",
            label="MySQL ping.ok",
            ok=ping_ok,
            detail=json.dumps(db.get("ping") or {}, ensure_ascii=False)[:400],
        ),
        _check_item(
            id="speed_coverage",
            label="测速覆盖：有 Rec 的 published 均有 summary",
            ok=bool(speed.get("ok")),
            detail=(
                f"{speed.get('with_summary')}/{speed.get('with_recommended')} · "
                f"缺口 {speed.get('gap_count')}"
            ),
        ),
        _check_item(
            id="tmdb_export",
            label="TMDB 标题库日同步新鲜（export_date ≤3 天）",
            ok=bool(tmdb.get("ok")),
            detail=(
                f"ready={tmdb.get('ready')} · date={tmdb.get('export_date')} · "
                f"age_days={tmdb.get('age_days')} · "
                f"movie={tmdb.get('movie_count')} tv={tmdb.get('tv_count')}"
            ),
        ),
        _check_item(
            id="cron_evidence",
            label="测速 cron / 最近报告可见（本机或 worklogs）",
            ok=bool(cron.get("ok")),
            detail=str(cron.get("note") or ""),
            required=False,
        ),
        _check_item(
            id="failed_slots",
            label="失败槽登记册可读",
            ok=bool(failed.get("ok")),
            detail=f"active={failed.get('active_count')} · path={failed.get('path')}",
            required=False,
        ),
    ]

    required = [c for c in checks if c.get("required")]
    all_required_ok = all(bool(c.get("ok")) for c in required)

    return {
        "ok": True,
        "patrol_ok": all_required_ok,
        "collected_at": _utc_now_iso(),
        "handbook_ref": "docs/12-日常运营执行手册.md §四",
        "checks": checks,
        "torrent": torrent,
        "db": db,
        "speed": speed,
        "tmdb_export": tmdb,
        "failed_slots": failed,
        "cron": cron,
        "store_error": store_error,
    }


def list_speed_summary_gaps(*, limit: int = 50) -> Dict[str, Any]:
    """
    列出有 Rec 但缺 ``slot_speed_summary`` 的 page_id。

    @param limit: 最多返回条数
    @returns: ok / page_ids / total_gaps
    """
    store = MySQLStore()
    cov = _speed_coverage(store)
    gaps = list(cov.get("gaps_sample") or [])
    # gaps_sample 已截断 20；若需更多再查一遍
    if cov.get("gap_count", 0) > len(gaps):
        conn = store._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.page_id
                    FROM media_pages p
                    WHERE p.page_status = 'published'
                      AND p.magnet_count >= 2
                      AND p.page_type IN ('episode', 'movie')
                      AND EXISTS (
                        SELECT 1 FROM download_resources d
                        WHERE d.page_id = p.page_id AND d.is_recommended = 1
                      )
                      AND NOT EXISTS (
                        SELECT 1 FROM slot_speed_summary s
                        WHERE s.page_id = p.page_id
                      )
                    ORDER BY p.page_id
                    LIMIT %s
                    """,
                    (int(limit),),
                )
                gaps = [str(r["page_id"]) for r in (cur.fetchall() or [])]
        finally:
            conn.close()
    else:
        gaps = gaps[: int(limit)]
    return {
        "ok": True,
        "total_gaps": int(cov.get("gap_count") or 0),
        "page_ids": gaps,
        "coverage": cov,
    }


def run_speedtest_gap_fill(
    *,
    limit: int = 20,
    workers: int = 3,
) -> Dict[str, Any]:
    """
    对测速缺口槽位跑 batch write（子进程），成功后不强制全站 generate。

    @param limit: 最多补测槽数
    @param workers: 并行 worker（传给 speedtest CLI 若支持；否则忽略）
    @returns: ok / page_ids / report_path / detail
    @description
      日常缺口补测用；全量仍走 cron ``--all-published``。
      测速后单页 regenerate 由运维在③段或 CLI 完成（缺口多为新扩槽）。
    """
    gaps = list_speed_summary_gaps(limit=limit)
    page_ids = list(gaps.get("page_ids") or [])
    if not page_ids:
        return {
            "ok": True,
            "skipped": True,
            "message": "无测速缺口",
            "page_ids": [],
        }

    report_dir = PROJECT_ROOT / "worklogs" / "ops"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"speedtest-gap-{stamp}.json"
    cmd = [
        sys.executable,
        "-m",
        "workflow.torrent_sources.speedtest.run",
        "batch",
        "--page-ids",
        ",".join(page_ids),
        "--write",
        "--report",
        str(report_path),
    ]
    # workers 参数：batch CLI 若支持则附带
    if workers and workers > 1:
        cmd.extend(["--workers", str(int(workers))])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "page_ids": page_ids,
            "cmd": cmd,
        }

    ok = proc.returncode == 0
    detail = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-800:]
    return {
        "ok": ok,
        "page_ids": page_ids,
        "report_path": str(report_path.relative_to(PROJECT_ROOT)),
        "returncode": proc.returncode,
        "detail": detail,
        "hint": "测速写入后请对缺口页执行 generate page（或③段 Generate 选中页）",
    }
