#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测速 / Grab 指数 UI 文案本地化（渲染期）。

@module portal.generator.i18n_speed
@description
  ``SpeedEvidenceContext.to_template_dict()`` 默认产出中文展示字段；
  英文站点在 ``merge_render_context`` 中调用本模块，按 ``RM_SITE_LOCALE`` 重写
  speed_evidence、recommended.grab_index、speed_endorsement 等动态字符串。
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from portal.generator.i18n import normalize_locale, translate

# 可达性等级（MySQL / 派生逻辑存中文 canonical）
_REACH_CANONICAL: Dict[str, str] = {
    "高": "high",
    "中": "medium",
    "低": "low",
    "不可达": "unreachable",
}

# freshness_class → validity 文案键
_FRESHNESS_VALIDITY_KEY: Dict[str, str] = {
    "fresh": "high",
    "valid": "medium",
    "stale": "low",
    "expired": "invalid",
    "unknown": "unknown",
}


def _reach_label(reachability: str, locale: str) -> str:
    """
    将可达性 canonical（中文或英文键）转为当前 locale 展示文案。

    @param reachability: 高/中/低/不可达 或 —
    @param locale: en | zh
    @returns: 本地化等级词
    """
    if not reachability or reachability == "—":
        return "—"
    key = _REACH_CANONICAL.get(reachability, reachability.lower())
    bucket = {
        "high": "speed.reach.level.high",
        "medium": "speed.reach.level.medium",
        "low": "speed.reach.level.low",
        "unreachable": "speed.reach.level.unreachable",
    }
    msg_key = bucket.get(key, "speed.reach.level.unreachable")
    return translate(msg_key, locale)


def _format_age_display(age_hours: Optional[float], locale: str) -> str:
    """
    相对测速时间（与 d1_models._format_age_display 对齐，支持 en）。

    @param age_hours: 距测速小时数
    @param locale: en | zh
    @returns: 如「2.5 hours ago」
    """
    if age_hours is None:
        return "—"
    hours = max(0.0, float(age_hours))
    if hours < 1.0:
        minutes = max(1, int(round(hours * 60)))
        return translate("speed.age.minutes_ago", locale, minutes=minutes)
    if hours < 48:
        return translate("speed.age.hours_ago", locale, hours=f"{hours:.1f}".rstrip("0").rstrip("."))
    days = hours / 24.0
    return translate("speed.age.days_ago", locale, days=f"{days:.1f}".rstrip("0").rstrip("."))


def _format_speed_human(avg_kbps: float) -> str:
    """
    格式化 KiB/s 为 MB/s 或 KB/s（与 reachability.format_recommended_speed 一致）。

    @param avg_kbps: KiB/s
    @returns: 如「4.2 MB/s」
    """
    if avg_kbps <= 0:
        return ""
    mb_per_sec = avg_kbps / 1024.0
    if mb_per_sec >= 1.0:
        return f"{mb_per_sec:.1f} MB/s"
    return f"{int(round(avg_kbps))} KB/s"


def _localize_freshness(se: Dict[str, Any], locale: str) -> None:
    """
    就地重写 freshness_label、validity_level、age_display、freshness_note。

    @param se: speed_evidence 字典
    @param locale: en | zh
    @returns: None
    """
    fc = str(se.get("freshness_class") or "unknown")
    ttl = int(se.get("ttl_hours") or 6)
    age_hours = se.get("age_hours")
    age_display = _format_age_display(age_hours, locale) if age_hours is not None else se.get("age_display", "—")

    label_key = f"speed.freshness.status.{fc}"
    validity_key = f"speed.validity.{_FRESHNESS_VALIDITY_KEY.get(fc, 'unknown')}"
    note_key = f"speed.freshness.note.{fc}"

    se["freshness_label"] = translate(label_key, locale)
    se["validity_level"] = translate(validity_key, locale)
    se["age_display"] = age_display
    if fc == "unknown":
        se["freshness_note"] = translate(note_key, locale)
    else:
        se["freshness_note"] = translate(note_key, locale, age=age_display, ttl=ttl)


