#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面 UI 国际化（en / zh）。

@module portal.generator.i18n
@description
  生成器模板通过 ``t('key')`` 取文案；``RM_SITE_I18N_ENABLED=true`` 时注入前端切换 catalog。
  ``RM_SITE_LOCALE`` 决定关闭 i18n 时的唯一语言，或开启 i18n 时的默认语言。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# 支持的语言代码（内部归一化为 en | zh）
SUPPORTED_LOCALES = frozenset({"en", "zh"})

# UI 文案表：key -> {en, zh}
MESSAGES: Dict[str, Dict[str, str]] = {
    # ── 站点 / SEO 默认 ──
    "site.title": {
        "en": "ReleaseMatch — Release Guide",
        "zh": "ReleaseMatch — Release 导航站",
    },
    "site.meta_default": {
        "en": "Release guide: Recommended Release, edition matching, and multi-source comparison.",
        "zh": "影视 Release 导航：Recommended Release、对版分析与多源对比。",
    },
    "site.home_meta": {
        "en": "Release guide: 100+ verified slots, Recommended Release, edition analysis, and multi-source magnets.",
        "zh": "影视 Release 导航：100+ 验证集槽位，Recommended Release、对版分析与多源 magnet 对比。",
    },
    # ── 导航 ──
    "nav.home": {"en": "Home", "zh": "首页"},
    "nav.how": {"en": "How matching works", "zh": "对版说明"},
    "nav.about": {"en": "About", "zh": "关于"},
    "nav.menu_open": {"en": "Open menu", "zh": "打开菜单"},
    "nav.home_aria": {"en": "ReleaseMatch home", "zh": "ReleaseMatch 首页"},
    "nav.main": {"en": "Main navigation", "zh": "主导航"},
    "nav.mobile": {"en": "Mobile navigation", "zh": "移动端导航"},
    "lang.switch": {"en": "Language", "zh": "语言"},
    "lang.en": {"en": "English", "zh": "English"},
    "lang.zh": {"en": "中文", "zh": "中文"},
    # ── 页脚 ──
    "footer.desc": {
        "en": "Release guide: pick the right release with edition analysis and quality notes. We do not host video; only public metadata.",
        "zh": "Release 导航站：帮助你在众多压制版本中选对 release，并提供对版分析与质量说明。不托管视频，仅索引公开元数据。",
    },
    "footer.trust": {"en": "Trust", "zh": "Trust"},
    "footer.notes": {"en": "Notes", "zh": "说明"},
    "footer.cross_verified": {
        "en": "Multi-source coverage & verification",
        "zh": "多源检索覆盖与交叉验证",
    },
    "footer.copyright": {
        "en": "© {year} ReleaseMatch · No video hosting · Magnet links rel=\"nofollow\"",
        "zh": "© {year} ReleaseMatch · 不托管视频内容 · Magnet 链接 rel=\"nofollow\"",
    },
    # ── 表格列 ──
    "table.release": {"en": "Release", "zh": "Release"},
    "table.quality": {"en": "Quality", "zh": "Quality"},
    "table.group": {"en": "Group", "zh": "Group"},
    "table.cross": {"en": "Verify", "zh": "验证"},
    "table.size": {"en": "Size", "zh": "Size"},
    "table.seed": {"en": "Seed", "zh": "Seed"},
    "table.action": {"en": "Action", "zh": "操作"},
    "table.source": {"en": "Source", "zh": "Source"},
    "table.video": {"en": "Video", "zh": "Video"},
    "table.audio": {"en": "Audio", "zh": "Audio"},
    # ── Badge ──
    "badge.recommended": {"en": "Site pick", "zh": "本站推荐"},
    "badge.edition_pick": {"en": "Best in edition", "zh": "本组最佳"},
    "badge.cross_page": {
        "en": "{count}/{total} sources with results",
        "zh": "{count}/{total} 源有结果",
    },
    "badge.cross_page_title": {
        "en": "S-03: {count} of {total} queried source families returned at least one release (coverage, not same-hash verification)",
        "zh": "S-03：在 {total} 个检索源族中，{count} 个至少返回 1 条 release（覆盖/可得性，非同一 hash 验证）",
    },
    "badge.group_tier_title": {
        "en": "Release Group tier {tier}",
        "zh": "Release Group 信誉 {tier}",
    },
    "badge.cross_item_title": {
        "en": "S-04: cross-verified on {count} source families (same release / infohash alignment)",
        "zh": "S-04：跨 {count} 个源族交叉验证（同一 release / infohash 对齐）",
    },
    "badge.cross_single_title": {
        "en": "Seen on one source family only (no cross-verification badge)",
        "zh": "仅在单一源族出现（无交叉验证标记）",
    },
    # ── Recommended ──
    "recommended.title": {"en": "Recommended Release", "zh": "Recommended Release"},
    "recommended.reason": {"en": "Why this release:", "zh": "推荐理由："},
    "recommended.endorsement": {"en": "Speed evidence:", "zh": "实测背书："},
    "recommended.speed_title": {"en": "Avg / peak speed", "zh": "均速 / 峰值"},
    "recommended.unavailable_title": {
        "en": "Recommended Release unavailable",
        "zh": "Recommended Release 暂不可用",
    },
    "recommended.unavailable_body": {
        "en": "Fewer than 2 public releases (or data degraded). Check All Sources below, revisit later, or see Scarcity tracking on the home page.",
        "zh": "公开源暂不足 2 条 release（或数据已降级），本站持续追踪。请查看下方 All Sources、稍后回访，或从首页「稀缺追踪」了解进展。",
    },
    # ── Torrent metadata（Phase 2 swarm 结构） ──
    "torrent.panel.summary": {
        "en": "Torrent structure (from swarm metadata)",
        "zh": "Torrent 结构（swarm metadata）",
    },
    "torrent.panel.files_short": {"en": "files", "zh": "个文件"},
    "torrent.panel.title": {"en": "Torrent structure", "zh": "Torrent 结构"},
    "torrent.method_note": {
        "en": "Read from swarm metadata during speed test — same fields as a .torrent info dict (not MediaInfo).",
        "zh": "测速时从 swarm 读取 metadata，等价 .torrent info 字典（非 MediaInfo 容器解析）。",
    },
    "torrent.field.name": {"en": "Name", "zh": "名称"},
    "torrent.field.total_size": {"en": "Swarm total size", "zh": "Swarm 总大小"},
    "torrent.field.indexer_size": {"en": "Indexer reported size", "zh": "Indexer 报告大小"},
    "torrent.field.size_match": {"en": "Size cross-check", "zh": "体积交叉验证"},
    "torrent.field.files": {"en": "File count", "zh": "文件数"},
    "torrent.field.primary": {"en": "Primary video file", "zh": "主视频文件"},
    "torrent.field.piece": {"en": "Piece length", "zh": "Piece 大小"},
    "torrent.field.private": {"en": "Private torrent", "zh": "Private"},
    "torrent.private.yes": {"en": "Yes", "zh": "是"},
    "torrent.files.title": {"en": "Video files", "zh": "视频文件"},
    "torrent.files.ancillary_note": {
        "en": "{count} non-video files hidden",
        "zh": "另有 {count} 个非视频文件未列出",
    },
    "torrent.extracted_at": {"en": "Extracted at", "zh": "提取时间"},
    "torrent.size_match.ok": {"en": "Matches indexer", "zh": "与 indexer 一致"},
    "torrent.size_match.mismatch": {"en": "Differs from indexer", "zh": "与 indexer 不一致"},
    "torrent.size_match.unknown": {"en": "Not compared", "zh": "未对比"},
    # ── 剧集页 ──
    "episode.breadcrumb": {"en": "Breadcrumb", "zh": "面包屑"},
    # SEO desc 由 build_episode_meta_description 组装；下列 key 作文档/回退
    "episode.meta_description": {
        "en": "{show} S{season:02d}E{episode:02d} torrent sources: {recommended_clause} and {count} matched downloads.",
        "zh": "{show} S{season:02d}E{episode:02d} torrent sources：{recommended_clause}，共 {count} 条 matched downloads。",
    },
    "episode.season_episode": {
        "en": "Season {season} · Episode {episode}",
        "zh": "第 {season} 季 · 第 {episode} 集",
    },
    "episode.hero_title": {
        "en": "{show} S{season:02d}E{episode:02d} — Release-Matched Sources",
        "zh": "{show} S{season:02d}E{episode:02d} — Release-Matched Sources",
    },
    "episode.hero_lead": {
        "en": "Matched torrent releases for this episode — pick Recommended, not just any magnet.",
        "zh": "本集 matched torrent releases：优先 Recommended，而非任意 magnet。",
    },
    "episode.sources_heading": {
        "en": "All torrent sources ({count} matched)",
        "zh": "All torrent sources（{count} matched）",
    },
    "episode.prev": {"en": "Previous", "zh": "上一集"},
    "episode.next": {"en": "Next", "zh": "下一集"},
    "episode.season_nav": {"en": "Season {season}", "zh": "第 {season} 季"},
    "episode.episode_nav": {"en": "Episode navigation", "zh": "同季集导航"},
    "episode.about": {"en": "About This Episode", "zh": "About This Episode"},
    "episode.watch_on": {"en": "Watch On", "zh": "Watch On"},
    "episode.subtitles": {"en": "Matched Subtitles", "zh": "Matched Subtitles"},
    "episode.subtitles_desc": {
        "en": "Our recommended release can pair with the subtitle page below (cross-site link).",
        "zh": "本站推荐 release 可与以下字幕页配对使用（跨站单链协同）。",
    },
    "episode.tmdb_cta": {"en": "View on TMDB", "zh": "在 TMDB 查看"},
    "episode.poster_alt": {"en": "{title} poster", "zh": "{title} 海报"},
    # ── 电影页 ──
    # SEO desc 由 build_movie_meta_description 组装；下列 key 作文档/回退
    "movie.meta_description": {
        "en": "{title} ({year}) torrent sources: {recommended_clause} and {count} edition comparisons (WEB-DL / BluRay / REMUX).",
        "zh": "{title} ({year}) torrent sources：{recommended_clause}，共 {count} 条 edition 对比（WEB-DL / BluRay / REMUX）。",
    },
    "movie.hero_title": {
        "en": "{title} ({year}) — Release-Matched Sources",
        "zh": "{title} ({year}) — Release-Matched Sources",
    },
    "movie.hero_lead": {
        "en": "Compare edition torrent sources — Recommended picks quality over link count.",
        "zh": "对比各 edition torrent sources：Recommended 重画质，而非链接数量。",
    },
    "movie.versions_heading": {
        "en": "All Versions ({count} matched)",
        "zh": "All Versions（{count} matched）",
    },
    "movie.versions_sub": {
        "en": "Grouped by WEB-DL / REMUX / BluRay · compare quality and audio",
        "zh": "按 WEB-DL / REMUX / BluRay 等版本分组 · 对比画质与音轨",
    },
    "movie.about": {"en": "About This Movie", "zh": "About This Movie"},
    "movie.poster_alt": {"en": "{title} poster", "zh": "{title} 海报"},
    # ── Hub ──
    "hub.title": {
        "en": "{show} — Episode Release Guide | ReleaseMatch",
        "zh": "{show} — 全部集数 Release 导航 | ReleaseMatch",
    },
    "hub.meta_description": {
        "en": "{show} episode release navigation: per-episode Recommended Release and multi-source comparison.",
        "zh": "{show} 剧集 Release 导航：分集 Recommended Release 与多源对比。",
    },
    "hub.season": {"en": "Season {season}", "zh": "第 {season} 季"},
    "hub.episode_chip": {"en": "Ep {episode}", "zh": "第 {episode} 集"},
    "hub.episode_aria": {
        "en": "{show} season {season} episode {episode}",
        "zh": "{show} 第 {season} 季第 {episode} 集",
    },
    "hub.episode_title": {
        "en": "Season {season} · Episode {episode}",
        "zh": "第 {season} 季 · 第 {episode} 集",
    },
    # ── 首页 ──
    "home.badge": {
        "en": "Release guide · No video hosting",
        "zh": "Release 导航站 · 非下载托管",
    },
    "home.hero_title": {
        "en": "Pick the right release, not just a magnet",
        "zh": "选对 Release，而不只是找到 Magnet",
    },
    "home.hero_subtitle": {
        "en": "We aggregate multi-source torrent metadata per slot with <strong>Recommended Release</strong>, edition notes, group tiers, and speed summaries.",
        "zh": "我们为每一槽位聚合多源 torrent 元数据，给出 <strong>Recommended Release</strong>、对版说明、Group 信誉与测速摘要。",
    },
    "home.cta_catalog": {
        "en": "Browse catalog ({count})",
        "zh": "浏览全部作品（{count}）",
    },
    "home.cta_how": {
        "en": "How matching works",
        "zh": "了解对版如何工作",
    },
    "home.features_heading": {"en": "Core features", "zh": "核心能力"},
    "home.feature_rec_title": {"en": "Recommended Release", "zh": "Recommended Release"},
    "home.feature_rec_text": {
        "en": "Group tier, cross-source signals, and seeders combined into a ranked pick with indexed reasons.",
        "zh": "综合 Group 信誉、跨源验证与做种情况，推荐最优 release 并给出可索引的推荐理由。",
    },
    "home.feature_cross_title": {"en": "Multi-source coverage", "zh": "多源检索覆盖"},
    "home.feature_cross_text": {
        "en": "Query EZTV, YTS, Nyaa, Jackett indexers; Hero shows how many families returned results. Per-row badges mark true cross-verification when the same release aligns.",
        "zh": "检索 EZTV、YTS、Nyaa、Jackett 等源；Hero 展示多少源族有结果。Sources 表仅在同一 release 对齐时显示交叉验证标记。",
    },
    "home.feature_speed_title": {"en": "Speed & reachability", "zh": "测速与可用性"},
    "home.feature_speed_text": {
        "en": "Connectivity tests and daily seeders; summaries baked into pages.",
        "zh": "连接性测试与 seeders 日更，将实测摘要嵌入页面。",
    },
    "home.scarcity_heading": {"en": "Scarcity tracking", "zh": "稀缺追踪"},
    "home.scarcity_count": {
        "en": "{count} titles still probing",
        "zh": "{count} 部作品持续探测中",
    },
    "home.scarcity_intro": {
        "en": "Slots with fewer than 2 public releases; we keep retrying and publish Recommended when found.",
        "zh": "以下槽位在公开源暂不足 2 条 release，本站仍持续 retry；命中后将自动上架 Recommended。",
    },
    "home.scarcity.region_gap": {"en": "Region gap", "zh": "区域缺口"},
    "home.scarcity.public": {"en": "Public scarcity", "zh": "公开源稀缺"},
    "home.catalog_heading": {"en": "Full catalog", "zh": "全部作品"},
    "home.catalog_stats": {
        "en": "{movies} movies · {tv} TV · {total} entries",
        "zh": "{movies} 电影 · {tv} 剧集 · {total} 入口",
    },
    "home.search_label": {"en": "Search titles", "zh": "搜索作品"},
    "home.search_placeholder": {
        "en": "Search titles, e.g. Breaking Bad…",
        "zh": "搜索作品，如 Breaking Bad…",
    },
    "home.search_empty": {
        "en": "No matches. Try another keyword.",
        "zh": "无匹配作品，请换个关键词。",
    },
    "home.catalog_empty": {
        "en": "No published pages yet; run pipeline and generate all.",
        "zh": "暂无 published 页面；请先运行 pipeline 扩槽与 generate all。",
    },
    # ── 通用 / JS toast ──
    "common.magnet": {"en": "Magnet", "zh": "Magnet"},
    "toast.no_magnet": {"en": "No magnet link to copy", "zh": "无 Magnet 链接可复制"},
    "toast.copied": {"en": "Magnet copied to clipboard", "zh": "Magnet 已复制到剪贴板"},
    "toast.copy_failed": {
        "en": "Copy failed; copy the magnet link manually",
        "zh": "复制失败，请手动复制 Magnet 链接",
    },
    # ── 测速 / Grab 指数（模板静态 + 动态文案键）──
    "speed.panel.summary": {
        "en": "Show speed evidence: avg {avg} · {reach}",
        "zh": "展开测速证据：均速 {avg} · {reach}",
    },
    "speed.panel.title": {
        "en": "Recommended Release — measured evidence",
        "zh": "Recommended Release 实测背书",
    },
    "speed.panel.ig_aria": {
        "en": "Information Gain fields",
        "zh": "Information Gain 字段",
    },
    "speed.freshness.label": {"en": "Data freshness", "zh": "数据时效"},
    "speed.freshness.validity": {"en": "Confidence {level}", "zh": "可信度 {level}"},
    "speed.freshness.tested_at": {"en": "Tested at {time}", "zh": "测速于 {time}"},
    "speed.freshness.no_time": {"en": "No speed test timestamp", "zh": "尚无测速时间记录"},
    "speed.freshness.ttl": {"en": "Refresh interval {hours}h", "zh": "刷新周期 {hours} 小时"},
    "speed.freshness.status.fresh": {"en": "Fresh", "zh": "新鲜"},
    "speed.freshness.status.valid": {"en": "Valid", "zh": "有效"},
    "speed.freshness.status.stale": {"en": "Stale", "zh": "陈旧"},
    "speed.freshness.status.aged": {"en": "Older", "zh": "较久"},
    "speed.freshness.status.expired": {"en": "Older", "zh": "较久"},
    "speed.freshness.status.unknown": {"en": "Not tested", "zh": "未测速"},
    "speed.validity.high": {"en": "High", "zh": "高"},
    "speed.validity.medium": {"en": "Medium", "zh": "中"},
    "speed.validity.low": {"en": "Low", "zh": "低"},
    "speed.validity.uncertain": {"en": "Uncertain", "zh": "待确认"},
    "speed.validity.invalid": {"en": "Invalid", "zh": "无效"},
    "speed.validity.unknown": {"en": "Unknown", "zh": "未知"},
    "speed.freshness.note.unknown": {
        "en": "No libtorrent measurement yet; speeds below are not valid IG evidence.",
        "zh": "尚无 libtorrent 实测记录，以下速度不可作为 IG 背书。",
    },
    "speed.freshness.note.fresh": {
        "en": "{age}, within 24h; suitable for Recommended measured evidence (S-07).",
        "zh": "距测速 {age}（≤24h）；数据可直接用于 Recommended 实测背书（S-07）。",
    },
    "speed.freshness.note.valid": {
        "en": "{age}, within 48h but past 24h; still referenceable — re-test when convenient.",
        "zh": "距测速 {age}（24–48h）；仍可参考，建议在方便时安排复测。",
    },
    "speed.freshness.note.stale": {
        "en": "{age}, within 72h but past 48h; peers/speed may have changed — re-test preferred.",
        "zh": "距测速 {age}（48–72h）；peer/速度可能已变化，IG 背书效力降低，应优先复测。",
    },
    "speed.freshness.note.aged": {
        "en": "{age}, older than 72h; swarm may have shifted — re-test before relying on it (not marked expired).",
        "zh": "距测速 {age}（>72h）；swarm 状态可能已有变化，建议复测后再作主要依据（非断言已失效）。",
    },
    "speed.freshness.note.expired": {
        "en": "{age}, older than 72h; swarm may have shifted — re-test before relying on it (not marked expired).",
        "zh": "距测速 {age}（>72h）；swarm 状态可能已有变化，建议复测后再作主要依据（非断言已失效）。",
    },
    "speed.age.minutes_ago": {"en": "{minutes} min ago", "zh": "{minutes} 分钟前"},
    "speed.age.hours_ago": {"en": "{hours} hours ago", "zh": "{hours} 小时前"},
    "speed.age.days_ago": {"en": "{days} days ago", "zh": "{days} 天前"},
    "speed.reach.label": {"en": "Peer reachability", "zh": "Peer 可达性"},
    "speed.reach.level.high": {"en": "High", "zh": "高"},
    "speed.reach.level.medium": {"en": "Medium", "zh": "中"},
    "speed.reach.level.low": {"en": "Low", "zh": "低"},
    "speed.reach.level.unreachable": {"en": "Unreachable", "zh": "不可达"},
    "speed.reach.display.timeout": {
        "en": "{level} ({status}, 0 peers available)",
        "zh": "{level}（{status}，0 peers 可用）",
    },
    "speed.reach.display.zero_peers": {
        "en": "{level} (0 peers observed)",
        "zh": "{level}（观测 0 peers）",
    },
    "speed.reach.display.full": {
        "en": "{level} · {total} peers observed · {reachable} connected · connect rate {rate}",
        "zh": "{level} · 观测 {total} peers · 已连 {reachable} · 连接率 {rate}",
    },
    "speed.reach.detail.timeout": {
        "en": "Speedtest status {status}; Phase 1/2 did not establish valid peer connections.",
        "zh": "测速状态 {status}；Phase 1/2 未获得有效 peer 连接。",
    },
    "speed.reach.detail.zero_peers": {
        "en": "libtorrent observed no usable peers; level derived as unreachable.",
        "zh": "libtorrent 未观测到可用 peer；等级派生为不可达。",
    },
    "speed.reach.detail.full": {
        "en": "A-01 from peers_total: {threshold}; A-02 peers_reachable={reachable} / peers_total={total}.",
        "zh": "A-01 由 peers_total 派生：{threshold}；A-02 peers_reachable={reachable} / peers_total={total}。",
    },
    "speed.reach.rule": {
        "en": "Rule: ≥10 High · 3–9 Medium · 1–2 Low · 0/error Unreachable",
        "zh": "规则：≥10 高 · 3–9 中 · 1–2 低 · 0/error 不可达",
    },
    "speed.reach.threshold.error": {
        "en": "timeout/error → Unreachable",
        "zh": "timeout/error → 不可达",
    },
    "speed.reach.threshold.high": {"en": "≥10 → High; observed {count}", "zh": "≥10 → 高；本次 {count}"},
    "speed.reach.threshold.medium": {"en": "3–9 → Medium; observed {count}", "zh": "3–9 → 中；本次 {count}"},
    "speed.reach.threshold.low": {"en": "1–2 → Low; observed {count}", "zh": "1–2 → 低；本次 {count}"},
    "speed.reach.threshold.zero": {"en": "0 peers → Unreachable", "zh": "0 peers → 不可达"},
    "speed.pair.display": {"en": "Avg {avg} · Peak {max}", "zh": "均速 {avg} · 峰值 {max}"},
    "speed.pair.spread": {"en": "Peak/avg ×{ratio}", "zh": "峰值/均速 ×{ratio}"},
    "speed.peers.connect_rate": {
        "en": "{pct} ({reachable}/{total})",
        "zh": "{pct}（{reachable}/{total}）",
    },
    "speed.metric.tested_at": {"en": "Test time", "zh": "测速时间"},
    "speed.metric.avg": {"en": "Avg speed", "zh": "均速 avg"},
    "speed.metric.max": {"en": "Peak speed", "zh": "峰值 max"},
    "speed.metric.peers_total": {"en": "Peers observed", "zh": "观测 peers total"},
    "speed.metric.peers_connected": {"en": "Peers connected", "zh": "已连 peers"},
    "speed.metric.connect_rate": {"en": "Connect rate", "zh": "连接率"},
    "speed.metric.latency": {"en": "First-byte latency", "zh": "首包延迟"},
    "speed.metric.summary_updated": {"en": "Summary stored", "zh": "摘要入库"},
    "speed.metric.validity": {"en": "Validity {level}", "zh": "效力 {level}"},
    "speed.facts.aria": {"en": "Measured download metrics", "zh": "实测下载指标"},
    "speed.facts.avg": {"en": "Segment avg", "zh": "片段均速"},
    "speed.facts.max": {"en": "Segment peak", "zh": "片段峰值"},
    "speed.facts.peers_observed": {"en": "Peers observed", "zh": "观测 peers"},
    "speed.facts.peers_connected": {"en": "Peers connected", "zh": "已连 peers"},
    "speed.facts.peers_sample": {
        "en": "libtorrent point-in-time sample",
        "zh": "libtorrent 时点采样",
    },
    "speed.facts.peers_handshake": {
        "en": "Successful handshake count",
        "zh": "成功握手 peer 数",
    },
    "speed.compare.label": {"en": "Index vs measured:", "zh": "索引 vs 实测："},
    "speed.footnote": {
        "en": "Data from libtorrent DHT/tracker point-in-time sampling; <strong>avg, peak, peers and connect rate are from the same {method} run</strong>, and may differ from Jackett indexed seeders.",
        "zh": "数据来自 libtorrent DHT/tracker 时点采样；<strong>均速、峰值、peers 与连接率均为同一次 {method} 结果</strong>，与 Jackett 索引 seeders 可能偏差。",
    },
    "speed.method_note": {
        "en": "libtorrent segment download ({target}, strategy A2)",
        "zh": "libtorrent 片段下载（{target}，策略 A2）",
    },
    "speed.index_vs.no_index": {
        "en": "Indexed seeders not recorded; libtorrent measured {peers} peers (A-02).",
        "zh": "索引 seeders 未记录；libtorrent 实测 {peers} peers（A-02）。",
    },
    "speed.index_vs.compare": {
        "en": "Indexed seeders {indexed} (B-02 ref) vs libtorrent measured {peers} peers (A-02) — measured takes precedence.",
        "zh": "索引 seeders {indexed}（B-02 参考） vs libtorrent 实测 {peers} peers（A-02）— 以实测为准。",
    },
    "speed.latency.ms": {"en": "{ms} ms", "zh": "{ms} ms"},
    "speed.grab.name": {"en": "RM Grab Index", "zh": "RM Grab 指数"},
    "speed.grab.tagline": {
        "en": "ReleaseMatch measured composite score",
        "zh": "ReleaseMatch 实测综合分",
    },
    "speed.grab.pending": {"en": "Awaiting test", "zh": "待测速"},
    "speed.grab.score_aria": {"en": "Overall score", "zh": "综合分"},
    "speed.grab.breakdown_aria": {"en": "Breakdown scores", "zh": "分项得分"},
    "speed.grab.tier.excellent": {"en": "Excellent", "zh": "极佳"},
    "speed.grab.tier.great": {"en": "Great", "zh": "优秀"},
    "speed.grab.tier.good": {"en": "Good", "zh": "良好"},
    "speed.grab.tier.fair": {"en": "Fair", "zh": "一般"},
    "speed.grab.tier.weak": {"en": "Weak", "zh": "偏弱"},
    "speed.grab.tier.poor": {"en": "Poor", "zh": "较差"},
    "speed.grab.dim.speed": {"en": "Speed", "zh": "速度"},
    "speed.grab.dim.reachability": {"en": "Reachability", "zh": "可达性"},
    "speed.grab.dim.connect": {"en": "Connect rate", "zh": "连接率"},
    "speed.grab.dim.freshness": {"en": "Freshness", "zh": "时效"},
    "speed.grab.summary.empty": {
        "en": "Not enough measured data yet",
        "zh": "尚无足够实测数据",
    },
    "speed.grab.summary.speed_ok": {"en": "Speed OK", "zh": "速度尚可"},
    "speed.grab.summary.speed_low": {"en": "Speed low", "zh": "速度偏低"},
    "speed.grab.summary.reach_level": {"en": "Reachability {level}", "zh": "可达性{level}"},
    "speed.grab.summary.reach_fair": {"en": "Reachability fair", "zh": "可达性一般"},
    "speed.grab.summary.connect_pct": {"en": "Connect rate {pct}%", "zh": "连接率 {pct}%"},
    "speed.grab.summary.connect_low": {"en": "Connect rate low", "zh": "连接率偏低"},
    "speed.grab.summary.data_fresh": {"en": "Data fresh", "zh": "数据新鲜"},
    "speed.grab.summary.data_valid": {"en": "Data valid", "zh": "数据有效"},
    "speed.grab.summary.data_stale": {"en": "Data stale", "zh": "数据陈旧"},
    "speed.grab.summary.data_aged": {"en": "Older data", "zh": "数据较久"},
    "speed.endorsement.title_named": {"en": "\"{title}\"", "zh": "「{title}」"},
    "speed.endorsement.title_default": {
        "en": "this site's Recommended release",
        "zh": "本站 Recommended release",
    },
    "speed.endorsement.time": {
        "en": " Tested at {tested} ({age}, validity {validity}·{freshness}).",
        "zh": "测速于 {tested}（{age}，有效性 {validity}·{freshness}）。",
    },
    "speed.endorsement.body": {
        "en": "Data bound to {title} (infohash …{hash}), libtorrent segment test {speed}, peer reachability {reach}.{time}",
        "zh": "以下数据绑定 {title}（infohash …{hash}），libtorrent 片段实测 {speed}，Peer 可达性 {reach}。{time}",
    },
    "movie.edition_pick": {"en": "Best in group:", "zh": "本组推荐："},
    # ── Trust 五页 ──
    "trust.about.title": {"en": "About — ReleaseMatch", "zh": "关于 — ReleaseMatch"},
    "trust.about.meta": {
        "en": "ReleaseMatch is an independent Release navigation site. We index public torrent metadata only—no video hosting—and provide Recommended Release matching.",
        "zh": "ReleaseMatch 是独立 Release 导航站，仅索引公开 torrent 元数据，不托管视频，提供 Recommended Release 对版推荐。",
    },
    "trust.about.heading": {"en": "About ReleaseMatch", "zh": "关于 ReleaseMatch"},
    "trust.how.title": {"en": "How Release Matching Works — ReleaseMatch", "zh": "对版如何工作 — ReleaseMatch"},
    "trust.how.meta": {
        "en": "How ReleaseMatch verifies release matching, scores Recommended Release, and produces Information Gain beyond magnet lists.",
        "zh": "ReleaseMatch 如何验证对版、评分 Recommended Release，并在 magnet 列表之外提供 Information Gain。",
    },
    "trust.how.heading": {"en": "How Release Matching Works", "zh": "对版如何工作"},
    "trust.contact.title": {"en": "Contact — ReleaseMatch", "zh": "联系 — ReleaseMatch"},
    "trust.contact.meta": {
        "en": "Contact ReleaseMatch for general inquiries, DMCA notices, and privacy questions. Functional email: ReleaseMatch@hotmail.com.",
        "zh": "联系 ReleaseMatch：一般咨询、DMCA 与隐私问题。邮箱：ReleaseMatch@hotmail.com。",
    },
    "trust.contact.heading": {"en": "Contact", "zh": "联系我们"},
    "trust.privacy.title": {"en": "Privacy Policy — ReleaseMatch", "zh": "隐私政策 — ReleaseMatch"},
    "trust.privacy.meta": {
        "en": "ReleaseMatch privacy policy: web logs, optional speed-test extension data, no video storage, Cloudflare hosting.",
        "zh": "ReleaseMatch 隐私政策：Web 日志、可选测速扩展数据、不存视频、Cloudflare 托管。",
    },
    "trust.privacy.heading": {"en": "Privacy Policy", "zh": "隐私政策"},
    "trust.dmca.title": {"en": "DMCA — ReleaseMatch", "zh": "DMCA — ReleaseMatch"},
    "trust.dmca.meta": {
        "en": "DMCA and copyright notice policy for ReleaseMatch. We index metadata only; valid notices are processed with 410 Gone removal.",
        "zh": "ReleaseMatch DMCA 与版权通知政策；仅索引元数据，有效通知将 410 Gone 处理。",
    },
    "trust.dmca.heading": {"en": "DMCA / Copyright Notice", "zh": "DMCA / 版权通知"},
    "trust.speed_grab.title": {
        "en": "Speed Test & RM Grab Index — ReleaseMatch",
        "zh": "测速可信度与 RM Grab 指数 — ReleaseMatch",
    },
    "trust.speed_grab.meta": {
        "en": "How ReleaseMatch calculates RM Grab Index, speed credibility, peer reachability, and libtorrent segment test metrics.",
        "zh": "ReleaseMatch 如何计算 RM Grab 指数、测速可信度、Peer 可达性与 libtorrent 片段测速指标。",
    },
    "trust.speed_grab.heading": {
        "en": "Speed Test Credibility & RM Grab Index",
        "zh": "测速可信度与 RM Grab 指数",
    },
    # ── 指标说明页链接（内容页各区域） ──
    "metrics.explainer.page_title": {
        "en": "How scores are calculated",
        "zh": "分数如何计算",
    },
    "metrics.explainer.grab": {
        "en": "How Grab Index is calculated",
        "zh": "Grab 指数说明",
    },
    "metrics.explainer.freshness": {
        "en": "Speed credibility explained",
        "zh": "测速可信度说明",
    },
    "metrics.explainer.speed": {
        "en": "Speed test metrics",
        "zh": "测速指标说明",
    },
    "metrics.explainer.reachability": {
        "en": "Reachability rules",
        "zh": "可达性规则",
    },
    "footer.speed_grab": {
        "en": "Speed & Grab scores",
        "zh": "测速与 Grab 说明",
    },
}


