#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面 IG 分级 Debug 面板数据组装。

@module portal.generator.ig_debug
@description
  当 RM_SHOW_IG_DEBUG=1 时，为 Jinja2 模板提供按区块登记的 IG-ID / 等级 / 字段 / 取值，
  便于本地与生成器测试对照 IG信息登记册。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from schema.d1_models import (
    DownloadResource,
    EpisodePageContext,
    MoviePageContext,
    ShowHubPageContext,
)

# 页面上下文联合类型（与 render.PageContext 对齐）
PageContextUnion = Union[EpisodePageContext, MoviePageContext, ShowHubPageContext]


def _ig_entry(
    *,
    ig_id: str,
    tier: str,
    name: str,
    field: str,
    value: Any,
    block: str,
    present: bool = True,
) -> Dict[str, Any]:
    """
    构造单条 IG debug 登记行。

    @param ig_id: 如 S-06
    @param tier: S | A | B | C
    @param name: 信息名称
    @param field: 字段路径
    @param value: 当前页面取值（展示用字符串化）
    @param block: 页面区块名
    @param present: 页面上是否已呈现该信息
    @returns: 模板用字典
    """
    text = str(value) if value is not None and value != "" else "—"
    if len(text) > 120:
        text = text[:117] + "..."
    return {
        "ig_id": ig_id,
        "tier": tier,
        "name": name,
        "field": field,
        "value": text,
        "block": block,
        "present": present,
    }


def _estimate_page_ig(tier_counts: Dict[str, int], *, has_speed: bool) -> str:
    """
    根据已呈现字段粗估页面 IG 分档（对照登记册 §九）。

    @param tier_counts: 各等级 present=True 的条数
    @param has_speed: 是否含 Phase2 测速证据
    @returns: 如 8~9
    """
    s_count = tier_counts.get("S", 0)
    a_count = tier_counts.get("A", 0)
    if s_count >= 5 and has_speed:
        return "8~9"
    if s_count >= 3 and a_count >= 3:
        return "7~8"
    if s_count >= 1 and a_count >= 2:
        return "5~7"
    if a_count >= 1:
        return "2~4"
    return "0~1"


def _entries_for_resource(
    res: DownloadResource,
    *,
    block: str,
    is_hero: bool = False,
) -> List[Dict[str, Any]]:
    """
    单条 download_resources 行的 IG 登记。

    @param res: 资源行
    @param block: 页面区块
    @param is_hero: 是否为 Recommended 块（S 级字段更全）
    @returns: IG debug 行列表
    """
    rows: List[Dict[str, Any]] = []
    prefix = "recommended." if is_hero else "sources[]."

    if is_hero:
        rows.append(
            _ig_entry(
                ig_id="S-01",
                tier="S",
                name="Recommended Release",
                field=f"{prefix}is_recommended",
                value=res.is_recommended,
                block=block,
                present=bool(res.is_recommended),
            )
        )
        rows.append(
            _ig_entry(
                ig_id="S-02",
                tier="S",
                name="推荐理由",
                field=f"{prefix}recommend_reason",
                value=res.recommend_reason,
                block=block,
                present=bool(res.recommend_reason),
            )
        )
        rows.append(
            _ig_entry(
                ig_id="S-05",
                tier="S",
                name="Release Group 信誉",
                field=f"{prefix}group_tier",
                value=res.group_tier,
                block=block,
                present=bool(res.group_tier),
            )
        )

    rows.extend(
        [
            _ig_entry(
                ig_id="S-04",
                tier="S",
                name="单条跨源置信度",
                field=f"{prefix}cross_source_count",
                value=f"{res.cross_source_count} (conf={res.cross_source_confidence:.2f})",
                block=block,
                present=res.cross_source_count > 0,
            ),
            _ig_entry(
                ig_id="A-05",
                tier="A",
                name="Release 质量解析",
                field=f"{prefix}resolution/codec/source",
                value=f"{res.resolution} · {res.codec} · {res.source}",
                block=block,
                present=bool(res.resolution or res.codec or res.source),
            ),
            _ig_entry(
                ig_id="A-06",
                tier="A",
                name="压制组名",
                field=f"{prefix}release_group",
                value=res.release_group or res.title_raw[:40],
                block=block,
                present=bool(res.release_group or res.title_raw),
            ),
            _ig_entry(
                ig_id="A-08",
                tier="A",
                name="匹配排序分",
                field=f"{prefix}match_score",
                value=round(res.match_score, 2),
                block=block,
                present=res.match_score > 0,
            ),
            _ig_entry(
                ig_id="B-02",
                tier="B",
                name="索引 seeders",
                field=f"{prefix}seeders",
                value=res.seeders,
                block=block,
                present=True,
            ),
            _ig_entry(
                ig_id="B-01",
                tier="B",
                name="magnet 列表项",
                field=f"{prefix}infohash",
                value=res.infohash[:12] + "…",
                block=block,
                present=bool(res.infohash),
            ),
            _ig_entry(
                ig_id="B-05",
                tier="B",
                name="来源 indexer",
                field=f"{prefix}indexer",
                value=res.indexer,
                block=block,
                present=bool(res.indexer),
            ),
        ]
    )
    return rows


