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
import re
from pathlib import Path

# ── 目录 ──────────────────────────────────────────────────

# releasematch/ 根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """
    从项目根目录 `.env` 加载环境变量（不覆盖已存在的系统变量）。

    @returns: None
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

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

# 直连失败时回退的代理（本机 SSH SOCKS：socks5h://127.0.0.1:1080）
TORRENT_PROXY: str = os.getenv(
    "TORRENT_PROXY",
    os.getenv("TORRENT_HTTP_PROXY", ""),
)

TORRENT_MIN_INTERVAL_SEC: float = float(os.getenv("TORRENT_MIN_INTERVAL_SEC", "2.0"))
TORRENT_SEEDERS_TTL_HOURS: int = int(os.getenv("TORRENT_SEEDERS_TTL_HOURS", "6"))

# ── Release 业务存储（MySQL 本地测试 → D1 生产）────────────────────────

# mysql: 本地/CI 使用 MySQL（schema/mysql_schema.sql）
# d1:    生产 Cloudflare D1（schema/d1_schema.sql，通过 sync Worker 写入）
STORAGE_BACKEND: str = os.getenv("RM_STORAGE_BACKEND", "mysql").strip().lower()

# Release 业务库（与 TMDB 元数据库分离；默认同实例不同 database）
RELEASE_MYSQL_HOST: str = os.getenv("RM_RELEASE_MYSQL_HOST", MYSQL_HOST)
RELEASE_MYSQL_PORT: int = int(os.getenv("RM_RELEASE_MYSQL_PORT", str(MYSQL_PORT)))
RELEASE_MYSQL_DB: str = os.getenv("RM_RELEASE_MYSQL_DB", "releasematch")
RELEASE_MYSQL_USER: str = os.getenv("RM_RELEASE_MYSQL_USER", MYSQL_USER)
RELEASE_MYSQL_PASSWORD: str = os.getenv("RM_RELEASE_MYSQL_PASSWORD", MYSQL_PASSWORD)

# D1 生产配置（RM_STORAGE_BACKEND=d1 时使用，T3 sync Worker 读取）
D1_DATABASE_NAME: str = os.getenv("RM_D1_DATABASE_NAME", "releasematch")
D1_BINDING: str = os.getenv("RM_D1_BINDING", "DB")

# SQL 文件路径
MYSQL_SCHEMA_FILE: Path = SCHEMA_DIR / "mysql_schema.sql"
MYSQL_SEED_DEMO_FILE: Path = SCHEMA_DIR / "mysql_seed_demo.sql"
D1_SCHEMA_FILE: Path = SCHEMA_DIR / "d1_schema.sql"
D1_SEED_DEMO_FILE: Path = SCHEMA_DIR / "d1_seed_demo.sql"

# 站点 origin（生成 canonical URL）
SITE_ORIGIN: str = os.getenv("RM_SITE_ORIGIN", "https://releasematch.io")


def _env_bool(name: str, default: bool = False) -> bool:
    """
    解析布尔型环境变量。

    @param name: 变量名
    @param default: 未设置时的默认值
    @returns: True 当值为 1/true/yes/on（不区分大小写）
    """
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


# 生成器 / dev server：页面底部展示 IG 分级 debug 面板（仅本地测试，生产应关闭）
SHOW_IG_DEBUG: bool = _env_bool("RM_SHOW_IG_DEBUG", False)


def release_mysql_configured() -> bool:
    """
    检查 Release MySQL 连接参数是否已配置。

    @returns: user 非空时为 True
    """
    return bool(RELEASE_MYSQL_USER)


def ensure_project_dirs() -> None:
    """
    确保运行时数据目录存在。

    @returns: None
    """
    (WORKFLOW_DIR / "torrent_sources" / "data").mkdir(parents=True, exist_ok=True)
    (WORKFLOW_DIR / "recommended" / "data").mkdir(parents=True, exist_ok=True)