def _localize_speed_pair(se: Dict[str, Any], locale: str) -> None:
    """
    重写均速/峰值展示与 speed_pair_display、speed_spread_display。

    @param se: speed_evidence 字典
    @param locale: en | zh
    @returns: None
    """
    avg_kbps = float(se.get("avg_kbps") or 0)
    max_kbps = float(se.get("max_kbps") or 0)
    avg_text = _format_speed_human(avg_kbps)
    max_text = _format_speed_human(max_kbps)
    se["avg_speed"] = avg_text
    se["max_speed"] = max_text
    if avg_kbps > 0 or max_kbps > 0:
        se["speed_pair_display"] = translate(
            "speed.pair.display",
            locale,
            avg=avg_text or "—",
            max=max_text or "—",
        )
    spread = ""
    if avg_kbps > 0 and max_kbps > 0:
        ratio = max_kbps / avg_kbps
        spread = translate("speed.pair.spread", locale, ratio=f"{ratio:.1f}")
    se["speed_spread_display"] = spread


def _localize_peers(se: Dict[str, Any], locale: str) -> None:
    """
    重写 peers 与连接率展示字段。

    @param se: speed_evidence 字典
    @param locale: en | zh
    @returns: None
    """
    peers_total = int(se.get("peers_total") or 0)
    peers_reachable = int(se.get("peers_reachable") or 0)
    if peers_total > 0 and peers_reachable >= 0:
        rate_pct = int(round(peers_reachable * 100.0 / peers_total))
        connect_rate_pct = f"{rate_pct}%"
        se["connect_rate_pct"] = connect_rate_pct
        se["peers_pair_display"] = f"{peers_reachable} / {peers_total}"
        se["connect_rate_display"] = translate(
            "speed.peers.connect_rate",
            locale,
            pct=connect_rate_pct,
            reachable=peers_reachable,
            total=peers_total,
        )
    se["peers_total_display"] = str(peers_total) if peers_total >= 0 else "—"
    se["peers_reachable_display"] = str(peers_reachable) if peers_reachable >= 0 else "—"


def _localize_reachability(se: Dict[str, Any], locale: str) -> None:
    """
    重写 reachability_display、reachability_detail、reachability_rule。

    @param se: speed_evidence 字典
    @param locale: en | zh
    @returns: None
    """
    reach_raw = str(se.get("reachability") or "—")
    reach_label = _reach_label(reach_raw, locale)
    peers_total = int(se.get("peers_total") or 0)
    peers_reachable = int(se.get("peers_reachable") or 0)
    status = str(se.get("status") or "ok")
    rate_pct = str(se.get("connect_rate_pct") or "—")

    if status in ("timeout", "error"):
        se["reachability_display"] = translate(
            "speed.reach.display.timeout",
            locale,
            level=reach_label,
            status=status,
        )
        se["reachability_detail"] = translate(
            "speed.reach.detail.timeout",
            locale,
            status=status,
        )
    elif peers_total <= 0:
        se["reachability_display"] = translate(
            "speed.reach.display.zero_peers",
            locale,
            level=reach_label,
        )
        se["reachability_detail"] = translate("speed.reach.detail.zero_peers", locale)
    else:
        se["reachability_display"] = translate(
            "speed.reach.display.full",
            locale,
            level=reach_label,
            total=peers_total,
            reachable=peers_reachable,
            rate=rate_pct,
        )
        threshold = translate(
            f"speed.reach.threshold.{_threshold_key(peers_total, status)}",
            locale,
            count=peers_total,
        )
        se["reachability_detail"] = translate(
            "speed.reach.detail.full",
            locale,
            threshold=threshold,
            reachable=peers_reachable,
            total=peers_total,
        )
    se["reachability"] = reach_label
    se["reachability_rule"] = translate("speed.reach.rule", locale)