def _entries_for_speed_evidence(
    speed_evidence: Dict[str, Any],
    *,
    block: str = "测速证据面板",
) -> List[Dict[str, Any]]:
    """
    speed_evidence 模板变量的 IG 登记。

    @param speed_evidence: SpeedEvidenceContext.to_template_dict() 结果
    @param block: 页面区块
    @returns: IG debug 行列表
    """
    if not speed_evidence:
        return []

    return [
        _ig_entry(
            ig_id="RM-GI",
            tier="S",
            name="RM Grab 指数",
            field="grab_index_score / breakdown",
            value=(
                f"{speed_evidence.get('grab_index_score')}（{speed_evidence.get('grab_index_tier_label')}）"
                f" · {speed_evidence.get('grab_index_summary')}"
            ),
            block=block,
            present=bool(speed_evidence.get("grab_index_has_data")),
        ),
        _ig_entry(
            ig_id="S-06",
            tier="S",
            name="实测下载速度",
            field="avg_kbps / max_kbps",
            value=speed_evidence.get("speed_pair_display"),
            block=block,
            present=bool(speed_evidence.get("avg_speed")),
        ),
        _ig_entry(
            ig_id="S-07",
            tier="S",
            name="Recommended 实测背书",
            field="recommended.infohash + speed",
            value=f"infohash …{speed_evidence.get('infohash_short')}",
            block=block,
            present=bool(speed_evidence.get("infohash_short")),
        ),
        _ig_entry(
            ig_id="A-01",
            tier="A",
            name="Peer 可达性等级",
            field="speed_evidence.reachability + peers",
            value=speed_evidence.get("reachability_display"),
            block=block,
            present=bool(speed_evidence.get("reachability")),
        ),
        _ig_entry(
            ig_id="A-02",
            tier="A",
            name="实测 peer 数量",
            field="peers_total / peers_reachable / connect_rate",
            value=(
                f"total={speed_evidence.get('peers_total_display')} · "
                f"connected={speed_evidence.get('peers_reachable_display')} · "
                f"rate={speed_evidence.get('connect_rate_pct')}"
            ),
            block=block,
            present=int(speed_evidence.get("peers_total") or 0) > 0,
        ),
        _ig_entry(
            ig_id="A-03",
            tier="A",
            name="测速 freshness",
            field="speed_evidence.tested_at / validity",
            value=(
                f"{speed_evidence.get('tested_at')} · {speed_evidence.get('age_display')} · "
                f"{speed_evidence.get('validity_level')}/{speed_evidence.get('freshness_label')}"
            ),
            block=block,
            present=bool(speed_evidence.get("tested_at")),
        ),
        _ig_entry(
            ig_id="A-09",
            tier="A",
            name="首包延迟",
            field="speed_evidence.latency_ms",
            value=speed_evidence.get("latency_display"),
            block=block,
            present=int(speed_evidence.get("latency_ms") or 0) > 0,
        ),
        _ig_entry(
            ig_id="A-10",
            tier="A",
            name="索引 vs 实测对比",
            field="speed_evidence.index_vs_measured",
            value=speed_evidence.get("index_vs_measured"),
            block=block,
            present=bool(speed_evidence.get("index_vs_measured")),
        ),
    ]


