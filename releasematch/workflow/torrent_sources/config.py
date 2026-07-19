#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
torrent_sources 模块配置。

@module workflow.torrent_sources.config
@description Jackett/EZTV/YTS 端点、本地 data 目录、限速参数。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import workflow.config as wc

MODULE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = MODULE_DIR / "data"
CACHE_DB_PATH: Path = DATA_DIR / "cache_index.sqlite3"

ACCOUNTS_EXAMPLE: Path = MODULE_DIR / "accounts.example.json"
ACCOUNTS_LOCAL: Path = MODULE_DIR / "accounts.local.json"

# Jackett API Key 占位符（视为未配置）
JACKETT_API_KEY_PLACEHOLDERS: frozenset[str] = frozenset(
    {"", "YOUR_JACKETT_API_KEY", "changeme", "replace_me"}
)


def resolve_accounts_config_path(path: Path | None = None) -> Path:
    """
    解析实际使用的 accounts 配置文件路径。

    @param path: 显式指定路径；默认 local 优先，否则 example
    @returns: 配置文件 Path
    """
    if path is not None:
        return path
    return ACCOUNTS_LOCAL if ACCOUNTS_LOCAL.exists() else ACCOUNTS_EXAMPLE


def is_jackett_api_key_configured(api_key: str | None) -> bool:
    """
    判断 Jackett API Key 是否已配置（非空且非占位符）。

    @param api_key: 来自 JSON 或环境变量
    @returns: True 表示可用于 Torznab 请求
    """
    if not api_key:
        return False
    normalized = api_key.strip()
    return normalized.lower() not in {p.lower() for p in JACKETT_API_KEY_PLACEHOLDERS}


def probe_jackett_http(base_url: str, timeout_sec: float = 5.0) -> Dict[str, Any]:
    """
    探测 Jackett HTTP 服务是否可达（块 A 环境验收）。

    @param base_url: Jackett 根 URL，如 http://127.0.0.1:9117
    @param timeout_sec: 请求超时秒数
    @returns: reachable、status_code 或 error
    """
    import requests  # noqa: WPS433 — 与 requirements 一致

    url = base_url.rstrip("/") + "/"
    try:
        response = requests.get(url, timeout=timeout_sec)
        return {
            "reachable": True,
            "status_code": response.status_code,
            "url": url,
        }
    except requests.RequestException as exc:
        return {
            "reachable": False,
            "error": str(exc),
            "url": url,
        }


def ensure_data_dirs() -> None:
    """确保 data/ 目录存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_accounts_config(path: Path | None = None) -> Dict[str, Any]:
    """
    加载 Jackett 等数据源配置。

    @description
      **真相源为 accounts JSON**（``accounts.local.json`` / example）。
      ``workflow.config`` / ``.env`` 中的 JACKETT_*、源站 URL、限速等仅在 JSON
      **缺键**时补默认值；不再用 ``.env`` 覆盖已写入 JSON 的字段。
      临时排障仍可在 shell ``export JACKETT_API_KEY=...``：仅当 JSON 的 Key
      未配置（空/占位符）时才会采用。

    @param path: 配置文件路径；默认 accounts.local.json 或 example
    @returns: 配置字典
    """
    cfg_path = resolve_accounts_config_path(path)
    # utf-8-sig: 兼容 PowerShell Set-Content -Encoding UTF8 写入的 BOM
    with open(cfg_path, encoding="utf-8-sig") as f:
        data: Dict[str, Any] = json.load(f)

    jackett = data.setdefault("jackett", {})
    # JSON 优先；仅 Key 未配置时允许环境变量补齐（CI / 一次性排查）
    if not is_jackett_api_key_configured(str(jackett.get("api_key") or "")):
        if wc.JACKETT_API_KEY:
            jackett["api_key"] = wc.JACKETT_API_KEY
    jackett.setdefault("base_url", wc.JACKETT_BASE_URL)

    data.setdefault("eztv", {}).setdefault("base_url", wc.EZTV_BASE_URL)
    data.setdefault("yts", {}).setdefault("base_url", wc.YTS_BASE_URL)
    data.setdefault("nyaa", {}).setdefault("base_url", wc.NYAA_BASE_URL)
    data.setdefault("nyaa", {}).setdefault("enabled", True)
    data.setdefault("nyaa", {}).setdefault("mirrors", [])
    data.setdefault("nyaa_live_action", {}).setdefault("enabled", True)
    data.setdefault("nyaa_live_action", {}).setdefault("category", "4_0")
    if not data.get("nyaa_live_action", {}).get("base_url"):
        data.setdefault("nyaa_live_action", {})["base_url"] = data.get("nyaa", {}).get(
            "base_url", wc.NYAA_BASE_URL
        )
    data.setdefault("nyaa_anime", {}).setdefault("enabled", True)
    data.setdefault("nyaa_anime", {}).setdefault("category", "1_0")
    if not data.get("nyaa_anime", {}).get("base_url"):
        data.setdefault("nyaa_anime", {})["base_url"] = data.get("nyaa", {}).get(
            "base_url", wc.NYAA_BASE_URL
        )
    data.setdefault("cn_sources", {}).setdefault(
        "jackett", ["dmhy", "mikan", "acgrip"]
    )
    data.setdefault("cn_sources", {}).setdefault(
        "direct", ["dmhy", "nyaa_live_action", "nyaa_anime"]
    )
    data.setdefault("dmhy", {}).setdefault("base_url", wc.DMHY_BASE_URL)
    data.setdefault("dmhy", {}).setdefault("enabled", True)
    data.setdefault("dmhy", {}).setdefault("mirrors", [])

    # 限速 / 缓存：JSON 已有则保留，缺省才用 workflow.config 默认
    rate = data.setdefault("rate_limit", {})
    rate.setdefault("min_interval_sec", wc.TORRENT_MIN_INTERVAL_SEC)
    cache = data.setdefault("cache", {})
    cache.setdefault("seeders_ttl_hours", wc.TORRENT_SEEDERS_TTL_HOURS)
    return data