def normalize_locale(raw: Optional[str]) -> str:
    """
    将配置或用户 locale 归一化为 en | zh。

    @param raw: 如 en、zh、zh-CN
    @returns: en 或 zh
    """
    token = (raw or "en").strip().lower().replace("_", "-")
    if token.startswith("zh"):
        return "zh"
    return "en"


def html_lang_attr(locale: str) -> str:
    """
    返回 HTML ``lang`` 属性值。

    @param locale: en | zh
    @returns: en 或 zh-CN
    """
    return "zh-CN" if normalize_locale(locale) == "zh" else "en"


def translate(key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
    """
    按 key 与 locale 返回 UI 文案。

    @param key: MESSAGES 键
    @param locale: en | zh；None 时使用站点默认
    @param kwargs: format 占位符
    @returns: 翻译字符串；缺 key 时回退 key 本身
    """
    loc = normalize_locale(locale)
    if loc not in SUPPORTED_LOCALES:
        loc = "en"
    bucket = MESSAGES.get(key, {})
    text = bucket.get(loc) or bucket.get("en") or key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def _seo_recommended_clause(
    locale: str,
    *,
    resolution: str = "",
    source: str = "",
    group: str = "",
) -> str:
    """
    组装 meta description 中 Recommended 后的画质/版本/组短语。

    @param locale: en | zh
    @param resolution: 如 1080p
    @param source: 如 WEB-DL / BluRay
    @param group: release group 名
    @returns: 如 ``Recommended 1080p WEB-DL (NTb)``；无字段时回退 ``Recommended Release``
    """
    loc = normalize_locale(locale)
    res = (resolution or "").strip()
    src = (source or "").strip()
    grp = (group or "").strip()
    parts = [p for p in (res, src) if p]
    core = " ".join(parts)
    if grp:
        detail = f"{core} ({grp})" if core else grp
    else:
        detail = core
    if loc == "zh":
        return f"Recommended {detail}" if detail else "Recommended Release"
    return f"Recommended {detail}" if detail else "Recommended Release"


def _clamp_meta_description(text: str, max_len: int = 160) -> str:
    """
    将 meta description 控制在约 160 字符内，避免 SERP 截断难看。

    @param text: 原始描述
    @param max_len: 最大长度（字符）
    @returns: 截断后的描述
    """
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[: max_len - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: max_len - 1]).rstrip(".,;:") + "…"


