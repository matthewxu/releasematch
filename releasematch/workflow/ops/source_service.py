# -*- coding: utf-8 -*-
"""
Ops 第一段：清单从哪来。

@module workflow.ops.source_service
@description
  支持 TMDB 日导出+锚点/curated 生成、加载既有 slots JSON、
  以及「每天全量下载 → MySQL 增量入库 → UI 搜索 → 工作区」手动选槽。
  为每条 slot 标注 source_tier（anchor / curated / pop / file）。
"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from workflow.config import PROJECT_ROOT
from workflow.metadata.tmdb_export_slots import (
    ANCHOR_SLOTS,
    CURATED_MOVIE_IDS,
    CURATED_TV_IDS,
    DEFAULT_EXPORT_DIR,
    ExportFileSet,
    MOVIE_POPULARITY_MAX,
    MOVIE_POPULARITY_MIN,
    TV_POPULARITY_MIN,
    _export_date_suffix,
    _short_label,
    build_benchmark_slot_list,
    download_tmdb_exports,
    resolve_latest_export_date,
    write_report_json,
    write_slots_json,
)
from workflow.ops import tmdb_export_store
from workflow.ops.track_store import resolve_page_id_from_slot

# 工作区候选清单 glob
DEFAULT_SLOT_GLOB_DIRS: Tuple[Path, ...] = (
    PROJECT_ROOT / "worklogs",
    PROJECT_ROOT / "data" / "failed_slots",
    PROJECT_ROOT / "data" / "ops",
)

# 日导出：下载 → MySQL 入库（异步进度供 UI 轮询）
_LOAD_LOCK = threading.Lock()
_LOAD_THREAD: Optional[threading.Thread] = None
_LOAD_PROGRESS: Dict[str, Any] = {
    "status": "idle",
    "phase": "",
    "percent": 0,
    "movies_loaded": 0,
    "tv_loaded": 0,
    "message": "尚未开始",
    "error": None,
    "result": None,
}


def get_export_load_progress() -> Dict[str, Any]:
    """
    读取日导出入库进度快照（叠加 MySQL 就绪状态）。

    @returns: status/phase/percent/message 等
    """
    db_meta = tmdb_export_store.meta_summary()
    with _LOAD_LOCK:
        prog = {**_LOAD_PROGRESS}
    ready = bool(db_meta.get("ready"))
    if prog.get("status") != "running" and ready:
        prog["status"] = prog.get("status") if prog.get("status") == "error" else "done"
        prog["percent"] = 100 if prog.get("status") == "done" else prog.get("percent", 0)
        if prog.get("status") == "done" and not prog.get("message"):
            prog["message"] = (
                f"MySQL 已就绪 · {db_meta.get('export_date')} · "
                f"movie {db_meta.get('movie_count'):,} · tv {db_meta.get('tv_count'):,}"
            )
    return {
        "ok": True,
        **prog,
        "ready": ready,
        "storage": "mysql",
        "cached_movie_count": int(db_meta.get("movie_count") or 0),
        "cached_tv_count": int(db_meta.get("tv_count") or 0),
        "export_date": db_meta.get("export_date"),
        "db": db_meta,
    }


def _set_load_progress(**kwargs: Any) -> None:
    """更新加载进度字段。"""
    with _LOAD_LOCK:
        _LOAD_PROGRESS.update(kwargs)


def _anchor_keys() -> Set[str]:
    """锚点 slot_key 集合。"""
    return {resolve_page_id_from_slot(s) for s in ANCHOR_SLOTS}


def _curated_movie_ids() -> Set[int]:
    """Curated 电影 TMDB ID。"""
    return set(CURATED_MOVIE_IDS)


def _curated_tv_ids() -> Set[int]:
    """Curated 剧集 TMDB ID。"""
    return set(CURATED_TV_IDS)


def classify_source_tier(slot: Dict[str, Any]) -> str:
    """
    标注清单层级：anchor | curated | pop | file。

    @param slot: 槽位 dict
    @returns: tier 字符串
    """
    if slot.get("source_tier"):
        return str(slot["source_tier"])
    key = resolve_page_id_from_slot(slot)
    if key in _anchor_keys():
        return "anchor"
    media = str(slot.get("media_type") or "tv")
    tmdb_id = int(slot["tmdb_id"])
    if media == "movie" and tmdb_id in _curated_movie_ids():
        return "curated"
    if media == "tv" and tmdb_id in _curated_tv_ids():
        # 锚点系列（BB）已在上面命中；其余 curated 默认 S01E01
        return "curated"
    if "popularity" in slot:
        return "pop"
    return "file"


def annotate_slots(slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    为清单条目补充 page_id / source_tier。

    @param slots: 原始 slots
    @returns: 标注后列表
    """
    out: List[Dict[str, Any]] = []
    for raw in slots:
        item = dict(raw)
        item["page_id"] = resolve_page_id_from_slot(item)
        item["source_tier"] = classify_source_tier(item)
        out.append(item)
    return out