def build_ig_debug_panel(
    ctx: PageContextUnion,
    template_vars: Dict[str, Any],
) -> Dict[str, Any]:
    """
    从页面上下文与已组装的模板变量构建 IG debug 面板。

    @param ctx: Episode / Movie / ShowHub 页面上下文
    @param template_vars: to_template_context 返回值
    @returns: ig_debug 模板字典
    """
    entries: List[Dict[str, Any]] = []
    page_id = ""
    page_type = "unknown"

    if isinstance(ctx, EpisodePageContext):
        page_type = "episode"
        page_id = ctx.page.page_id
        entries.append(
            _ig_entry(
                ig_id="S-03",
                tier="S",
                name="跨源验证 N/M",
                field="page.cross_source_count/total",
                value=f"{ctx.page.cross_source_count}/{ctx.page.cross_source_total}",
                block="Hero",
                present=ctx.page.cross_source_total > 0,
            )
        )
        entries.append(
            _ig_entry(
                ig_id="B-06",
                tier="B",
                name="TMDB 元数据",
                field="catalog.title / tmdb_url",
                value=ctx.catalog.title,
                block="侧栏 TMDB",
                present=bool(ctx.catalog.title),
            )
        )

        speed_evidence = template_vars.get("speed_evidence")
        entries.extend(_entries_for_speed_evidence(speed_evidence or {}))

        if ctx.recommended:
            entries.extend(
                _entries_for_resource(ctx.recommended, block="Recommended Release", is_hero=True)
            )
            if template_vars.get("recommended", {}).get("speed_endorsement"):
                entries.append(
                    _ig_entry(
                        ig_id="S-07",
                        tier="S",
                        name="Recommended 实测背书（文案）",
                        field="recommended.speed_endorsement",
                        value=template_vars["recommended"]["speed_endorsement"][:80] + "…",
                        block="Recommended Release",
                        present=True,
                    )
                )

        # Sources 表：登记首条 + 汇总条数（避免 debug 面板过长）
        if ctx.sources:
            entries.extend(
                _entries_for_resource(ctx.sources[0], block="All Sources（首行样例）", is_hero=False)
            )
            entries.append(
                _ig_entry(
                    ig_id="B-01",
                    tier="B",
                    name="magnet 列表",
                    field="sources.length",
                    value=f"{len(ctx.sources)} 条",
                    block="All Sources 表",
                    present=len(ctx.sources) >= 2,
                )
            )

        if len(ctx.sources) < 2:
            entries.append(
                _ig_entry(
                    ig_id="C-01",
                    tier="C",
                    name="薄页门禁",
                    field="sources.length",
                    value=len(ctx.sources),
                    block="全页",
                    present=False,
                )
            )

    elif isinstance(ctx, MoviePageContext):
        page_type = "movie"
        page_id = ctx.page.page_id
        if ctx.recommended:
            entries.extend(
                _entries_for_resource(ctx.recommended, block="Recommended Release", is_hero=True)
            )
        speed_evidence = template_vars.get("speed_evidence")
        entries.extend(_entries_for_speed_evidence(speed_evidence or {}))
        entries.append(
            _ig_entry(
                ig_id="B-06",
                tier="B",
                name="TMDB 元数据",
                field="catalog.title",
                value=ctx.catalog.title,
                block="侧栏",
                present=bool(ctx.catalog.title),
            )
        )

    elif isinstance(ctx, ShowHubPageContext):
        page_type = "show_hub"
        page_id = ctx.page.page_id
        entries.append(
            _ig_entry(
                ig_id="B-06",
                tier="B",
                name="TMDB 作品 Hub",
                field="catalog.title",
                value=ctx.catalog.title,
                block="Hub",
                present=bool(ctx.catalog.title),
            )
        )

    tier_counts: Dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0}
    for row in entries:
        if row.get("present"):
            tier = str(row.get("tier", "B"))
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

    by_block: Dict[str, List[Dict[str, Any]]] = {}
    for row in entries:
        by_block.setdefault(row["block"], []).append(row)

    has_speed = bool(template_vars.get("speed_evidence"))

    return {
        "page_id": page_id,
        "page_type": page_type,
        "entries": entries,
        "by_block": by_block,
        "tier_counts": tier_counts,
        "ig_estimate": _estimate_page_ig(tier_counts, has_speed=has_speed),
        "config_env": "RM_SHOW_IG_DEBUG",
        "entry_count": len(entries),
        "present_count": sum(1 for e in entries if e.get("present")),
    }
