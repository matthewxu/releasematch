#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch 工作流全局配置。

@module workflow.config
@description
  集中管理项目根路径、MySQL 可选桥接、数据源环境变量默认值。
  支持从 ``.env`` 启动加载，以及 Ops 控制台热刷新（``reload_runtime_config``）。
  不依赖 tmdbpy/workflow/config.py 或字幕站配置。
"""

from __future__ import annotations

import os
from pathlib import Path

# ── 目录 ──────────────────────────────────────────────────

# releasematch/ 根目录
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


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


def load_dotenv_file(*, overwrite: bool = False) -> Path | None:
    """
    从项目根目录 ``.env`` 加载键值到 ``os.environ``。

    @param overwrite: True 时用文件值覆盖已有环境变量（Ops「加载到进程」）；
      False 时仅填充尚未存在的键（启动默认行为）
    @returns: 实际读取的 ``.env`` 路径；文件不存在时为 None
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        if overwrite or key not in os.environ:
            os.environ[key] = value
    return env_path


def apply_environ_to_module() -> None:
    """
    用当前 ``os.environ`` 刷新本模块全部运行时常量。

    @description
      供 Ops 控制台「保存后加载到进程」调用，避免必须重启 ``ops serve``。
      路径类常量（PROJECT_ROOT / SCHEMA 文件）不变。
    @returns: None
    """
    global TMDB_DATA_MODE, TMDB_API_KEY, TMDB_CORS_PROXY_URL, TMDB_API_BASE, TMDB_API_TIMEOUT
    global MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD
    global JACKETT_BASE_URL, JACKETT_API_KEY
    global EZTV_BASE_URL, YTS_BASE_URL, NYAA_BASE_URL, DMHY_BASE_URL, TORRENT_PROXY
    global TORRENT_MIN_INTERVAL_SEC, TORRENT_SEEDERS_TTL_HOURS
    global STORAGE_BACKEND
    global RELEASE_MYSQL_HOST, RELEASE_MYSQL_PORT, RELEASE_MYSQL_DB
    global RELEASE_MYSQL_USER, RELEASE_MYSQL_PASSWORD
    global D1_DATABASE_NAME, D1_BINDING, SITE_ORIGIN
    global SHOW_IG_DEBUG, SITE_I18N_ENABLED, SITE_LOCALE

    # standalone: JSON 清单；mysql: 只读 TMDB 元数据库
    TMDB_DATA_MODE = os.getenv("RM_TMDB_DATA_MODE", "standalone")
    # TMDB v3 API Key（扩槽 imdb/tvdb）
    TMDB_API_KEY = os.getenv("RM_TMDB_API_KEY", os.getenv("TMDB_API_KEY", ""))
    # TMDB CORS Proxy（Cloudflare Workers）
    TMDB_CORS_PROXY_URL = os.getenv(
        "RM_TMDB_CORS_PROXY",
        os.getenv("TMDB_CORS_PROXY_URL", "https://api.weidaohang.org/cp/"),
    )
    # TMDB API 根路径
    TMDB_API_BASE = os.getenv(
        "RM_TMDB_API_BASE",
        os.getenv("TMDB_API_BASE", "https://api.themoviedb.org/3"),
    )
    # (connect_sec, read_sec)
    TMDB_API_TIMEOUT = (
        int(os.getenv("RM_TMDB_API_CONNECT_TIMEOUT", "6")),
        int(os.getenv("RM_TMDB_API_READ_TIMEOUT", "12")),
    )

    # TMDB 元数据 MySQL（可选桥接）
    MYSQL_HOST = os.getenv("RM_MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("RM_MYSQL_PORT", "3306"))
    MYSQL_DB = os.getenv("RM_MYSQL_DB", "test")
    MYSQL_USER = os.getenv("RM_MYSQL_USER", "")
    MYSQL_PASSWORD = os.getenv("RM_MYSQL_PASSWORD", "")

    # 数据源默认端点 / Key
    JACKETT_BASE_URL = os.getenv("JACKETT_BASE_URL", "http://127.0.0.1:9117")
    JACKETT_API_KEY = os.getenv("JACKETT_API_KEY", "")
    EZTV_BASE_URL = os.getenv("EZTV_BASE_URL", "https://eztvx.to")
    YTS_BASE_URL = os.getenv("YTS_BASE_URL", "https://yts.lt")
    NYAA_BASE_URL = os.getenv("NYAA_BASE_URL", "https://nyaa.si")
    # 动漫花园 RSS
    DMHY_BASE_URL = os.getenv("DMHY_BASE_URL", "https://share.dmhy.org")
    # 直连失败回退代理
    TORRENT_PROXY = os.getenv("TORRENT_PROXY", os.getenv("TORRENT_HTTP_PROXY", ""))
    TORRENT_MIN_INTERVAL_SEC = float(os.getenv("TORRENT_MIN_INTERVAL_SEC", "2.0"))
    TORRENT_SEEDERS_TTL_HOURS = int(os.getenv("TORRENT_SEEDERS_TTL_HOURS", "6"))

    # mysql | d1
    STORAGE_BACKEND = os.getenv("RM_STORAGE_BACKEND", "mysql").strip().lower()
    # Release 业务库（与 TMDB 元数据库分离）
    RELEASE_MYSQL_HOST = os.getenv("RM_RELEASE_MYSQL_HOST", MYSQL_HOST)
    RELEASE_MYSQL_PORT = int(os.getenv("RM_RELEASE_MYSQL_PORT", str(MYSQL_PORT)))
    RELEASE_MYSQL_DB = os.getenv("RM_RELEASE_MYSQL_DB", "releasematch")
    RELEASE_MYSQL_USER = os.getenv("RM_RELEASE_MYSQL_USER", MYSQL_USER)
    RELEASE_MYSQL_PASSWORD = os.getenv("RM_RELEASE_MYSQL_PASSWORD", MYSQL_PASSWORD)
    # D1 生产绑定名
    D1_DATABASE_NAME = os.getenv("RM_D1_DATABASE_NAME", "releasematch")
    D1_BINDING = os.getenv("RM_D1_BINDING", "DB")
    # 站点 canonical origin
    SITE_ORIGIN = os.getenv("RM_SITE_ORIGIN", "https://releasematch.io")
    # 页面 IG debug 面板
    SHOW_IG_DEBUG = _env_bool("RM_SHOW_IG_DEBUG", False)
    # UI 国际化开关
    SITE_I18N_ENABLED = _env_bool("RM_SITE_I18N_ENABLED", False)
    # 默认 UI 语言
    SITE_LOCALE = os.getenv("RM_SITE_LOCALE", "en").strip().lower() or "en"


def reload_runtime_config(*, overwrite_environ: bool = True) -> Path | None:
    """
    重新读取 ``.env`` 并刷新本模块常量（Ops 热加载入口）。

    @param overwrite_environ: 是否用文件覆盖 ``os.environ`` 中已有键
    @returns: 读取到的 ``.env`` 路径；无文件时为 None（仍会按当前 environ 刷新常量）
    """
    env_path = load_dotenv_file(overwrite=overwrite_environ)
    apply_environ_to_module()
    return env_path


# 启动时：不覆盖系统已导出变量
load_dotenv_file(overwrite=False)

# workflow/ 目录
WORKFLOW_DIR: Path = PROJECT_ROOT / "workflow"

# schema/ SQL 文件目录
SCHEMA_DIR: Path = PROJECT_ROOT / "schema"

# ── 运行时常量（占位后由 apply_environ_to_module 填充）────────────────

# standalone | mysql — TMDB 元数据模式
TMDB_DATA_MODE: str = "standalone"
# TMDB v3 API Key
TMDB_API_KEY: str = ""
# TMDB CORS Proxy URL
TMDB_CORS_PROXY_URL: str = "https://api.weidaohang.org/cp/"
# TMDB API base
TMDB_API_BASE: str = "https://api.themoviedb.org/3"
# TMDB HTTP 超时 (connect, read)
TMDB_API_TIMEOUT: tuple[int, int] = (6, 12)

# TMDB 元数据 MySQL
MYSQL_HOST: str = "127.0.0.1"
MYSQL_PORT: int = 3306
MYSQL_DB: str = "test"
MYSQL_USER: str = ""
MYSQL_PASSWORD: str = ""

# Jackett / 直连源默认
JACKETT_BASE_URL: str = "http://127.0.0.1:9117"
JACKETT_API_KEY: str = ""
EZTV_BASE_URL: str = "https://eztvx.to"
YTS_BASE_URL: str = "https://yts.lt"
NYAA_BASE_URL: str = "https://nyaa.si"
DMHY_BASE_URL: str = "https://share.dmhy.org"
TORRENT_PROXY: str = ""
TORRENT_MIN_INTERVAL_SEC: float = 2.0
TORRENT_SEEDERS_TTL_HOURS: int = 6

# 存储后端与 Release MySQL / D1
STORAGE_BACKEND: str = "mysql"
RELEASE_MYSQL_HOST: str = "127.0.0.1"
RELEASE_MYSQL_PORT: int = 3306
RELEASE_MYSQL_DB: str = "releasematch"
RELEASE_MYSQL_USER: str = ""
RELEASE_MYSQL_PASSWORD: str = ""
D1_DATABASE_NAME: str = "releasematch"
D1_BINDING: str = "DB"

# SQL 文件路径（不随热加载变化）
MYSQL_SCHEMA_FILE: Path = SCHEMA_DIR / "mysql_schema.sql"
MYSQL_SEED_DEMO_FILE: Path = SCHEMA_DIR / "mysql_seed_demo.sql"
D1_SCHEMA_FILE: Path = SCHEMA_DIR / "d1_schema.sql"
D1_SEED_DEMO_FILE: Path = SCHEMA_DIR / "d1_seed_demo.sql"

# 站点与生成器开关
SITE_ORIGIN: str = "https://releasematch.io"
SHOW_IG_DEBUG: bool = False
SITE_I18N_ENABLED: bool = False
SITE_LOCALE: str = "en"

# 用已加载的 environ 填充上述常量
apply_environ_to_module()


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
