# -*- coding: utf-8 -*-
"""
TMDB 剧集季/集目录 — 复用 crawler_tmdb API，结果写入 ReleaseMatch MySQL。

@module workflow.metadata.tmdb_tv_catalog
@description
  供 Ops「清单从哪来」手动选槽：拉 TV 的 seasons / episodes，
  避免硬编码默认 S01E01。

  调用链：
    1. 确保 sibling 包 ``tmdb/tmdbpy/crawler_tmdb`` 可 import
    2. 优先读 MySQL ``tmdb_tv_*``；未命中再调 ``tv_details`` / ``tv_season_details``
    3. crawler 原始响应缓存进业务库 ``tmdb_api_cache``（MySQL，非 JSON 文件）
    4. 精简季/集 UPSERT 到 ``tmdb_tv_series`` / ``tmdb_tv_seasons`` / ``tmdb_tv_episodes``

  环境变量：
    RM_CRAWLER_TMDB_ROOT — crawler_tmdb 包根目录
    RM_RELEASE_MYSQL_* — 业务库（季集与 API 缓存落库）
    RM_TMDB_API_KEY / TMDB_API_KEY（可选；优先 crawler api_config）
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from workflow.config import (
    PROJECT_ROOT,
    RELEASE_MYSQL_DB,
    RELEASE_MYSQL_HOST,
    RELEASE_MYSQL_PASSWORD,
    RELEASE_MYSQL_PORT,
    RELEASE_MYSQL_USER,
    TMDB_API_BASE,
    TMDB_API_KEY,
    TMDB_API_TIMEOUT,
    TMDB_CORS_PROXY_URL,
    release_mysql_configured,
)
from workflow.ops import tmdb_tv_store

#: 默认 sibling 路径：trafficforvideo/tmdb/tmdbpy/crawler_tmdb
_DEFAULT_CRAWLER_ROOT: Path = (
    PROJECT_ROOT.parent.parent / "tmdb" / "tmdbpy" / "crawler_tmdb"
)


def resolve_crawler_root() -> Path:
    """
    解析 crawler_tmdb 安装/源码根目录。

    优先级：环境变量 ``RM_CRAWLER_TMDB_ROOT`` > 默认 sibling 路径。

    @returns: 包含 ``crawler_tmdb`` 子包的目录
    @raises FileNotFoundError: 路径不存在
    """
    import os

    raw = (os.getenv("RM_CRAWLER_TMDB_ROOT") or "").strip()
    root = Path(raw) if raw else _DEFAULT_CRAWLER_ROOT
    root = root.resolve()
    if not (root / "crawler_tmdb").is_dir():
        raise FileNotFoundError(
            f"未找到 crawler_tmdb 包：{root}；"
            "请设置 RM_CRAWLER_TMDB_ROOT 或 pip install -e 该目录"
        )
    return root


def _ensure_crawler_on_path() -> Path:
    """
    将 crawler_tmdb 根目录插入 ``sys.path``（若尚未可 import）。

    @returns: crawler 根路径
    """
    try:
        import crawler_tmdb  # noqa: F401

        from crawler_tmdb.legacy_bridge import get_project_root

        return Path(get_project_root())
    except ImportError:
        root = resolve_crawler_root()
        root_s = str(root)
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
        import crawler_tmdb  # noqa: F401

        return root


def _resolve_api_key() -> str:
    """
    解析 TMDB API Key。

    优先级：crawler_tmdb ``api_config.API_KEY`` → ``RM_TMDB_API_KEY`` / ``TMDB_API_KEY``。

    @returns: API Key 字符串
    @raises ValueError: 两端均未配置
    """
    try:
        _ensure_crawler_on_path()
        from crawler_tmdb.legacy_bridge import import_legacy

        api = import_legacy("api_config")
        key = str(getattr(api, "API_KEY", "") or "").strip()
        if key:
            return key
    except Exception:  # noqa: BLE001
        pass
    if TMDB_API_KEY:
        return str(TMDB_API_KEY).strip()
    raise ValueError(
        "未配置 TMDB API Key：请在 crawler_tmdb/api_config.py 设置 API_KEY，"
        "或设置 RM_TMDB_API_KEY / TMDB_API_KEY"
    )


def _resolve_proxy_url() -> Optional[str]:
    """
    解析 CORS Proxy：优先 crawler ``api_config``，否则 ReleaseMatch 配置。

    @returns: 代理根 URL 或 None
    """
    try:
        _ensure_crawler_on_path()
        from crawler_tmdb.legacy_bridge import import_legacy

        api = import_legacy("api_config")
        proxy = str(getattr(api, "CORS_PROXY_URL", "") or "").strip()
        if proxy:
            return proxy
    except Exception:  # noqa: BLE001
        pass
    return (TMDB_CORS_PROXY_URL or "").strip() or None


def _resolve_api_base() -> str:
    """
    解析 TMDB API Base。

    @returns: 如 https://api.themoviedb.org/3
    """
    try:
        _ensure_crawler_on_path()
        from crawler_tmdb.legacy_bridge import import_legacy

        api = import_legacy("api_config")
        base = str(
            getattr(api, "TARGET_API_BASE", None)
            or getattr(api, "BASE_API_URL", "")
            or ""
        ).strip()
        if base:
            return base.rstrip("/")
    except Exception:  # noqa: BLE001
        pass
    return (TMDB_API_BASE or "https://api.themoviedb.org/3").rstrip("/")


_client_singleton: Any = None


def get_crawler_client(*, force_refresh: bool = False) -> Any:
    """
    获取 crawler_tmdb ``TMDbClient``，API 缓存在 ReleaseMatch MySQL ``tmdb_api_cache``。

    @param force_refresh: True 时客户端默认跳过缓存
    @returns: ``TMDbClient`` 实例
    @raises ValueError: 未配置业务 MySQL
    """
    global _client_singleton
    if not release_mysql_configured():
        raise ValueError(
            "未配置 RM_RELEASE_MYSQL_*；TV 季集须写入业务 MySQL，请先配置 .env"
        )

    _ensure_crawler_on_path()
    from crawler_tmdb import CrawlerConfig, MySQLConfig, StorageBackendType, TMDbClient

    if _client_singleton is not None:
        cfg = _client_singleton.config
        if bool(getattr(cfg, "force_refresh", False)) == bool(force_refresh):
            return _client_singleton
        try:
            _client_singleton.close()
        except Exception:  # noqa: BLE001
            pass
        _client_singleton = None

    # 原始 API JSON → 业务库 tmdb_api_cache；季集精简表另由 tmdb_tv_store 维护
    config = CrawlerConfig(
        api_key=_resolve_api_key(),
        base_url=_resolve_api_base(),
        storage_backend=StorageBackendType.MYSQL,
        mysql=MySQLConfig(
            host=RELEASE_MYSQL_HOST,
            port=int(RELEASE_MYSQL_PORT),
            user=RELEASE_MYSQL_USER,
            password=RELEASE_MYSQL_PASSWORD or "",
            database=RELEASE_MYSQL_DB,
            charset="utf8mb4",
            table_name="tmdb_api_cache",
        ),
        force_refresh=bool(force_refresh),
        timeout=TMDB_API_TIMEOUT,
        proxy_url=_resolve_proxy_url(),
        legacy_normalized=False,
    )
    _client_singleton = TMDbClient(config)
    return _client_singleton


def _slim_season(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    压缩 TV ``seasons[]`` 摘要项。

    @param raw: TMDB season 摘要
    @returns: UI / MySQL 用精简字段
    """
    return {
        "season_number": int(raw.get("season_number") or 0),
        "name": raw.get("name") or "",
        "episode_count": int(raw.get("episode_count") or 0),
        "air_date": raw.get("air_date") or None,
        "poster_path": raw.get("poster_path") or None,
    }


