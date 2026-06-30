#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量槽位 magnet 拉取。

@module workflow.torrent_sources.batch_fetch
@description 按槽位队列串行调用 FetchService，输出汇总 JSON。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.metadata.external_ids import resolve_external_ids
from workflow.torrent_sources.fetch_service import FetchService
from workflow.torrent_sources.models import FetchMode, FetchRequest, MediaType


@dataclass
class BatchSlot:
    """
    单条批补槽位。

    @var tmdb_id: TMDB 作品 ID
    @var media_type: tv | movie
    @var season: 季号（剧集）
    @var episode: 集号（剧集）
    @var force: 是否忽略缓存
    """

    tmdb_id: int
    media_type: str = "tv"
    season: Optional[int] = None
    episode: Optional[int] = None
    force: bool = False


# standalone Demo 默认队列（与 external_ids 映射一致）
DEFAULT_DEMO_SLOTS: List[BatchSlot] = [
    BatchSlot(tmdb_id=1396, media_type="tv", season=4, episode=6),
    BatchSlot(tmdb_id=603, media_type="movie"),
    BatchSlot(tmdb_id=27205, media_type="movie"),
]


@dataclass
class BatchSlotResult:
    """
    单槽批补结果摘要。

    @var slot: 原始槽位
    @var cache_key: 缓存键
    @var count: magnet 条数
    @var cached: 是否命中缓存
    @var cross_source_max: 本槽最大跨源数
    @var error: 错误信息
    @var ok: 是否成功（无 error 且 count >= min_count）
    """

    slot: BatchSlot
    cache_key: str
    count: int = 0
    cached: bool = False
    cross_source_max: int = 0
    error: Optional[str] = None
    ok: bool = False


@dataclass
class BatchFetchSummary:
    """
    批补运行汇总。

    @var total: 槽位数
    @var succeeded: 成功数
    @var failed: 失败数
    @var results: 各槽结果
    """

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: List[BatchSlotResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "results": [
                {
                    "tmdb_id": r.slot.tmdb_id,
                    "media_type": r.slot.media_type,
                    "season": r.slot.season,
                    "episode": r.slot.episode,
                    "cache_key": r.cache_key,
                    "count": r.count,
                    "cached": r.cached,
                    "cross_source_max": r.cross_source_max,
                    "error": r.error,
                    "ok": r.ok,
                }
                for r in self.results
            ],
        }


def load_slots_from_json(path: Path) -> List[BatchSlot]:
    """
    从 JSON 文件加载槽位队列。

    文件格式：``[{"tmdb_id":1396,"media_type":"tv","season":4,"episode":6}, ...]``

    @param path: JSON 路径
    @returns: BatchSlot 列表
    """
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("batch slots JSON 必须是数组")

    slots: List[BatchSlot] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        slots.append(
            BatchSlot(
                tmdb_id=int(row["tmdb_id"]),
                media_type=str(row.get("media_type") or "tv"),
                season=row.get("season"),
                episode=row.get("episode"),
                force=bool(row.get("force", False)),
            )
        )
    return slots


def _build_request(slot: BatchSlot) -> FetchRequest:
    """
    构造 FetchRequest。

    @param slot: BatchSlot
    @returns: FetchRequest
    """
    media = MediaType.MOVIE if slot.media_type == "movie" else MediaType.TV
    ext = resolve_external_ids(tmdb_id=slot.tmdb_id, media_type=slot.media_type)
    return FetchRequest(
        tmdb_id=slot.tmdb_id,
        media_type=media,
        season=slot.season,
        episode=slot.episode,
        imdb_id=ext.get("imdb_id"),
        tvdb_id=ext.get("tvdb_id"),
        mode=FetchMode.BATCH,
        force=slot.force,
    )


def run_batch_fetch(
    slots: List[BatchSlot],
    accounts_path: Optional[str] = None,
    min_count: int = 1,
) -> BatchFetchSummary:
    """
    串行批补多个槽位。

    @param slots: 槽位队列
    @param accounts_path: 可选 accounts 配置路径
    @param min_count: 单槽最少 magnet 条数视为成功
    @returns: BatchFetchSummary
    """
    service = FetchService(accounts_path=accounts_path)
    summary = BatchFetchSummary(total=len(slots))

    for slot in slots:
        request = _build_request(slot)
        result = service.fetch_slot(request)
        cross_max = max((i.cross_source_count for i in result.items), default=0)
        ok = result.error is None and len(result.items) >= min_count
        slot_result = BatchSlotResult(
            slot=slot,
            cache_key=request.cache_key(),
            count=len(result.items),
            cached=result.cached,
            cross_source_max=cross_max,
            error=result.error,
            ok=ok,
        )
        summary.results.append(slot_result)
        if ok:
            summary.succeeded += 1
        else:
            summary.failed += 1

    return summary


def run_demo_batch(
    force: bool = False,
    accounts_path: Optional[str] = None,
    min_count: int = 1,
) -> BatchFetchSummary:
    """
    运行内置 Demo 槽位队列。

    @param force: 全部槽位强制重拉
    @param accounts_path: 可选配置路径
    @param min_count: 成功最少条数
    @returns: BatchFetchSummary
    """
    slots = [
        BatchSlot(
            tmdb_id=s.tmdb_id,
            media_type=s.media_type,
            season=s.season,
            episode=s.episode,
            force=force or s.force,
        )
        for s in DEFAULT_DEMO_SLOTS
    ]
    return run_batch_fetch(slots, accounts_path=accounts_path, min_count=min_count)
