#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch 槽位处理流水线。

@module workflow.storage.pipeline
@description
  总控 orchestration：拉取 → 评分 → 写入 MySQL →（后续）生成 HTML → sync D1。

  当前阶段（R0）：
    - demo: 使用 scorer 内置 Demo 数据写入 MySQL
    - query: 从 MySQL 读取并输出 Jinja2 上下文
    - fetch: 预留 torrent_sources 接入（--fetch 时调用）
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import STORAGE_BACKEND, SITE_ORIGIN
from workflow.recommended.scorer import rank_items
from workflow.storage.mysql_store import MySQLStore


def _demo_items_for_slot(
    tmdb_id: int,
    season: Optional[int],
    episode: Optional[int],
) -> List[Dict[str, Any]]:
    """
    返回与 portal 演示页一致的 Demo ResourceItem 列表。

    @param tmdb_id: TMDB ID
    @param season: 季号
    @param episode: 集号
    @returns: ResourceItem 字典列表
    """
    if tmdb_id == 1396 and season == 4 and episode == 6:
        return [
            {
                "infohash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "title_raw": "Breaking.Bad.S04E06.1080p.WEB-DL.DDP5.1.H.264-NTb",
                "release_group": "NTb",
                "source": "WEB-DL（Amazon Prime US）",
                "resolution": "1080p",
                "codec": "H.264",
                "video_spec": "H.264 1080p ~8 Mbps",
                "audio_spec": "DDP5.1 @ 640 kbps",
                "size_bytes": 2576980378,
                "seeders": 24,
                "peers": 30,
                "magnet_uri": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "indexer": "jackett",
                "cross_source_count": 3,
                "cross_source_confidence": 1.0,
            },
            {
                "infohash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "title_raw": "Breaking.Bad.S04E06.1080p.WEB-DL.H.264-HiFi",
                "release_group": "HiFi",
                "source": "WEB-DL",
                "resolution": "1080p",
                "codec": "H.264",
                "video_spec": "H.264 1080p",
                "audio_spec": "DDP5.1",
                "size_bytes": 2469606195,
                "seeders": 18,
                "peers": 22,
                "magnet_uri": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexer": "eztv",
                "cross_source_count": 2,
                "cross_source_confidence": 0.67,
            },
            {
                "infohash": "cccccccccccccccccccccccccccccccccccccccc",
                "title_raw": "Breaking.Bad.S04E06.720p.WEB-DL.H.264-BTN",
                "release_group": "BTN",
                "source": "WEB-DL",
                "resolution": "720p",
                "codec": "H.264",
                "video_spec": "H.264 720p",
                "audio_spec": "DDP5.1",
                "size_bytes": 1181116006,
                "seeders": 31,
                "peers": 35,
                "magnet_uri": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
                "indexer": "jackett",
                "cross_source_count": 2,
                "cross_source_confidence": 0.67,
            },
            {
                "infohash": "dddddddddddddddddddddddddddddddddddddddd",
                "title_raw": "Breaking.Bad.S04E06.1080p.BluRay.x264-ROVERS",
                "release_group": "ROVERS",
                "source": "BluRay",
                "resolution": "1080p",
                "codec": "x264",
                "video_spec": "x264 1080p",
                "audio_spec": "DTS-HD MA 5.1",
                "size_bytes": 4402341478,
                "seeders": 9,
                "peers": 12,
                "magnet_uri": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
                "indexer": "jackett",
                "cross_source_count": 1,
                "cross_source_confidence": 0.33,
            },
        ]
    return []