def load_slots_json(path: Path) -> Dict[str, Any]:
    """
    读取 slots JSON（数组或含 slots 字段的报告）。

    @param path: 文件路径
    @returns: { ok, path, slots, meta? }
    """
    if not path.is_file():
        return {"ok": False, "error": f"文件不存在: {path}"}
    data = json.loads(path.read_text(encoding="utf-8"))
    meta: Dict[str, Any] = {}
    if isinstance(data, list):
        slots = data
    elif isinstance(data, dict) and isinstance(data.get("slots"), list):
        slots = data["slots"]
        meta = data.get("meta") or {}
    else:
        return {"ok": False, "error": "JSON 需为 slots 数组或含 slots 字段的对象"}
    annotated = annotate_slots(slots)
    return {
        "ok": True,
        "path": str(path),
        "kind": "file",
        "meta": meta,
        "slots": annotated,
        "count": len(annotated),
        "tier_counts": _tier_counts(annotated),
    }


def _tier_counts(slots: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计各 tier 数量。"""
    counts: Dict[str, int] = {}
    for s in slots:
        tier = str(s.get("source_tier") or "unknown")
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def list_candidate_slot_files(*, limit: int = 40) -> List[Dict[str, Any]]:
    """
    扫描 worklogs / failed_slots 下可用的 slot JSON。

    @param limit: 最多返回条数
    @returns: 摘要列表
    """
    found: List[Dict[str, Any]] = []
    patterns = ("*slots*.json", "*benchmark-slots*.json", "failed-slots.json")
    for root in DEFAULT_SLOT_GLOB_DIRS:
        if not root.is_dir():
            continue
        for pattern in patterns:
            for path in root.rglob(pattern):
                if "registry" in path.name:
                    continue
                if path.name.startswith("batch-"):
                    continue
                try:
                    stat = path.stat()
                    found.append(
                        {
                            "path": str(path.relative_to(PROJECT_ROOT)),
                            "abs_path": str(path),
                            "name": path.name,
                            "mtime": int(stat.st_mtime),
                            "size": stat.st_size,
                        }
                    )
                except OSError:
                    continue
    # 去重并按 mtime 降序
    dedup: Dict[str, Dict[str, Any]] = {}
    for item in found:
        dedup[item["abs_path"]] = item
    items = sorted(dedup.values(), key=lambda x: x["mtime"], reverse=True)
    return items[:limit]


def build_from_tmdb_export(
    *,
    total: int = 20,
    movie_count: Optional[int] = None,
    tv_count: Optional[int] = None,
    download: bool = False,
    force_download: bool = False,
    export_date: Optional[str] = None,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    运行「TMDB 日导出 + 锚点/curated」选槽并写 JSON。

    @param total: 目标总数（含锚点）
    @param movie_count: 可选电影数
    @param tv_count: 可选剧集数
    @param download: 是否下载导出
    @param force_download: 强制重下
    @param export_date: YYYY-MM-DD
    @param out_dir: 输出目录，默认 worklogs/今日
    @returns: 含 slots / paths / meta 的结果
    """
    resolved_date: Optional[date] = date.fromisoformat(export_date) if export_date else None

    if download or force_download:
        files = download_tmdb_exports(resolved_date, force=force_download)
    else:
        resolved = resolved_date or resolve_latest_export_date()
        suffix = _export_date_suffix(resolved)
        movie_gz = DEFAULT_EXPORT_DIR / f"movie_ids_{suffix}.json.gz"
        tv_gz = DEFAULT_EXPORT_DIR / f"tv_series_ids_{suffix}.json.gz"
        if not movie_gz.is_file() or not tv_gz.is_file():
            files = download_tmdb_exports(resolved, force=False)
        else:
            files = ExportFileSet(export_date=resolved, movie_gz=movie_gz, tv_gz=tv_gz)

    report = build_benchmark_slot_list(
        files,
        total=total,
        movie_count=movie_count,
        tv_count=tv_count,
    )
    day = date.today().isoformat()
    target_dir = out_dir or (PROJECT_ROOT / "worklogs" / day)
    slots_path = target_dir / "tmdb-benchmark-slots.json"
    report_path = target_dir / "tmdb-benchmark-slots-report.json"
    write_slots_json(report, slots_path)
    write_report_json(report, report_path)

    annotated: List[Dict[str, Any]] = []
    for raw in report["slots"]:
        item = dict(raw)
        item["page_id"] = resolve_page_id_from_slot(item)
        # 新建导出不含 source_tier，按锚点/curated/pop 分类
        item["source_tier"] = classify_source_tier({k: v for k, v in item.items() if k != "source_tier"})
        annotated.append(item)

    return {
        "ok": True,
        "kind": "tmdb_export",
        "path": str(slots_path.relative_to(PROJECT_ROOT)),
        "abs_path": str(slots_path),
        "report_path": str(report_path.relative_to(PROJECT_ROOT)),
        "meta": report.get("meta") or {},
        "slots": annotated,
        "count": len(annotated),
        "tier_counts": _tier_counts(annotated),
        "logic": {
            "anchors": "ANCHOR_SLOTS 固定回归（BB S04 + Inception）",
            "curated": "CURATED_MOVIE_IDS / CURATED_TV_IDS 优先",
            "pop": "TMDB 日导出 popularity 补位（电影 8~150，TV≥15）",
            "tv_default": "新 TV 默认 S01E01",
        },
    }


def describe_source_logic() -> Dict[str, Any]:
    """返回 UI 展示用的选槽逻辑说明。"""
    return {
        "title": "TMDB 日导出 + 锚点/curated",
        "steps": [
            {
                "id": "anchor",
                "name": "锚点 ANCHOR_SLOTS",
                "desc": "固定回归槽：Breaking Bad S04 多集 + Inception，始终先入清单",
                "count": len(ANCHOR_SLOTS),
            },
            {
                "id": "curated",
                "name": "精选 curated",
                "desc": "硬编码高价值作品 ID，按列表顺序优先选取",
                "movie_count": len(CURATED_MOVIE_IDS),
                "tv_count": len(CURATED_TV_IDS),
            },
            {
                "id": "pop",
                "name": "TMDB Daily Export popularity",
                "desc": "files.tmdb.org 日导出；电影 pop∈[8,150]，剧集 pop≥15；过滤 adult/video",
            },
            {
                "id": "manual",
                "name": "手动：全量下载 → 增量入库 → 搜索 → 拉季集 → 工作区",
                "desc": "Daily Export → MySQL UPSERT → UI 搜索；TV 经 crawler_tmdb 拉 seasons/episodes 选型后再写入工作区",
            },
        ],
        "cli": "python -m workflow.run ops tmdb-sync",
        "export_dir": str(DEFAULT_EXPORT_DIR.relative_to(PROJECT_ROOT)),
        "manual_flow": [
            "full_download",
            "incremental_mysql",
            "ui_search",
            "tv_seasons_episodes",
            "workspace",
        ],
        "tv_catalog": {
            "api": "crawler_tmdb.tv_details / tv_season_details",
            "storage": "mysql",
            "tables": [
                "tmdb_tv_series",
                "tmdb_tv_seasons",
                "tmdb_tv_episodes",
                "tmdb_api_cache",
            ],
        },
        "defaults": {
            "movie_pop_min": MOVIE_POPULARITY_MIN,
            "movie_pop_max": MOVIE_POPULARITY_MAX,
            "tv_pop_min": TV_POPULARITY_MIN,
        },
    }


def resolve_export_files(
    *,
    download: bool = False,
    force_download: bool = False,
    export_date: Optional[str] = None,
) -> ExportFileSet:
    """
    解析（并可选下载）本地 TMDB 日导出文件组。

    @param download: 缺失时下载
    @param force_download: 强制重下
    @param export_date: YYYY-MM-DD
    @returns: ExportFileSet
    """
    resolved_date: Optional[date] = date.fromisoformat(export_date) if export_date else None
    if download or force_download:
        return download_tmdb_exports(resolved_date, force=force_download)

    resolved = resolved_date or resolve_latest_export_date()
    suffix = _export_date_suffix(resolved)
    movie_gz = DEFAULT_EXPORT_DIR / f"movie_ids_{suffix}.json.gz"
    tv_gz = DEFAULT_EXPORT_DIR / f"tv_series_ids_{suffix}.json.gz"
    if not movie_gz.is_file() or not tv_gz.is_file():
        return download_tmdb_exports(resolved, force=False)
    return ExportFileSet(export_date=resolved, movie_gz=movie_gz, tv_gz=tv_gz)


def _index_meta_from_db() -> Dict[str, Any]:
    """
    从 MySQL 组装索引元信息（兼容旧 API 字段名）。

    @returns: 含 ready / ingest_mode / last_* 的摘要
    """
    summary = tmdb_export_store.meta_summary()
    return {
        "ok": True,
        "storage": "mysql",
        "export_date": summary.get("export_date"),
        "movie_count": int(summary.get("movie_count") or 0),
        "tv_count": int(summary.get("tv_count") or 0),
        "movie_gz": summary.get("movie_gz") or None,
        "tv_gz": summary.get("tv_gz") or None,
        "export_dir": str(DEFAULT_EXPORT_DIR.relative_to(PROJECT_ROOT)),
        "ready": bool(summary.get("ready")),
        "ingest_mode": summary.get("ingest_mode"),
        "last_scanned": int(summary.get("last_scanned") or 0),
        "last_deleted": int(summary.get("last_deleted") or 0),
    }


def _db_matches_files(db_meta: Dict[str, Any], files: ExportFileSet) -> bool:
    """
    判断 MySQL 是否已同步到指定导出文件日。

    @param db_meta: meta_summary
    @param files: 本地导出文件集
    @returns: True 表示无需再次入库
    """
    return bool(
        db_meta.get("ready")
        and str(db_meta.get("export_date") or "") == files.export_date.isoformat()
        and str(db_meta.get("movie_gz") or "") == files.movie_gz.name
    )


def ensure_export_index(
    *,
    download: bool = True,
    force_download: bool = False,
    force_reload: bool = False,
    export_date: Optional[str] = None,
    daily: bool = False,
) -> Dict[str, Any]:
    """
    同步：全量下载 Daily Export（如需）→ 增量 UPSERT 入 MySQL。

    @param download: 本地缺失时下载
    @param force_download: 强制重下全量文件（日同步建议开启）
    @param force_reload: True=TRUNCATE 全量重建；False=增量 UPSERT + prune
    @param export_date: YYYY-MM-DD
    @param daily: 日同步模式（默认强制重下最新全量文件，再增量入库）
    @returns: 索引元信息
    """
    tmdb_export_store.ensure_tables()
    # 日同步：始终拉最新全量包，再增量写库
    effective_force_download = bool(force_download or daily)
    ingest_mode = "replace" if force_reload else "incremental"
    _set_load_progress(
        status="running",
        phase="resolve",
        percent=2,
        movies_loaded=0,
        tv_loaded=0,
        message=(
            "解析 / 全量下载日导出…"
            if effective_force_download
            else "解析 / 下载日导出文件…"
        ),
        error=None,
        result=None,
    )
    try:
        db_meta = tmdb_export_store.meta_summary()
        files = resolve_export_files(
            download=download or daily,
            force_download=effective_force_download,
            export_date=export_date,
        )
        # 同日已就绪且非强制重建 → 跳过（幂等；实际行数也须有效）
        if (
            not force_reload
            and _db_matches_files(db_meta, files)
            and tmdb_export_store.is_db_ready()
        ):
            meta = _index_meta_from_db()
            _set_load_progress(
                status="done",
                phase="done",
                percent=100,
                movies_loaded=meta["movie_count"],
                tv_loaded=meta["tv_count"],
                message=(
                    f"MySQL 已是最新导出日，跳过 · {meta['export_date']} · "
                    f"movie {meta['movie_count']:,} · tv {meta['tv_count']:,}"
                ),
                result=meta,
            )
            return meta

        mode_label = "全量重建" if ingest_mode == "replace" else "增量入库"
        _set_load_progress(
            phase="download_ok",
            percent=10,
            message=(
                f"全量文件就绪，开始{mode_label} · {files.export_date.isoformat()}"
            ),
        )

        def _on_phase(phase: str, count: int, message: str) -> None:
            """把 store 阶段映射为 UI 百分比。"""
            if phase == "truncate":
                pct = 12
            elif phase == "movies_db":
                pct = min(68, 15 + int(count / 20000))
            elif phase == "prune_movies":
                pct = 70
            elif phase == "tv_db":
                pct = min(92, 72 + int(count / 8000))
            elif phase == "prune_tv":
                pct = 96
            else:
                pct = 100
            kwargs: Dict[str, Any] = {
                "phase": phase,
                "percent": pct,
                "message": message,
            }
            if phase == "movies_db":
                kwargs["movies_loaded"] = count
            if phase == "tv_db":
                kwargs["tv_loaded"] = count
            _set_load_progress(**kwargs)

        tmdb_export_store.sync_from_export_files(
            movie_gz=files.movie_gz,
            tv_gz=files.tv_gz,
            export_date=files.export_date,
            mode=ingest_mode,
            on_phase=_on_phase,
        )
        meta = _index_meta_from_db()
        _set_load_progress(
            status="done",
            phase="done",
            percent=100,
            movies_loaded=meta["movie_count"],
            tv_loaded=meta["tv_count"],
            message=(
                f"{mode_label}完成 · {meta['export_date']} · "
                f"movie {meta['movie_count']:,} · tv {meta['tv_count']:,} · "
                f"扫描 {meta['last_scanned']:,} · 删除 {meta['last_deleted']:,}"
            ),
            result=meta,
        )
        return meta
    except Exception as exc:  # noqa: BLE001
        _set_load_progress(
            status="error",
            phase="error",
            percent=0,
            message=f"失败: {exc}",
            error=str(exc),
            result=None,
        )
        raise


def start_export_index_load(
    *,
    download: bool = True,
    force_download: bool = False,
    force_reload: bool = False,
    export_date: Optional[str] = None,
    daily: bool = False,
) -> Dict[str, Any]:
    """
    后台启动「全量下载 → 增量入库」（立即返回，UI 轮询进度）。

    @param download: 本地缺失时下载
    @param force_download: 强制重下
    @param force_reload: TRUNCATE 全量重建
    @param export_date: YYYY-MM-DD
    @param daily: 日同步（强制全量下载 + 增量入库）
    @returns: { ok, started|already_running|already_ready, progress }
    """
    global _LOAD_THREAD
    tmdb_export_store.ensure_tables()
    with _LOAD_LOCK:
        if _LOAD_PROGRESS.get("status") == "running" and _LOAD_THREAD and _LOAD_THREAD.is_alive():
            return {
                "ok": True,
                "started": False,
                "already_running": True,
                "progress": get_export_load_progress(),
            }
        # 仅在「非日同步 / 非强制」且库已是同一导出日时短路
        if (
            not daily
            and not force_reload
            and not force_download
            and tmdb_export_store.is_db_ready()
        ):
            try:
                files = resolve_export_files(
                    download=False,
                    force_download=False,
                    export_date=export_date,
                )
                if _db_matches_files(tmdb_export_store.meta_summary(), files):
                    meta = _index_meta_from_db()
                    _LOAD_PROGRESS.update(
                        {
                            "status": "done",
                            "phase": "done",
                            "percent": 100,
                            "movies_loaded": meta["movie_count"],
                            "tv_loaded": meta["tv_count"],
                            "message": f"MySQL 已是最新 · {meta['export_date']}",
                            "error": None,
                            "result": meta,
                        }
                    )
                    return {
                        "ok": True,
                        "started": False,
                        "already_ready": True,
                        "progress": get_export_load_progress(),
                        "result": meta,
                    }
            except Exception:  # noqa: BLE001 — 缺文件则继续走下载入库
                pass

    def _worker() -> None:
        """后台线程执行 ensure。"""
        try:
            ensure_export_index(
                download=download,
                force_download=force_download,
                force_reload=force_reload,
                export_date=export_date,
                daily=daily,
            )
        except Exception:  # noqa: BLE001 — 进度已记录
            pass

    mode_msg = (
        "已启动：日同步（全量下载 → 增量入库）…"
        if daily
        else (
            "已启动：全量重建入库…"
            if force_reload
            else "已启动：全量下载 → 增量入库…"
        )
    )
    thread = threading.Thread(target=_worker, name="ops-export-mysql", daemon=True)
    with _LOAD_LOCK:
        _LOAD_THREAD = thread
        _LOAD_PROGRESS.update(
            {
                "status": "running",
                "phase": "starting",
                "percent": 1,
                "movies_loaded": 0,
                "tv_loaded": 0,
                "message": mode_msg,
                "error": None,
                "result": None,
            }
        )
    thread.start()
    return {
        "ok": True,
        "started": True,
        "already_running": False,
        "progress": get_export_load_progress(),
    }


def daily_sync_export(
    *,
    export_date: Optional[str] = None,
    force_reload: bool = False,
) -> Dict[str, Any]:
    """
    每日任务：全量下载最新 Daily Export → 增量入库 MySQL。

    @param export_date: 可选指定日；默认探测最近可用日
    @param force_reload: True 则改为 TRUNCATE 全量重建
    @returns: 索引元信息
    """
    return ensure_export_index(
        download=True,
        force_download=True,
        force_reload=force_reload,
        export_date=export_date,
        daily=True,
    )


def search_tmdb_export(
    *,
    q: Optional[str] = None,
    media_types: Optional[List[str]] = None,
    pop_min: Optional[float] = None,
    pop_max: Optional[float] = None,
    exclude_adult: bool = True,
    exclude_video: bool = True,
    limit: int = 50,
    offset: int = 0,
    download: bool = False,
    export_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从 MySQL `tmdb_export_titles` 搜索/筛选，供手动勾选。

    @param q: 标题子串或纯数字 TMDB ID
    @param media_types: movie / tv
    @param pop_min: 最低 popularity
    @param pop_max: 最高 popularity
    @param exclude_adult: 排除成人内容
    @param exclude_video: 电影排除 video 标记
    @param limit: 返回条数上限
    @param offset: 分页偏移
    @param download: 库未就绪时是否自动下载入库（默认同步会阻塞，UI 应先 ensure）
    @param export_date: YYYY-MM-DD
    @returns: { ok, hits, total_matched, meta }
    """
    tmdb_export_store.ensure_tables()
    if not tmdb_export_store.is_db_ready():
        if download:
            ensure_export_index(download=True, export_date=export_date)
        else:
            return {
                "ok": False,
                "error": "TMDB 导出尚未入库；请先点击「下载并入库日导出」",
                "hits": [],
                "total_matched": 0,
            }

    raw = tmdb_export_store.search_titles(
        q=q,
        media_types=media_types,
        pop_min=pop_min,
        pop_max=pop_max,
        exclude_adult=exclude_adult,
        exclude_video=exclude_video,
        limit=limit,
        offset=offset,
    )
    if not raw.get("ok"):
        return raw

    hits: List[Dict[str, Any]] = []
    for row in raw.get("hits") or []:
        media = str(row["media_type"])
        item: Dict[str, Any] = {
            "tmdb_id": int(row["tmdb_id"]),
            "media_type": media,
            "title": row.get("title"),
            "popularity": round(float(row.get("popularity") or 0.0), 4),
            "label": _short_label(str(row.get("title") or "")),
        }
        if media == "tv":
            item["season"] = 1
            item["episode"] = 1
            item["label"] = f"{_short_label(str(row.get('title') or ''), 24)} S01E01"
        slim = {k: v for k, v in item.items() if k != "source_tier"}
        item["page_id"] = resolve_page_id_from_slot(slim)
        item["source_tier"] = classify_source_tier(slim)
        hits.append(item)

    meta = raw.get("meta") or {}
    return {
        "ok": True,
        "hits": hits,
        "total_matched": raw.get("total_matched", 0),
        "offset": raw.get("offset", offset),
        "limit": raw.get("limit", limit),
        "meta": meta,
    }


def slots_from_manual_selections(
    selections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    将手动勾选条目转为已标注 slot 列表（标题优先取自 MySQL）。

    @param selections: 每项含 tmdb_id、media_type、可选 season/episode/title/popularity
    @returns: { ok, slots, count }
    """
    if not selections:
        return {"ok": False, "error": "未选择任何条目", "slots": [], "count": 0}

    keys = [
        (str(s.get("media_type") or "tv").lower(), int(s["tmdb_id"]))
        for s in selections
    ]
    looked = tmdb_export_store.lookup_titles(keys)
    db_meta = tmdb_export_store.meta_summary()

    slots: List[Dict[str, Any]] = []
    for sel in selections:
        tmdb_id = int(sel["tmdb_id"])
        media = str(sel.get("media_type") or "tv").lower()
        src = looked.get((media, tmdb_id))
        title = sel.get("title") or (src or {}).get("title") or f"{media}:{tmdb_id}"
        pop = sel.get("popularity")
        if pop is None and src is not None:
            pop = src.get("popularity")
        item: Dict[str, Any] = {
            "tmdb_id": tmdb_id,
            "media_type": media,
            "title": title,
            "label": _short_label(str(title)),
            "popularity": round(float(pop), 4) if pop is not None else None,
        }
        if media == "tv":
            season = int(sel.get("season") if sel.get("season") is not None else 1)
            episode = int(sel.get("episode") if sel.get("episode") is not None else 1)
            item["season"] = season
            item["episode"] = episode
            item["label"] = f"{_short_label(str(title), 24)} S{season:02d}E{episode:02d}"
        item["page_id"] = resolve_page_id_from_slot(item)
        item["source_tier"] = classify_source_tier(
            {k: v for k, v in item.items() if k != "source_tier"}
        )
        item["manual"] = True
        slots.append(item)

    return {
        "ok": True,
        "kind": "tmdb_export_manual",
        "slots": slots,
        "count": len(slots),
        "tier_counts": _tier_counts(slots),
        "meta": {
            "export_date": db_meta.get("export_date"),
            "source": "tmdb_daily_export_mysql",
            "storage": "mysql",
        },
    }


def fetch_tv_seasons(
    tmdb_id: int,
    *,
    force_refresh: bool = False,
    include_specials: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    拉取 TV 季列表（crawler_tmdb + 本地 ``data/tmdb_tv``）。

    @param tmdb_id: 剧集 ID
    @param force_refresh: 强制刷新 TMDB
    @param include_specials: 是否含 Specials（season 0）
    @param language: 语言
    @returns: 目录结果
    """
    from workflow.metadata.tmdb_tv_catalog import list_seasons

    return list_seasons(
        int(tmdb_id),
        force_refresh=force_refresh,
        include_specials=include_specials,
        language=language,
    )


def fetch_tv_episodes(
    tmdb_id: int,
    season: int,
    *,
    force_refresh: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    拉取指定季分集列表。

    @param tmdb_id: 剧集 ID
    @param season: 季号
    @param force_refresh: 强制刷新
    @param language: 语言
    @returns: 分集结果
    """
    from workflow.metadata.tmdb_tv_catalog import list_episodes

    return list_episodes(
        int(tmdb_id),
        int(season),
        force_refresh=force_refresh,
        language=language,
    )


def fetch_tv_catalog(
    tmdb_id: int,
    *,
    season: Optional[int] = None,
    force_refresh: bool = False,
    include_specials: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    确保本地 TV 季集目录；可选同时拉某一季分集。

    @param tmdb_id: 剧集 ID
    @param season: 可选季号
    @param force_refresh: 强制刷新
    @param include_specials: 含 Specials
    @param language: 语言
    @returns: 综合结果
    """
    from workflow.metadata.tmdb_tv_catalog import ensure_catalog

    return ensure_catalog(
        int(tmdb_id),
        season=season,
        force_refresh=force_refresh,
        include_specials=include_specials,
        language=language,
    )
