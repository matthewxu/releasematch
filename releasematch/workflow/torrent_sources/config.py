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

from workflow.config import (
    DMHY_BASE_URL,
    EZTV_BASE_URL,
    JACKETT_API_KEY,
    JACKETT_BASE_URL,
    NYAA_BASE_URL,
    TORRENT_MIN_INTERVAL_SEC,
    TORRENT_SEEDERS_TTL_HOURS,
    YTS_BASE_URL,
)

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

    @param path: 配置文件路径；默认 accounts.local.json 或 example
    @returns: 配置字典
    """
    cfg_path = resolve_accounts_config_path(path)
    # utf-8-sig: 兼容 PowerShell Set-Content -Encoding UTF8 写入的 BOM
    with open(cfg_path, encoding="utf-8-sig") as f:
        data: Dict[str, Any] = json.load(f)

    # 环境变量覆盖 JSON
    if JACKETT_API_KEY:
        data.setdefault("jackett", {})["api_key"] = JACKETT_API_KEY
    data.setdefault("jackett", {}).setdefault("base_url", JACKETT_BASE_URL)
    data.setdefault("eztv", {}).setdefault("base_url", EZTV_BASE_URL)
    data.setdefault("yts", {}).setdefault("base_url", YTS_BASE_URL)
    data.setdefault("nyaa", {}).setdefault("base_url", NYAA_BASE_URL)
    data.setdefault("nyaa", {}).setdefault("enabled", True)
    data.setdefault("nyaa", {}).setdefault("mirrors", [])
    data.setdefault("nyaa_live_action", {}).setdefault("enabled", True)
    data.setdefault("nyaa_live_action", {}).setdefault("category", "4_0")
    if not data.get("nyaa_live_action", {}).get("base_url"):
        data.setdefault("nyaa_live_action", {})["base_url"] = data.get("nyaa", {}).get(
            "base_url", NYAA_BASE_URL
        )
    data.setdefault("dmhy", {}).setdefault("base_url", DMHY_BASE_URL)
    data.setdefault("dmhy", {}).setdefault("enabled", True)
    data.setdefault("dmhy", {}).setdefault("mirrors", [])
    data.setdefault("rate_limit", {})["min_interval_sec"] = TORRENT_MIN_INTERVAL_SEC
    data.setdefault("cache", {})["seeders_ttl_hours"] = TORRENT_SEEDERS_TTL_HOURS
    return data
