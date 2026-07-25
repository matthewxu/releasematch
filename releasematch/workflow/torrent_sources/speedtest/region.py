# -*- coding: utf-8 -*-
"""
测速节点区域 ID 与展示文案解析。

@module workflow.torrent_sources.speedtest.region
@description
  页面测速证据需披露「从哪一出口测得」，避免用户误读为本地带宽。
  区域 ID 写入 ``slot_speed_summary.test_region``；展示文案按 locale 派生。
  配置：``RM_SPEEDTEST_REGION``（必填倾向，默认 jp-osa）、
  ``RM_SPEEDTEST_REGION_LABEL``（可选，覆盖 catalog 文案）。
"""

from __future__ import annotations

from typing import Dict, Optional

# 常见 Linode / 自建出口区域 ID → 双语展示名（与 linode_vps.DEFAULT_REGION 对齐）
REGION_CATALOG: Dict[str, Dict[str, str]] = {
    "jp-osa": {"en": "Japan · Osaka", "zh": "日本 · 大阪"},
    "jp-tyo": {"en": "Japan · Tokyo", "zh": "日本 · 东京"},
    "jp-tyo-3": {"en": "Japan · Tokyo", "zh": "日本 · 东京"},
    "ap-northeast": {"en": "Asia Pacific · Northeast", "zh": "亚太 · 东北"},
    "ap-south": {"en": "Asia Pacific · South", "zh": "亚太 · 南亚"},
    "ap-southeast": {"en": "Asia Pacific · Southeast", "zh": "亚太 · 东南亚"},
    "sg-sin-2": {"en": "Singapore", "zh": "新加坡"},
    "us-west": {"en": "US West", "zh": "美国西部"},
    "us-east": {"en": "US East", "zh": "美国东部"},
    "us-central": {"en": "US Central", "zh": "美国中部"},
    "us-southeast": {"en": "US Southeast", "zh": "美国东南"},
    "eu-central": {"en": "EU Central", "zh": "欧洲中部"},
    "eu-west": {"en": "EU West", "zh": "欧洲西部"},
    "de-fra-2": {"en": "Germany · Frankfurt", "zh": "德国 · 法兰克福"},
    "gb-lon": {"en": "UK · London", "zh": "英国 · 伦敦"},
    "au-mel": {"en": "Australia · Melbourne", "zh": "澳大利亚 · 墨尔本"},
    "in-maa": {"en": "India · Chennai", "zh": "印度 · 金奈"},
    "local": {"en": "Local node", "zh": "本机节点"},
    "unknown": {"en": "Unknown region", "zh": "未知区域"},
}

# 未配置时的默认出口（与 linode.example.json / 日本测速 VPS 惯例一致）
DEFAULT_SPEEDTEST_REGION: str = "jp-osa"


def normalize_region_id(raw: Optional[str]) -> str:
    """
    规范化测速区域 ID。

    @param raw: 原始区域字符串
    @returns: 小写去空白 ID；空则返回空串
    """
    return str(raw or "").strip().lower()


def get_configured_speedtest_region() -> str:
    """
    读取当前进程配置的测速出口区域 ID。

    @returns: 区域 ID（如 jp-osa）；未配置时用 DEFAULT_SPEEDTEST_REGION
    """
    from workflow import config as cfg

    configured = normalize_region_id(getattr(cfg, "SPEEDTEST_REGION", "") or "")
    return configured or DEFAULT_SPEEDTEST_REGION


def get_configured_speedtest_region_label_override() -> str:
    """
    读取可选的区域展示文案覆盖（不分 locale）。

    @returns: 覆盖文案；未设置时为空串
    """
    from workflow import config as cfg

    return str(getattr(cfg, "SPEEDTEST_REGION_LABEL", "") or "").strip()


def format_speedtest_region_label(
    region_id: Optional[str],
    *,
    locale: str = "zh",
    label_override: Optional[str] = None,
) -> str:
    """
    将区域 ID 格式化为页面展示文案。

    @param region_id: 区域 ID（如 jp-osa）
    @param locale: en | zh
    @param label_override: 非空时优先使用（配置覆盖）
    @returns: 展示文案；无 ID 时返回「—」
    """
    # None=读配置覆盖；显式传 "" 表示禁用覆盖、仅用 catalog
    if label_override is None:
        override = get_configured_speedtest_region_label_override()
    else:
        override = str(label_override or "").strip()
    if override:
        return override

    rid = normalize_region_id(region_id)
    if not rid:
        return "—"

    loc = "en" if str(locale or "").strip().lower().startswith("en") else "zh"
    entry = REGION_CATALOG.get(rid)
    if entry:
        return entry.get(loc) or entry.get("en") or rid
    # 未知 ID：原样展示，便于运维识别
    return rid


def resolve_speedtest_region_for_persist(
    region_id: Optional[str] = None,
) -> str:
    """
    测速写库时解析应持久化的区域 ID。

    @param region_id: 显式传入；缺省读配置
    @returns: 非空区域 ID
    """
    explicit = normalize_region_id(region_id)
    if explicit:
        return explicit
    return get_configured_speedtest_region()


def resolve_speedtest_region_for_display(
    stored_region: Optional[str] = None,
    *,
    locale: str = "zh",
) -> Dict[str, str]:
    """
    页面生成时解析测速区域展示字段。

    优先用库内 ``test_region``；空则回退当前配置（便于旧数据 regenerate 即可见）。

    @param stored_region: slot_speed_summary.test_region
    @param locale: en | zh
    @returns: test_region / test_region_label / test_region_display
    """
    rid = normalize_region_id(stored_region) or get_configured_speedtest_region()
    label = format_speedtest_region_label(rid, locale=locale)
    return {
        "test_region": rid,
        "test_region_label": label,
        # 主文案 + ID，便于核对出口（如 日本 · 大阪 · jp-osa）
        "test_region_display": f"{label} · {rid}" if rid and label not in ("—", rid) else (label or rid or "—"),
    }