def _threshold_key(peers_total: int, status: str) -> str:
    """
    可达性阈值说明键后缀。

    @param peers_total: 观测 peer 数
    @param status: 测速状态
    @returns: high | medium | low | zero | error
    """
    if status in ("timeout", "error"):
        return "error"
    if peers_total >= 10:
        return "high"
    if peers_total >= 3:
        return "medium"
    if peers_total >= 1:
        return "low"
    return "zero"


def _localize_grab(se: Dict[str, Any], locale: str) -> None:
    """
    重写 Grab 指数名称、等级、分项与 summary。

    @param se: 含 grab_index_* 字段的字典
    @param locale: en | zh
    @returns: None
    """
    se["grab_index_name"] = translate("speed.grab.name", locale)
    se["grab_index_tagline"] = translate("speed.grab.tagline", locale)

    tier = str(se.get("grab_index_tier") or "poor")
    se["grab_index_tier_label"] = translate(f"speed.grab.tier.{tier}", locale)

    breakdown = se.get("grab_index_breakdown") or []
    dim_keys = {"speed": "speed.grab.dim.speed", "reachability": "speed.grab.dim.reachability",
                "connect": "speed.grab.dim.connect", "freshness": "speed.grab.dim.freshness"}
    for item in breakdown:
        key = str(item.get("key") or "")
        if key in dim_keys:
            item["label"] = translate(dim_keys[key], locale)

    if not se.get("grab_index_has_data"):
        se["grab_index_summary"] = translate("speed.grab.summary.empty", locale)
        return

    parts: List[str] = []
    scores = {str(b.get("key")): int(b.get("score") or 0) for b in breakdown}
    reach_raw = str(se.get("reachability_raw") or se.get("reachability") or "")
    reach_label = _reach_label(reach_raw, locale) if reach_raw else "—"

    speed_pts = scores.get("speed", 0)
    reach_pts = scores.get("reachability", 0)
    connect_pts = scores.get("connect", 0)
    fresh_pts = scores.get("freshness", 0)
    peers_total = int(se.get("peers_total") or 0)

    if speed_pts >= 60:
        parts.append(translate("speed.grab.summary.speed_ok", locale))
    elif speed_pts > 0:
        parts.append(translate("speed.grab.summary.speed_low", locale))
    if reach_pts >= 65:
        parts.append(translate("speed.grab.summary.reach_level", locale, level=reach_label))
    elif reach_pts > 0:
        parts.append(translate("speed.grab.summary.reach_fair", locale))
    if connect_pts >= 50:
        parts.append(translate("speed.grab.summary.connect_pct", locale, pct=connect_pts))
    elif peers_total > 0:
        parts.append(translate("speed.grab.summary.connect_low", locale))
    if fresh_pts >= 78:
        parts.append(translate("speed.grab.summary.data_fresh", locale))
    elif fresh_pts >= 42:
        parts.append(translate("speed.grab.summary.data_valid", locale))
    elif fresh_pts > 0:
        parts.append(translate("speed.grab.summary.data_stale", locale))

    se["grab_index_summary"] = " · ".join(parts) if parts else translate("speed.grab.summary.empty", locale)


def _extract_target_bytes(method_note: str) -> str:
    """
    从 method_note 提取片段大小（如 256 KB）。

    @param method_note: 中文或英文 method_note
    @returns: 大小文案或默认 256 KB
    """
    match = re.search(r"(\d+\s*[KMG]B)", method_note or "", re.IGNORECASE)
    return match.group(1) if match else "256 KB"