def build_episode_meta_description(
    locale: str,
    *,
    show: str,
    season: int,
    episode: int,
    count: int,
    resolution: str = "",
    source: str = "",
    group: str = "",
) -> str:
    """
    剧集页 SEO meta description（v1.1 方案：torrent + 动态画质/版本/组）。

    @param locale: en | zh
    @param show: 剧名
    @param season: 季号
    @param episode: 集号
    @param count: sources 条数
    @param resolution: Recommended 分辨率
    @param source: Recommended 版本源（WEB-DL 等）
    @param group: Recommended release group
    @returns: 适合 ``<meta name="description">`` 的英文/中文描述
    """
    clause = _seo_recommended_clause(
        locale, resolution=resolution, source=source, group=group
    )
    text = translate(
        "episode.meta_description",
        locale,
        show=show,
        season=int(season or 0),
        episode=int(episode or 0),
        recommended_clause=clause,
        count=int(count or 0),
    )
    return _clamp_meta_description(text)


def build_movie_meta_description(
    locale: str,
    *,
    title: str,
    year: Any,
    count: int,
    resolution: str = "",
    source: str = "",
    group: str = "",
) -> str:
    """
    电影页 SEO meta description（v1.1：torrent + edition 三型 + 动态 Recommended）。

    @param locale: en | zh
    @param title: 片名
    @param year: 上映年
    @param count: versions 条数
    @param resolution: Recommended 分辨率
    @param source: Recommended 版本源
    @param group: Recommended release group（电影一般可空）
    @returns: meta description 字符串
    """
    clause = _seo_recommended_clause(
        locale, resolution=resolution, source=source, group=group
    )
    text = translate(
        "movie.meta_description",
        locale,
        title=title,
        year=year if year not in (None, "") else "—",
        recommended_clause=clause,
        count=int(count or 0),
    )
    return _clamp_meta_description(text)