def run_slot_pipeline(
    tmdb_id: int,
    media_kind: str = "tv",
    season: Optional[int] = None,
    episode: Optional[int] = None,
    mode: str = "demo",
    fetch: bool = False,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    执行单槽位 pipeline：评分 → 写入存储 → 返回摘要。

    @param tmdb_id: TMDB 作品 ID
    @param media_kind: tv | movie
    @param season: 季号（剧集必填）
    @param episode: 集号（剧集必填）
    @param mode: demo | live（live 需 --fetch）
    @param fetch: 是否调用 torrent_sources 拉取（R1）
    @param title: 可选 slot 标题（扩槽时来自 TMDB 导出）
    @returns: pipeline 结果 JSON
    """
    if STORAGE_BACKEND != "mysql":
        return {
            "ok": False,
            "error": f"当前 STORAGE_BACKEND={STORAGE_BACKEND}；本地测试请设 RM_STORAGE_BACKEND=mysql",
        }

    store = MySQLStore()
    ping = store.ping()
    if not ping.get("ok"):
        return {"ok": False, "step": "db_ping", "detail": ping}

    media_type = "tv_episode" if media_kind == "tv" else "movie"
    page_id = store.resolve_page_id(tmdb_id, media_kind, season, episode)
    ensure_result = store.ensure_slot_page(
        tmdb_id, media_kind, season, episode, title=title
    )

    items: List[Dict[str, Any]] = []
    fetch_note = ""
    cross_source_page_count: Optional[int] = None
    cross_source_page_total: Optional[int] = None

    if fetch:
        from workflow.metadata.tmdb_api import enrich_external_ids
        from workflow.torrent_sources.fetch_service import FetchService
        from workflow.torrent_sources.models import FetchMode, FetchRequest, MediaType

        ext = enrich_external_ids(tmdb_id, media_kind, title=title)
        mt = MediaType.MOVIE if media_kind == "movie" else MediaType.TV
        request = FetchRequest(
            tmdb_id=tmdb_id,
            media_type=mt,
            season=season,
            episode=episode,
            imdb_id=ext.get("imdb_id"),
            tvdb_id=ext.get("tvdb_id"),
            title=title or ext.get("title"),
            mode=FetchMode.ON_DEMAND,
            force=False,
        )
        fetch_result = FetchService().fetch_slot(request)
        cross_source_page_count = fetch_result.cross_source_page_count
        cross_source_page_total = fetch_result.cross_source_page_total
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
    elif mode == "demo":
        items = _demo_items_for_slot(tmdb_id, season, episode)
    else:
        return {"ok": False, "error": "live 模式需 --fetch（R1 实现 jackett 编排）"}

    if not items:
        return {
            "ok": False,
            "page_id": page_id,
            "error": "无可用 items；请先 db seed 或使用已知 Demo 槽位 1396/4/6",
        }

    from workflow.torrent_sources.release_parser import enrich_item_dict

    for it in items:
        enrich_item_dict(it, force_specs=True)

    ranked = rank_items(items, media_kind=media_kind)
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
        source="pipeline_demo" if mode == "demo" else "pipeline_fetch",
        slots_processed=1,
        resources_upserted=write_result["resources_upserted"],
        pages_published=1 if write_result["magnet_count"] >= 2 else 0,
    )

    ctx = store.get_episode_page_context(page_id)
    template_preview = None
    if ctx:
        template_preview = {
            "show_title": ctx.catalog.title,
            "source_count": len(ctx.sources),
            "recommended": ctx.recommended.title_raw if ctx.recommended else None,
            "cross_source_count": ctx.page.cross_source_count,
            "cross_source_total": ctx.page.cross_source_total,
            "robots_noindex": not ctx.page.is_indexable(),
        }

    return {
        "ok": True,
        "backend": STORAGE_BACKEND,
        "page_id": page_id,
        "ensure": ensure_result,
        "mode": mode,
        "fetch_note": fetch_note or None,
        "ranked_top": {
            "title_raw": ranked[0].title_raw,
            "score": ranked[0].score,
            "group_tier": ranked[0].group_tier,
        },
        "write": write_result,
        "sync_run_id": run_id,
        "template_preview": template_preview,
    }


def run_batch_slot_pipeline(
    slots: List[Dict[str, Any]],
    *,
    mode: str = "live",
    fetch: bool = True,
    skip_existing: bool = True,
    warm_tmdb: bool = True,
) -> Dict[str, Any]:
    """
    批量执行 slot pipeline（扩槽 benchmark 清单）。

    @param slots: 每项含 tmdb_id、media_type、可选 season/episode、label
    @param mode: demo | live
    @param fetch: 是否拉取 torrent
    @param skip_existing: 跳过已有 >=2 magnet 的页面
    @param warm_tmdb: 批量前预热 TMDB external_ids 缓存
    @returns: 批次摘要 JSON
    """
    if STORAGE_BACKEND != "mysql":
        return {
            "ok": False,
            "error": f"当前 STORAGE_BACKEND={STORAGE_BACKEND}；请设 RM_STORAGE_BACKEND=mysql",
        }

    store = MySQLStore()
    ping = store.ping()
    if not ping.get("ok"):
        return {"ok": False, "step": "db_ping", "detail": ping}

    tmdb_warm: Optional[Dict[str, Any]] = None
    if warm_tmdb and fetch:
        from workflow.metadata.tmdb_api import warm_external_ids_cache

        tmdb_warm = warm_external_ids_cache(slots)

    results: List[Dict[str, Any]] = []
    ok_count = 0
    skip_count = 0
    fail_count = 0

    for slot in slots:
        label = str(slot.get("label") or "")
        tmdb_id = int(slot["tmdb_id"])
        media_kind = str(slot.get("media_type") or slot.get("media_kind") or "tv")
        season = slot.get("season")
        episode = slot.get("episode")
        page_id = store.resolve_page_id(
            tmdb_id,
            media_kind,
            int(season) if season is not None else None,
            int(episode) if episode is not None else None,
        )

        if skip_existing and store.page_has_resources(page_id):
            skip_count += 1
            results.append({"label": label, "page_id": page_id, "status": "skipped_existing"})
            continue

        one = run_slot_pipeline(
            tmdb_id=tmdb_id,
            media_kind=media_kind,
            season=int(season) if season is not None else None,
            episode=int(episode) if episode is not None else None,
            mode=mode,
            fetch=fetch,
            title=slot.get("title") or slot.get("label"),
        )
        entry = {
            "label": label,
            "page_id": page_id,
            "status": "ok" if one.get("ok") else "failed",
            "result": one,
        }
        results.append(entry)
        if one.get("ok"):
            ok_count += 1
        else:
            fail_count += 1

    run_id = str(uuid.uuid4())
    store.record_sync_run(
        run_id=run_id,
        source="pipeline_batch",
        slots_processed=len(slots),
        resources_upserted=sum(
            int(r.get("result", {}).get("write", {}).get("resources_upserted") or 0)
            for r in results
            if r.get("status") == "ok"
        ),
        pages_published=ok_count,
    )

    report = {
        "ok": fail_count == 0,
        "total": len(slots),
        "ok_count": ok_count,
        "skip_count": skip_count,
        "fail_count": fail_count,
        "sync_run_id": run_id,
        "tmdb_warm": tmdb_warm,
        "results": results,
    }
    return report


def _resource_item_dict(resource: Any) -> Dict[str, Any]:
    """
    将 DownloadResource ORM 行转为 scorer 输入字典（含 spec 回填）。

    @param resource: DownloadResource 实例
    @returns: rank_items 可用的 item 字典
    """
    from workflow.torrent_sources.release_parser import enrich_item_dict

    item = {
        "infohash": resource.infohash,
        "title_raw": resource.title_raw,
        "seeders": resource.seeders,
        "release_group": resource.release_group,
        "cross_source_count": resource.cross_source_count,
        "resolution": resource.resolution,
        "codec": resource.codec,
        "source": resource.source,
        "size_bytes": resource.size_bytes,
        "magnet_uri": resource.magnet_uri,
        "indexer": resource.indexer,
        "cross_source_confidence": resource.cross_source_confidence,
        "video_spec": resource.video_spec,
        "audio_spec": resource.audio_spec,
    }
    return enrich_item_dict(item, force_specs=True)


def rescore_page_recommendations(
    page_id: str,
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    不重拉 torrent：用 DB 现有 resources 重算 Recommended 并写回。

    @param page_id: movie:… 或 tv:…:sXXeYY
    @param store: 可选 MySQLStore
    @returns: 重算摘要 JSON
    """
    store = store or MySQLStore()
    media_kind = "movie" if page_id.startswith("movie:") else "tv"
    media_type = "movie" if media_kind == "movie" else "tv_episode"

    if media_kind == "movie":
        ctx = store.get_movie_page_context(page_id)
        if not ctx:
            return {"ok": False, "page_id": page_id, "error": "电影页不存在"}
        tmdb_id = ctx.catalog.tmdb_id
        season: Optional[int] = None
        episode: Optional[int] = None
    else:
        ctx = store.get_episode_page_context(page_id)
        if not ctx:
            return {"ok": False, "page_id": page_id, "error": "剧集页不存在"}
        tmdb_id = ctx.catalog.tmdb_id
        season = ctx.page.season
        episode = ctx.page.episode

    if not ctx.sources:
        return {
            "ok": False,
            "page_id": page_id,
            "error": "无 download_resources，无法重算",
        }

    old_rec = ctx.recommended.title_raw if ctx.recommended else None
    old_score = ctx.recommended.match_score if ctx.recommended else None
    items = [_resource_item_dict(r) for r in ctx.sources]
    ranked = rank_items(items, media_kind=media_kind)
    write = store.upsert_slot_resources(
        page_id=page_id,
        tmdb_id=tmdb_id,
        media_type=media_type,
        season=season,
        episode=episode,
        items=items,
        ranked=ranked,
        cross_source_page_count=ctx.page.cross_source_count,
        cross_source_page_total=ctx.page.cross_source_total,
    )

    ctx2 = (
        store.get_movie_page_context(page_id)
        if media_kind == "movie"
        else store.get_episode_page_context(page_id)
    )
    new_rec = ctx2.recommended.title_raw if ctx2 and ctx2.recommended else None
    new_score = ctx2.recommended.match_score if ctx2 and ctx2.recommended else None
    new_seeders = ctx2.recommended.seeders if ctx2 and ctx2.recommended else None

    return {
        "ok": True,
        "page_id": page_id,
        "media_kind": media_kind,
        "resources": len(items),
        "changed": old_rec != new_rec or old_score != new_score,
        "old_recommended": old_rec,
        "old_score": old_score,
        "new_recommended": new_rec,
        "new_score": new_score,
        "new_seeders": new_seeders,
        "write": write,
    }


def rescore_published_pages(
    *,
    media_kind: Optional[str] = None,
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    批量重算 published 页的 Recommended（不重拉）。

    @param media_kind: None=全部 · tv · movie
    @param store: 可选 MySQLStore
    @returns: 批次摘要
    """
    store = store or MySQLStore()
    results: List[Dict[str, Any]] = []
    ok_count = 0
    changed_count = 0
    fail_count = 0

    for page_id in store.list_published_page_ids():
        if media_kind == "movie" and not page_id.startswith("movie:"):
            continue
        if media_kind == "tv" and not page_id.startswith("tv:"):
            continue

        one = rescore_page_recommendations(page_id, store=store)
        results.append(one)
        if one.get("ok"):
            ok_count += 1
            if one.get("changed"):
                changed_count += 1
        else:
            fail_count += 1

    return {
        "ok": fail_count == 0,
        "media_kind": media_kind or "all",
        "total": len(results),
        "ok_count": ok_count,
        "changed_count": changed_count,
        "fail_count": fail_count,
        "results": results,
    }


def load_slots_json(path: Path) -> List[Dict[str, Any]]:
    """
    从 benchmark slot JSON 加载槽位列表。

    @param path: tmdb-benchmark-slots.json 路径
    @returns: slot 字典列表
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "slots" in data:
        return list(data["slots"])
    if isinstance(data, list):
        return data
    raise ValueError(f"无法解析 slot JSON: {path}")


def query_page_context(page_id: str) -> Dict[str, Any]:
    """
    从 MySQL 读取页面上下文并转为 JSON（供 query CLI / 生成器调试）。

    @param page_id: 如 tv:1396:s04e06
    @returns: 含 template_context 的字典
    """
    if STORAGE_BACKEND != "mysql":
        return {"ok": False, "error": f"query 当前仅支持 mysql，当前为 {STORAGE_BACKEND}"}

    store = MySQLStore()
    ctx = store.get_episode_page_context(page_id)
    if not ctx:
        return {"ok": False, "page_id": page_id, "error": "页面不存在或非 episode 类型"}

    template = ctx.to_template_context(site_origin=SITE_ORIGIN)
    return {
        "ok": True,
        "page_id": page_id,
        "magnet_count": ctx.page.magnet_count,
        "page_status": ctx.page.page_status,
        "template_context": template,
    }
