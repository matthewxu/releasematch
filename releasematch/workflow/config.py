#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch 工作流全局配置。

@module workflow.config
@description
  集中管理项目根路径、MySQL 可选桥接、数据源环境变量默认值。
  不依赖 tmdbpy/workflow/config.py 或字幕站配置。
"""

from __future__ import annotations

import os
from pathlib import Path

# ── 目录 ──────────────────────────────────────────────────

# releasematch/ 根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# workflow/ 目录
WORKFLOW_DIR: Path = PROJECT_ROOT / "workflow"

# schema/ SQL 文件
SCHEMA_DIR: Path = PROJECT_ROOT / "schema"

# ── TMDB 元数据桥接（可选，只读）──────────────────────────

# standalone: 使用 JSON 静态清单，不连 MySQL
# mysql: 只读连接 TMDB 元数据库（与字幕站共享 MySQL 实例时可启用）
TMDB_DATA_MODE: str = os.getenv("RM_TMDB_DATA_MODE", "standalone")

MYSQL_HOST: str = os.getenv("RM_MYSQL_HOST", "127.0.0.1")
MYSQL_PORT: int = int(os.getenv("RM_MYSQL_PORT", "3306"))
MYSQL_DB: str = os.getenv("RM_MYSQL_DB", "test")
MYSQL_USER: str = os.getenv("RM_MYSQL_USER", "")
MYSQL_PASSWORD: str = os.getenv("RM_MYSQL_PASSWORD", "")

# ── 数据源默认端点 ────────────────────────────────────────

JACKETT_BASE_URL: str = os.getenv("JACKETT_BASE_URL", "http://127.0.0.1:9117")
JACKETT_API_KEY: str = os.getenv("JACKETT_API_KEY", "")

EZTV_BASE_URL: str = os.getenv("EZTV_BASE_URL", "https://eztvx.to")
YTS_BASE_URL: str = os.getenv("YTS_BASE_URL", "https://yts.lt")
NYAA_BASE_URL: str = os.getenv("NYAA_BASE_URL", "https://nyaa.si")

TORRENT_MIN_INTERVAL_SEC: float = float(os.getenv("TORRENT_MIN_INTERVAL_SEC", "2.0"))
TORRENT_SEEDERS_TTL_HOURS: int = int(os.getenv("TORRENT_SEEDERS_TTL_HOURS", "6"))


def ensure_project_dirs() -> None:
    """
    确保运行时数据目录存在。

    @returns: None
    """
    (WORKFLOW_DIR / "torrent_sources" / "data").mkdir(parents=True, exist_ok=True)
    (WORKFLOW_DIR / "recommended" / "data").mkdir(parents=True, exist_ok=True)