def attach_seo_meta_description(context: Dict[str, Any], locale: str) -> None:
    """
    按页面类型向模板上下文写入 ``seo_meta_description``（就地修改）。

    剧集：有 show_title + season + episode，且无 hub 的 seasons 列表。
    电影：有 movie_title。

    @param context: Jinja 上下文
    @param locale: 当前渲染语言
    """
    rec = context.get("recommended")
    if isinstance(rec, dict):
        resolution = str(
            context.get("recommended_quality") or rec.get("resolution") or ""
        )
        source = str(context.get("recommended_source") or rec.get("source") or "")
        group = str(
            context.get("recommended_group") or rec.get("release_group") or ""
        )
    else:
        resolution = str(context.get("recommended_quality") or "")
        source = str(context.get("recommended_source") or "")
        group = str(context.get("recommended_group") or "")

    if context.get("movie_title") is not None and "year" in context:
        context["seo_meta_description"] = build_movie_meta_description(
            locale,
            title=str(context.get("movie_title") or ""),
            year=context.get("year") or "",
            count=int(context.get("source_count") or 0),
            resolution=resolution,
            source=source,
            group=group,
        )
        return

    if (
        context.get("show_title") is not None
        and context.get("season") is not None
        and context.get("episode") is not None
        and "seasons" not in context
    ):
        context["seo_meta_description"] = build_episode_meta_description(
            locale,
            show=str(context.get("show_title") or ""),
            season=int(context.get("season") or 0),
            episode=int(context.get("episode") or 0),
            count=int(context.get("source_count") or 0),
            resolution=resolution,
            source=source,
            group=group,
        )


