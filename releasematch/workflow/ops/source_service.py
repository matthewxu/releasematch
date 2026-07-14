# -*- coding: utf-8 -*-
"""
Ops 第一段：清单从哪来。

@module workflow.ops.source_service
@description
  支持 TMDB 日导出+锚点/curated 生成、加载既有 slots JSON、失败槽清单。
  为每条 slot 标注 source_tier（anchor / curated / pop / file）。
"""

from __future__ import annotations

import json
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
    _export_date_suffix,
    build_benchmark_slot_list,
    download_tmdb_exports,
    resolve_latest_export_date,
    write_report_json,
    write_slots_json,
)
from workflow.ops.track_store import resolve_page_id_from_slot

# 工作区候选清单 glob
DEFAULT_SLOT_GLOB_DIRS: Tuple[Path, ...] = (
    PROJECT_ROOT / "worklogs",
    PROJECT_ROOT / "data" / "failed_slots",
    PROJECT_ROOT / "data" / "ops",
)


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
        ],
        "cli": "python scripts/tmdb_select_benchmark_slots.py --download --total 20",
        "export_dir": str(DEFAULT_EXPORT_DIR.relative_to(PROJECT_ROOT)),
    }