def _localize_method_and_compare(se: Dict[str, Any], locale: str) -> None:
    """
    重写 method_note、index_vs_measured。

    @param se: speed_evidence 字典
    @param locale: en | zh
    @returns: None
    """
    target = se.get("target_bytes_label") or _extract_target_bytes(str(se.get("method_note") or ""))
    se["method_note"] = translate("speed.method_note", locale, target=target)

    indexed = int(se.get("indexed_seeders") or 0)
    peers = int(se.get("peers_total") or 0)
    if indexed <= 0 and peers <= 0:
        se["index_vs_measured"] = ""
    elif indexed <= 0:
        se["index_vs_measured"] = translate("speed.index_vs.no_index", locale, peers=peers)
    else:
        se["index_vs_measured"] = translate(
            "speed.index_vs.compare",
            locale,
            indexed=indexed,
            peers=peers,
        )


def _localize_endorsement(se: Dict[str, Any], locale: str, release_title: str = "") -> str:
    """
    生成 S-07 实测背书句（en / zh）。

    @param se: 已局部本地化的 speed_evidence 字典
    @param locale: en | zh
    @param release_title: Recommended release 标题
    @returns: 背书句
    """
    loc = normalize_locale(locale)
    title_part = (
        translate("speed.endorsement.title_named", loc, title=release_title)
        if release_title
        else translate("speed.endorsement.title_default", loc)
    )
    infohash = str(se.get("infohash_short") or "")
    speed_pair = se.get("speed_pair_display") or ""
    reach = se.get("reachability_display") or se.get("reachability") or "—"
    time_part = ""
    if se.get("tested_at_iso"):
        time_part = translate(
            "speed.endorsement.time",
            loc,
            tested=se.get("tested_at") or "",
            age=se.get("age_display") or "—",
            validity=se.get("validity_level") or "—",
            freshness=se.get("freshness_label") or "—",
        )
    return translate(
        "speed.endorsement.body",
        loc,
        title=title_part,
        hash=infohash,
        speed=speed_pair,
        reach=reach,
        time=time_part,
    )


def localize_speed_evidence_dict(se: Dict[str, Any], locale: str) -> Dict[str, Any]:
    """
    深拷贝并本地化 speed_evidence 模板字典。

    @param se: ``SpeedEvidenceContext.to_template_dict()`` 结果
    @param locale: en | zh
    @returns: 本地化后的新字典
    """
    if normalize_locale(locale) == "zh":
        return se
    out = deepcopy(se)
    out["reachability_raw"] = out.get("reachability")
    _localize_freshness(out, locale)
    _localize_speed_pair(out, locale)
    _localize_peers(out, locale)
    _localize_reachability(out, locale)
    _localize_grab(out, locale)
    _localize_method_and_compare(out, locale)
    if out.get("latency_ms"):
        ms = int(out["latency_ms"])
        out["latency_display"] = translate("speed.latency.ms", locale, ms=ms)
    if out.get("tested_at_iso"):
        out["tested_at_prefix"] = translate("speed.freshness.tested_at", locale, time=out.get("tested_at") or "")
    return out


def _localize_speed_test_subset(st: Dict[str, Any], se: Dict[str, Any]) -> None:
    """
    将 recommended.speed_test 与 speed_evidence 已本地化字段对齐。

    @param st: recommended.speed_test 字典（就地修改）
    @param se: 已本地化的 speed_evidence
    @returns: None
    """
    for key in (
        "age_display", "freshness_label", "validity_level",
        "avg_speed", "max_speed", "peers_total_display", "peers_reachable_display",
        "connect_rate_pct", "connect_rate_display", "peers_pair_display",
    ):
        if key in se:
            st[key] = se[key]


def _refresh_recommend_reason_torrent_meta(
    rec: Dict[str, Any],
    torrent_meta: Optional[Dict[str, Any]],
    locale: str,
) -> None:
    """
    将 swarm 体积交叉验证句追加到 ``recommend_reason``（A-11 候选）。

    @param rec: recommended 模板字典（就地修改）
    @param torrent_meta: ``torrent_metadata.to_template_dict()`` 结果
    @param locale: en | zh
    @returns: None
    """
    if not torrent_meta:
        return
    size_human = str(torrent_meta.get("total_size_human") or "").strip()
    match = str(torrent_meta.get("size_match") or "")
    if not size_human or match not in ("ok", "mismatch"):
        return

    from workflow.recommended.reason_i18n import reason_translate

    key = "swarm_size_verified" if match == "ok" else "swarm_size_mismatch"
    clause = reason_translate(key, locale, size=size_human)
    base = str(rec.get("recommend_reason") or "")
    if clause in base:
        return
    sep = "; " if normalize_locale(locale) == "en" else "；"
    rec["recommend_reason"] = f"{base}{sep}{clause}" if base else clause