def catalog_for_js() -> Dict[str, Dict[str, str]]:
    """
    导出前端语言切换用的完整 catalog。

    @returns: {"en": {key: text}, "zh": {key: text}}
    """
    out: Dict[str, Dict[str, str]] = {"en": {}, "zh": {}}
    for key, bucket in MESSAGES.items():
        out["en"][key] = bucket.get("en", key)
        out["zh"][key] = bucket.get("zh", bucket.get("en", key))
    return out


class I18nRuntime:
    """
    单次渲染会话的 i18n 上下文。

    @var enabled: 是否启用前端 en/zh 切换
    @var locale: 服务端渲染默认语言
    """

    def __init__(self, *, enabled: bool, locale: str) -> None:
        self.enabled = bool(enabled)
        self.locale = normalize_locale(locale)

    @property
    def html_lang(self) -> str:
        """HTML lang 属性。"""
        return html_lang_attr(self.locale)

    def t(self, key: str, **kwargs: Any) -> str:
        """
        模板 callable：``{{ t('nav.home') }}``。

        @param key: MESSAGES 键
        @param kwargs: format 参数
        @returns: 当前 locale 文案
        """
        return translate(key, self.locale, **kwargs)

    def merge_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        向 Jinja 上下文中注入 i18n 变量。

        @param context: 原有模板 dict
        @returns: 合并后的 dict（含 t、html_lang、i18n_catalog 等）
        """
        from portal.generator.i18n_speed import localize_page_variables

        merged = dict(context)
        merged["t"] = self.t
        merged["i18n_enabled"] = self.enabled
        merged["site_locale"] = self.locale
        merged["html_lang"] = self.html_lang
        if self.enabled:
            merged["i18n_catalog"] = catalog_for_js()
            from portal.generator.i18n_dynamic import build_i18n_dynamic

            preset = dict(merged.get("i18n_dynamic") or {})
            dynamic = build_i18n_dynamic(merged)
            dynamic.update(preset)
            merged["i18n_dynamic"] = dynamic
        localize_page_variables(merged, self.locale)
        attach_seo_meta_description(merged, self.locale)
        from portal.generator.link_attrs import outbound_link_context

        merged.update(outbound_link_context())
        return merged


def build_i18n_runtime() -> I18nRuntime:
    """
    从 ``workflow.config`` 读取开关与默认语言。

    @returns: I18nRuntime 实例
    """
    from workflow.config import SITE_I18N_ENABLED, SITE_LOCALE

    return I18nRuntime(enabled=SITE_I18N_ENABLED, locale=SITE_LOCALE)


def static_asset_version() -> str:
    """
    根据 design-system.css 与 site.js 内容生成短 hash，用作静态资源缓存破坏参数。

    @returns: 10 位十六进制版本串；读文件失败时回退为固定占位
    """
    import hashlib
    from pathlib import Path

    static_root = Path(__file__).resolve().parents[1] / "static"
    # 完整注释：CSS/JS 任一变更都需换 ?v=，避免海报懒加载等脚本被 CDN/浏览器旧缓存
    asset_paths = (
        static_root / "css" / "design-system.css",
        static_root / "js" / "site.js",
    )
    digest = hashlib.md5()
    read_any = False
    for path in asset_paths:
        try:
            digest.update(path.read_bytes())
            read_any = True
        except OSError:
            continue
    if not read_any:
        return "dev"
    return digest.hexdigest()[:10]


def merge_render_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    渲染前统一注入 i18n 与静态资源版本（供 render.py / 首页等调用）。

    @param context: 模板变量 dict
    @returns: 注入 i18n 后的 dict
    """
    merged = build_i18n_runtime().merge_context(context)
    # 完整注释：页面 CSS/JS 链接依赖此版本号，避免旧样式（如 ellipsis）被缓存
    merged["static_asset_version"] = static_asset_version()
    return merged