def _slim_episode(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    压缩单集字段。

    @param raw: TMDB episode 项
    @returns: UI / MySQL 用精简字段
    """
    return {
        "episode_number": int(raw.get("episode_number") or 0),
        "name": raw.get("name") or "",
        "air_date": raw.get("air_date") or None,
        "runtime": raw.get("runtime"),
        "overview": (raw.get("overview") or "")[:240],
        "still_path": raw.get("still_path") or None,
        "vote_average": raw.get("vote_average"),
    }


def _row_to_season(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    MySQL 季行 → UI 结构。

    @param row: DB 行
    @returns: 精简季对象
    """
    return {
        "season_number": int(row.get("season_number") or 0),
        "name": row.get("name") or "",
        "episode_count": int(row.get("episode_count") or 0),
        "air_date": row.get("air_date"),
        "poster_path": row.get("poster_path"),
    }


def _row_to_episode(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    MySQL 分集行 → UI 结构。

    @param row: DB 行
    @returns: 精简集对象
    """
    return {
        "episode_number": int(row.get("episode_number") or 0),
        "name": row.get("name") or "",
        "air_date": row.get("air_date"),
        "runtime": row.get("runtime"),
        "overview": row.get("overview") or "",
        "still_path": row.get("still_path"),
        "vote_average": row.get("vote_average"),
    }


def list_seasons(
    tmdb_id: int,
    *,
    force_refresh: bool = False,
    include_specials: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取剧集季列表：优先 MySQL，未命中则 crawler_tmdb 拉取并入库。

    @param tmdb_id: 剧集 TMDB ID
    @param force_refresh: True 时强制打 TMDB 并覆盖 MySQL
    @param include_specials: 是否包含 season 0（Specials）
    @param language: 可选语言，如 ``zh-CN``
    @returns: ``{ ok, tmdb_id, name, seasons, source, cached }``
    """
    tid = int(tmdb_id)
    if tid <= 0:
        return {"ok": False, "error": "无效 tmdb_id"}

    tmdb_tv_store.ensure_tables()

    if not force_refresh:
        seasons_rows = tmdb_tv_store.list_seasons(
            tid, include_specials=include_specials
        )
        if seasons_rows:
            series = tmdb_tv_store.get_series(tid) or {}
            return {
                "ok": True,
                "tmdb_id": tid,
                "name": series.get("name") or "",
                "original_name": series.get("original_name") or "",
                "number_of_seasons": series.get("number_of_seasons"),
                "seasons": [_row_to_season(r) for r in seasons_rows],
                "source": "mysql.tmdb_tv_seasons",
                "storage": "mysql",
                "cached": True,
            }

    try:
        client = get_crawler_client(force_refresh=force_refresh)
        from crawler_tmdb.api import tv_details

        raw = tv_details(tid, client=client, language=language)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"拉取 TV 详情失败: {exc}", "tmdb_id": tid}

    if not isinstance(raw, dict) or not raw.get("id"):
        return {"ok": False, "error": "TMDB 返回空/无效", "tmdb_id": tid}

    seasons_raw = [
        _slim_season(s) for s in (raw.get("seasons") or []) if isinstance(s, dict)
    ]
    tmdb_tv_store.upsert_series_catalog(
        tmdb_id=tid,
        name=str(raw.get("name") or ""),
        original_name=str(raw.get("original_name") or ""),
        number_of_seasons=raw.get("number_of_seasons"),
        number_of_episodes=raw.get("number_of_episodes"),
        first_air_date=raw.get("first_air_date"),
        seasons=seasons_raw,
    )

    seasons_out = list(seasons_raw)
    if not include_specials:
        seasons_out = [s for s in seasons_out if int(s.get("season_number") or 0) > 0]

    return {
        "ok": True,
        "tmdb_id": tid,
        "name": str(raw.get("name") or ""),
        "original_name": str(raw.get("original_name") or ""),
        "number_of_seasons": raw.get("number_of_seasons"),
        "seasons": seasons_out,
        "source": "crawler_tmdb.tv_details",
        "storage": "mysql",
        "tables": ["tmdb_tv_series", "tmdb_tv_seasons", "tmdb_api_cache"],
        "cached": False,
    }


def list_episodes(
    tmdb_id: int,
    season_number: int,
    *,
    force_refresh: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取指定季分集：优先 MySQL，未命中则 crawler_tmdb 拉取并入库。

    @param tmdb_id: 剧集 TMDB ID
    @param season_number: 季号（0=Specials）
    @param force_refresh: True 时强制打 TMDB
    @param language: 可选语言
    @returns: ``{ ok, tmdb_id, season, episodes, source, ... }``
    """
    tid = int(tmdb_id)
    sn = int(season_number)
    if tid <= 0:
        return {"ok": False, "error": "无效 tmdb_id"}
    if sn < 0:
        return {"ok": False, "error": "无效 season_number"}

    tmdb_tv_store.ensure_tables()

    if not force_refresh:
        ep_rows = tmdb_tv_store.list_episodes(tid, sn)
        if ep_rows:
            series = tmdb_tv_store.get_series(tid) or {}
            return {
                "ok": True,
                "tmdb_id": tid,
                "season": sn,
                "name": series.get("name") or "",
                "episodes": [_row_to_episode(r) for r in ep_rows],
                "source": "mysql.tmdb_tv_episodes",
                "storage": "mysql",
                "cached": True,
            }

    try:
        client = get_crawler_client(force_refresh=force_refresh)
        from crawler_tmdb.api import tv_season_details

        raw = tv_season_details(tid, sn, client=client, language=language)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"拉取季详情失败: {exc}",
            "tmdb_id": tid,
            "season": sn,
        }

    if not isinstance(raw, dict):
        return {"ok": False, "error": "TMDB 季响应无效", "tmdb_id": tid, "season": sn}

    episodes = [
        _slim_episode(ep)
        for ep in (raw.get("episodes") or [])
        if isinstance(ep, dict) and int(ep.get("episode_number") or 0) > 0
    ]
    episodes.sort(key=lambda e: int(e.get("episode_number") or 0))

    if not tmdb_tv_store.get_series(tid) or not tmdb_tv_store.list_seasons(
        tid, include_specials=True
    ):
        list_seasons(
            tid, force_refresh=False, include_specials=True, language=language
        )

    tmdb_tv_store.replace_season_episodes(
        tmdb_id=tid, season_number=sn, episodes=episodes
    )
    series = tmdb_tv_store.get_series(tid) or {}

    return {
        "ok": True,
        "tmdb_id": tid,
        "season": sn,
        "season_name": raw.get("name") or f"Season {sn}",
        "name": series.get("name") or "",
        "episodes": episodes,
        "source": "crawler_tmdb.tv_season_details",
        "storage": "mysql",
        "tables": ["tmdb_tv_episodes", "tmdb_api_cache"],
        "cached": False,
    }


def ensure_catalog(
    tmdb_id: int,
    *,
    season: Optional[int] = None,
    force_refresh: bool = False,
    include_specials: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    确保 MySQL 有季列表；若指定 ``season`` 则同时拉该季分集。

    @param tmdb_id: 剧集 ID
    @param season: 可选季号
    @param force_refresh: 强制刷新
    @param include_specials: 含 Specials
    @param language: 语言
    @returns: seasons 结果 + 可选 episodes
    """
    seasons_result = list_seasons(
        tmdb_id,
        force_refresh=force_refresh,
        include_specials=include_specials,
        language=language,
    )
    if not seasons_result.get("ok"):
        return seasons_result

    out: Dict[str, Any] = dict(seasons_result)
    if season is not None:
        ep_result = list_episodes(
            tmdb_id,
            int(season),
            force_refresh=force_refresh,
            language=language,
        )
        out["episodes_result"] = ep_result
        if ep_result.get("ok"):
            out["episodes"] = ep_result.get("episodes") or []
            out["season"] = int(season)
        else:
            out["ok"] = False
            out["error"] = ep_result.get("error")
    return out