def _refresh_recommend_reason_measured(
    rec: Dict[str, Any],
    localized_se: Dict[str, Any],
    locale: str,
) -> None:
    """
    用本地化 ``index_vs_measured`` 替换 ``recommend_reason`` 末尾实测句。

    @param rec: recommended 模板字典（就地修改）
    @param localized_se: 已本地化的 speed_evidence
    @param locale: en | zh
    @returns: None
    """
    measured = str(localized_se.get("index_vs_measured") or "").strip()
    if not measured:
        return
    base = str(rec.get("recommend_reason") or "")
    base = re.sub(
        r"[;；]\s*(?:索引 seeders|Indexed seeders).*",
        "",
        base,
        flags=re.DOTALL,
    ).strip()
    if measured in base:
        rec["recommend_reason"] = base
        return
    sep = "; " if normalize_locale(locale) == "en" else "；"
    if base:
        rec["recommend_reason"] = f"{base}{sep}{measured}"
    else:
        rec["recommend_reason"] = measured


def apply_page_locale(variables: Dict[str, Any], locale: str) -> None:
    """
    就地按 locale 重写测速与推荐理由等动态字段。

    @param variables: Jinja 模板变量 dict
    @param locale: en | zh
    @returns: None
    """
    from portal.generator.i18n_reason import localize_recommend_reason

    loc = normalize_locale(locale)
    recommended = variables.get("recommended")
    if isinstance(recommended, dict):
        localize_recommend_reason(recommended, loc)

    speed_ev = variables.get("speed_evidence")
    if isinstance(speed_ev, dict):
        localized = localize_speed_evidence_dict(speed_ev, loc)
        variables["speed_evidence"] = localized

        if isinstance(recommended, dict):
            release_title = str(recommended.get("title_raw") or recommended.get("release_title") or "")
            if recommended.get("grab_index"):
                grab = deepcopy(recommended["grab_index"])
                wrapper: Dict[str, Any] = {**localized, **grab}
                wrapper["grab_index_breakdown"] = deepcopy(grab.get("grab_index_breakdown") or [])
                _localize_grab(wrapper, loc)
                recommended["grab_index"] = {
                    **grab,
                    "grab_index_name": wrapper["grab_index_name"],
                    "grab_index_tagline": wrapper["grab_index_tagline"],
                    "grab_index_tier_label": wrapper["grab_index_tier_label"],
                    "grab_index_summary": wrapper["grab_index_summary"],
                    "grab_index_breakdown": wrapper["grab_index_breakdown"],
                }
            if recommended.get("speed_test"):
                _localize_speed_test_subset(recommended["speed_test"], localized)
            endorsement = _localize_endorsement(localized, loc, release_title)
            if endorsement:
                recommended["speed_endorsement"] = endorsement
            _refresh_recommend_reason_measured(recommended, localized, loc)
            _refresh_recommend_reason_torrent_meta(
                recommended,
                variables.get("torrent_metadata"),
                loc,
            )


def localize_page_variables(variables: Dict[str, Any], locale: str) -> Dict[str, Any]:
    """
    渲染前本地化页面上下文（``RM_SITE_LOCALE`` 固定语言模式）。

    @param variables: Jinja 模板变量 dict
    @param locale: en | zh
    @returns: 就地更新后的 variables
    """
    loc = normalize_locale(locale)
    if loc == "zh":
        return variables
    apply_page_locale(variables, loc)
    return variables
