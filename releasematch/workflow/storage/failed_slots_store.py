# -*- coding: utf-8 -*-
"""
失败 slot 去重登记册 — 供人工复查与 retry 清单导出。

@module workflow.storage.failed_slots_store
@description
  pipeline batch 失败槽位写入本地 JSON，按 slot_key 去重合并。
  成功 retry 后自动移入 resolved 区。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from workflow.config import PROJECT_ROOT

# 主登记册（去重、含历史）
DEFAULT_REGISTRY_PATH: Path = PROJECT_ROOT / "data" / "failed_slots" / "registry.json"
# 仅 active 失败项，供 pipeline retry
DEFAULT_ACTIVE_SLOTS_PATH: Path = PROJECT_ROOT / "data" / "failed_slots" / "failed-slots.json"
# worklog 镜像，便于人工打开
DEFAULT_WORKLOG_MIRROR_PATH: Path = PROJECT_ROOT / "worklogs" / "failed-slots-registry.json"


def _utc_now_iso() -> str:
    """返回当前 UTC ISO8601 字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_slot_key(
    tmdb_id: int,
    media_type: str,
    *,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> str:
    """
    生成 slot 唯一键（与 media_pages page_id 对齐）。

    @param tmdb_id: TMDB ID
    @param media_type: movie | tv
    @param season: 季号
    @param episode: 集号
    @returns: 如 movie:424、tv:34307:s01e01
    """
    if media_type == "movie":
        return f"movie:{tmdb_id}"
    season_num = int(season or 0)
    episode_num = int(episode or 0)
    return f"tv:{tmdb_id}:s{season_num:02d}e{episode_num:02d}"


def parse_page_id(page_id: str) -> Optional[Dict[str, Any]]:
    """
    从 page_id 反解析 slot 最小字段。

    @param page_id: 如 movie:424、tv:34307:s01e01
    @returns: 含 tmdb_id、media_type、season、episode 的字典
    """
    import re

    if page_id.startswith("movie:"):
        try:
            return {"tmdb_id": int(page_id.split(":", 1)[1]), "media_type": "movie"}
        except ValueError:
            return None
    match = re.match(r"^tv:(\d+):s(\d+)e(\d+)$", page_id, re.IGNORECASE)
    if match:
        return {
            "tmdb_id": int(match.group(1)),
            "media_type": "tv",
            "season": int(match.group(2)),
            "episode": int(match.group(3)),
        }
    return None


def slot_key_from_dict(slot: Dict[str, Any]) -> str:
    """
    从 slot 字典计算 slot_key。

    @param slot: benchmark slot 项
    @returns: slot_key
    """
    media_type = str(slot.get("media_type") or slot.get("media_kind") or "tv")
    season = slot.get("season")
    episode = slot.get("episode")
    return build_slot_key(
        int(slot["tmdb_id"]),
        media_type,
        season=int(season) if season is not None else None,
        episode=int(episode) if episode is not None else None,
    )


def _empty_registry() -> Dict[str, Any]:
    """构造空登记册结构。"""
    return {
        "meta": {
            "updated_at": _utc_now_iso(),
            "active_count": 0,
            "resolved_count": 0,
            "version": 1,
        },
        "active": {},
        "resolved": {},
    }


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> Dict[str, Any]:
    """
    读取失败 slot 登记册。

    @param path: registry.json 路径
    @returns: 登记册字典
    """
    if not path.is_file():
        return _empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_registry()
    if not isinstance(data, dict):
        return _empty_registry()
    data.setdefault("meta", {})
    data.setdefault("active", {})
    data.setdefault("resolved", {})
    if not isinstance(data["active"], dict):
        data["active"] = {}
    if not isinstance(data["resolved"], dict):
        data["resolved"] = {}
    return data


def save_registry(registry: Dict[str, Any], path: Path = DEFAULT_REGISTRY_PATH) -> Path:
    """
    写入登记册并同步导出 active 清单与 worklog 镜像。

    @param registry: 登记册字典
    @param path: 主文件路径
    @returns: 写入路径
    """
    registry["meta"]["updated_at"] = _utc_now_iso()
    registry["meta"]["active_count"] = len(registry.get("active") or {})
    registry["meta"]["resolved_count"] = len(registry.get("resolved") or {})

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    active_slots = export_active_slots(registry)
    DEFAULT_ACTIVE_SLOTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_ACTIVE_SLOTS_PATH.write_text(
        json.dumps(active_slots, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    DEFAULT_WORKLOG_MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_WORKLOG_MIRROR_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def export_active_slots(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    导出当前 active 失败 slot 列表（pipeline retry 用）。

    @param registry: 登记册
    @returns: slot 数组，按 label 排序
    """
    active: Dict[str, Dict[str, Any]] = registry.get("active") or {}
    rows: List[Dict[str, Any]] = []
    for entry in active.values():
        row: Dict[str, Any] = {
            "label": entry.get("label"),
            "tmdb_id": entry.get("tmdb_id"),
            "media_type": entry.get("media_type"),
        }
        if entry.get("media_type") == "tv":
            row["season"] = entry.get("season")
            row["episode"] = entry.get("episode")
        if entry.get("title"):
            row["title"] = entry.get("title")
        if entry.get("popularity") is not None:
            row["popularity"] = entry.get("popularity")
        rows.append(row)
    rows.sort(key=lambda item: str(item.get("label") or "").lower())
    return rows


def _lookup_external_ids(tmdb_id: int, media_type: str) -> Dict[str, Any]:
    """从 TMDB 缓存读取 imdb/tvdb（便于人工排查）。"""
    try:
        from workflow.metadata.tmdb_api import fetch_external_ids_from_api

        row = fetch_external_ids_from_api(tmdb_id, media_type, use_cache=True)
        return row or {}
    except Exception:
        return {}


def _slot_row_from_source(slot: Dict[str, Any]) -> Dict[str, Any]:
    """从 benchmark slot 提取登记字段。"""
    media_type = str(slot.get("media_type") or slot.get("media_kind") or "tv")
    tmdb_id = int(slot["tmdb_id"])
    season = slot.get("season")
    episode = slot.get("episode")
    ext = _lookup_external_ids(tmdb_id, media_type)
    row: Dict[str, Any] = {
        "slot_key": slot_key_from_dict(slot),
        "tmdb_id": tmdb_id,
        "media_type": media_type,
        "label": slot.get("label"),
        "title": slot.get("title") or ext.get("title") or slot.get("label"),
        "page_id": None,
        "imdb_id": ext.get("imdb_id"),
        "tvdb_id": ext.get("tvdb_id"),
        "attempt_count": 0,
        "sources": [],
    }
    if media_type == "tv":
        row["season"] = int(season) if season is not None else None
        row["episode"] = int(episode) if episode is not None else None
    if slot.get("popularity") is not None:
        row["popularity"] = slot.get("popularity")
    return row


def _index_slots_by_key(slots: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """slot_key → 源 slot 字典。"""
    indexed: Dict[str, Dict[str, Any]] = {}
    for slot in slots:
        indexed[slot_key_from_dict(slot)] = slot
    return indexed


def merge_batch_report(
    slots: List[Dict[str, Any]],
    batch_report: Dict[str, Any],
    *,
    report_path: Optional[str] = None,
    source: str = "pipeline_batch",
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> Dict[str, Any]:
    """
    将单次 batch 结果合并进失败登记册（去重）。

    @param slots: 本批输入 slot 列表
    @param batch_report: run_batch_slot_pipeline 返回值
    @param report_path: 批次报告文件路径
    @param source: 来源标签
    @param registry_path: 登记册路径
    @returns: 合并摘要
    """
    registry = load_registry(registry_path)
    active: Dict[str, Dict[str, Any]] = dict(registry.get("active") or {})
    resolved: Dict[str, Dict[str, Any]] = dict(registry.get("resolved") or {})
    slot_index = _index_slots_by_key(slots)
    now = _utc_now_iso()

    added = 0
    updated = 0
    resolved_now = 0

    for item in batch_report.get("results") or []:
        page_id = str(item.get("page_id") or "")
        status = str(item.get("status") or "")
        label = item.get("label")

        slot_key = page_id
        source_slot = slot_index.get(page_id)
        if not source_slot:
            for candidate in slots:
                if slot_key_from_dict(candidate) == page_id:
                    source_slot = candidate
                    break
        if source_slot:
            slot_key = slot_key_from_dict(source_slot)
        elif page_id:
            parsed = parse_page_id(page_id)
            if parsed:
                source_slot = {**parsed, "label": label}
                slot_key = slot_key_from_dict(source_slot)
        elif not slot_key:
            continue

        if status == "failed":
            if source_slot and source_slot.get("tmdb_id"):
                base = _slot_row_from_source(source_slot)
            else:
                base = {
                    "slot_key": slot_key,
                    "page_id": page_id,
                    "label": label,
                    "attempt_count": 0,
                    "sources": [],
                }
            base["page_id"] = page_id
            result = item.get("result") or {}
            base["error"] = result.get("error") or "unknown"
            base["fetch_note"] = result.get("fetch_note")
            base["last_failed_at"] = now
            base["last_report_path"] = report_path
            base["last_sync_run_id"] = batch_report.get("sync_run_id")
            if source not in (base.get("sources") or []):
                base.setdefault("sources", []).append(source)

            if slot_key in active:
                prev = active[slot_key]
                base["first_failed_at"] = prev.get("first_failed_at") or now
                base["attempt_count"] = int(prev.get("attempt_count") or 0) + 1
                updated += 1
            else:
                base["first_failed_at"] = now
                base["attempt_count"] = 1
                added += 1
            active[slot_key] = base
            resolved.pop(slot_key, None)

        elif status == "ok" and slot_key in active:
            entry = active.pop(slot_key)
            entry["resolved_at"] = now
            entry["resolved_report_path"] = report_path
            entry["resolved_sync_run_id"] = batch_report.get("sync_run_id")
            resolved[slot_key] = entry
            resolved_now += 1

    registry["active"] = active
    registry["resolved"] = resolved
    save_registry(registry, registry_path)

    return {
        "ok": True,
        "registry_path": str(registry_path),
        "active_slots_path": str(DEFAULT_ACTIVE_SLOTS_PATH),
        "worklog_mirror": str(DEFAULT_WORKLOG_MIRROR_PATH),
        "added": added,
        "updated": updated,
        "resolved": resolved_now,
        "active_count": len(active),
        "resolved_count": len(resolved),
    }


def merge_report_files(
    report_paths: List[Path],
    *,
    slots_paths: Optional[List[Path]] = None,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> Dict[str, Any]:
    """
    从多个历史 batch 报告重建/合并登记册。

    @param report_paths: pipeline-*-report.json 路径列表
    @param slots_paths: 可选 slot JSON 列表（用于补全 metadata）
    @param registry_path: 登记册路径
    @returns: 合并摘要
    """
    slot_pool: Dict[str, Dict[str, Any]] = {}
    for spath in slots_paths or []:
        if not spath.is_file():
            continue
        from workflow.storage.pipeline import load_slots_json

        for slot in load_slots_json(spath):
            slot_pool[slot_key_from_dict(slot)] = slot

    summaries: List[Dict[str, Any]] = []
    for rpath in report_paths:
        if not rpath.is_file():
            continue
        report = json.loads(rpath.read_text(encoding="utf-8"))
        batch_slots: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        for item in report.get("results") or []:
            page_id = str(item.get("page_id") or "")
            slot = slot_pool.get(page_id)
            if not slot:
                for candidate in slot_pool.values():
                    if slot_key_from_dict(candidate) == page_id:
                        slot = candidate
                        break
            slot_key = slot_key_from_dict(slot) if slot else page_id
            if slot_key in seen_keys:
                continue
            seen_keys.add(slot_key)
            if slot:
                batch_slots.append(slot)
        summary = merge_batch_report(
            batch_slots,
            report,
            report_path=str(rpath),
            source=rpath.stem,
            registry_path=registry_path,
        )
        summaries.append(summary)

    registry = load_registry(registry_path)
    return {
        "ok": True,
        "reports_merged": len(summaries),
        "active_count": len(registry.get("active") or {}),
        "resolved_count": len(registry.get("resolved") or {}),
        "registry_path": str(registry_path),
        "details": summaries,
    }
