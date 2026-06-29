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


def ensure_data_dirs() -> None:
    """确保 data/ 目录存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_accounts_config(path: Path | None = None) -> Dict[str, Any]:
    """
    加载 Jackett 等数据源配置。

    @param path: 配置文件路径；默认 accounts.local.json 或 example
    @returns: 配置字典
    """
    cfg_path = path or (ACCOUNTS_LOCAL if ACCOUNTS_LOCAL.exists() else ACCOUNTS_EXAMPLE)
    with open(cfg_path, encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    # 环境变量覆盖 JSON
    if JACKETT_API_KEY:
        data.setdefault("jackett", {})["api_key"] = JACKETT_API_KEY
    data.setdefault("jackett", {}).setdefault("base_url", JACKETT_BASE_URL)
    data.setdefault("eztv", {}).setdefault("base_url", EZTV_BASE_URL)
    data.setdefault("yts", {}).setdefault("base_url", YTS_BASE_URL)
    data.setdefault("nyaa", {}).setdefault("base_url", NYAA_BASE_URL)
    data.setdefault("rate_limit", {})["min_interval_sec"] = TORRENT_MIN_INTERVAL_SEC
    data.setdefault("cache", {})["seeders_ttl_hours"] = TORRENT_SEEDERS_TTL_HOURS
    return data
