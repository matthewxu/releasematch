# -*- coding: utf-8 -*-
"""
TMDB 剧集季/集目录 MySQL 存储（ReleaseMatch 业务库）。

@module workflow.ops.tmdb_tv_store
@description
  供 Ops「清单从哪来」手动选 TV 槽：存储 crawler_tmdb 拉取后的
  seasons / episodes 精简字段。表见 schema/mysql_schema.sql §13–15。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from workflow.storage.mysql_store import MySQLStore, _normalize_row, _utc_now_str

# ── DDL（与 schema/mysql_schema.sql 对齐，ops serve 幂等建表）──────────────

_SERIES_DDL: str = """
CREATE TABLE IF NOT EXISTS tmdb_tv_series (
    tmdb_id                 INT UNSIGNED NOT NULL PRIMARY KEY,
    name                    VARCHAR(512) NOT NULL DEFAULT '',
    original_name           VARCHAR(512) NOT NULL DEFAULT '',
    number_of_seasons       SMALLINT UNSIGNED NULL,
    number_of_episodes      INT UNSIGNED NULL,
    first_air_date          DATE NULL,
    updated_at              DATETIME(3)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB TV 剧集摘要（Ops 季集选型）'
"""

_SEASONS_DDL: str = """
CREATE TABLE IF NOT EXISTS tmdb_tv_seasons (
    tmdb_id                 INT UNSIGNED NOT NULL,
    season_number           SMALLINT NOT NULL,
    name                    VARCHAR(256) NOT NULL DEFAULT '',
    episode_count           INT UNSIGNED NOT NULL DEFAULT 0,
    air_date                DATE NULL,
    poster_path             VARCHAR(256) NULL,
    updated_at              DATETIME(3)  NOT NULL,
    PRIMARY KEY (tmdb_id, season_number),
    KEY idx_tts_tmdb (tmdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB TV 季列表'
"""

_EPISODES_DDL: str = """
CREATE TABLE IF NOT EXISTS tmdb_tv_episodes (
    tmdb_id                 INT UNSIGNED NOT NULL,
    season_number           SMALLINT NOT NULL,
    episode_number          SMALLINT UNSIGNED NOT NULL,
    name                    VARCHAR(512) NOT NULL DEFAULT '',
    air_date                DATE NULL,
    runtime                 SMALLINT UNSIGNED NULL,
    overview                VARCHAR(512) NOT NULL DEFAULT '',
    still_path              VARCHAR(256) NULL,
    vote_average            DOUBLE NULL,
    updated_at              DATETIME(3)  NOT NULL,
    PRIMARY KEY (tmdb_id, season_number, episode_number),
    KEY idx_tte_lookup (tmdb_id, season_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB TV 分集列表'
"""

_SCHEMA_ENSURED: bool = False


def ensure_tables(store: Optional[MySQLStore] = None) -> Dict[str, Any]:
    """
    确保 TV 季集表存在。

    @param store: 可选 MySQLStore
    @returns: { ok }
    """
    global _SCHEMA_ENSURED
    store = store or MySQLStore()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_SERIES_DDL)
            cur.execute(_SEASONS_DDL)
            cur.execute(_EPISODES_DDL)
        conn.commit()
        _SCHEMA_ENSURED = True
        return {"ok": True}
    finally:
        conn.close()


def _ensure(store: Optional[MySQLStore] = None) -> MySQLStore:
    """惰性建表并返回 store。"""
    store = store or MySQLStore()
    if not _SCHEMA_ENSURED:
        ensure_tables(store)
    return store


def get_series(tmdb_id: int, store: Optional[MySQLStore] = None) -> Optional[Dict[str, Any]]:
    """
    读取剧集摘要行。

    @param tmdb_id: 剧集 ID
    @param store: 可选 store
    @returns: 行 dict 或 None
    """
    store = _ensure(store)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tmdb_tv_series WHERE tmdb_id = %s LIMIT 1",
                (int(tmdb_id),),
            )
            row = cur.fetchone()
            return _normalize_row(row) if row else None
    finally:
        conn.close()


def list_seasons(
    tmdb_id: int,
    *,
    include_specials: bool = False,
    store: Optional[MySQLStore] = None,
) -> List[Dict[str, Any]]:
    """
    读取已入库的季列表。

    @param tmdb_id: 剧集 ID
    @param include_specials: 是否含 season 0
    @param store: 可选 store
    @returns: 季摘要列表（按 season_number 升序）
    """
    store = _ensure(store)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            if include_specials:
                cur.execute(
                    """
                    SELECT season_number, name, episode_count, air_date, poster_path
                    FROM tmdb_tv_seasons
                    WHERE tmdb_id = %s
                    ORDER BY season_number ASC
                    """,
                    (int(tmdb_id),),
                )
            else:
                cur.execute(
                    """
                    SELECT season_number, name, episode_count, air_date, poster_path
                    FROM tmdb_tv_seasons
                    WHERE tmdb_id = %s AND season_number > 0
                    ORDER BY season_number ASC
                    """,
                    (int(tmdb_id),),
                )
            return [_normalize_row(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def list_episodes(
    tmdb_id: int,
    season_number: int,
    store: Optional[MySQLStore] = None,
) -> List[Dict[str, Any]]:
    """
    读取指定季已入库的分集列表。

    @param tmdb_id: 剧集 ID
    @param season_number: 季号
    @param store: 可选 store
    @returns: 分集列表（按 episode_number 升序）
    """
    store = _ensure(store)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT episode_number, name, air_date, runtime, overview,
                       still_path, vote_average
                FROM tmdb_tv_episodes
                WHERE tmdb_id = %s AND season_number = %s
                ORDER BY episode_number ASC
                """,
                (int(tmdb_id), int(season_number)),
            )
            return [_normalize_row(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def upsert_series_catalog(
    *,
    tmdb_id: int,
    name: str = "",
    original_name: str = "",
    number_of_seasons: Optional[int] = None,
    number_of_episodes: Optional[int] = None,
    first_air_date: Optional[str] = None,
    seasons: Optional[List[Dict[str, Any]]] = None,
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    UPSERT 剧集摘要，并可选整表替换该剧的 seasons 行。

    @param tmdb_id: 剧集 ID
    @param name: 剧名
    @param original_name: 原名
    @param number_of_seasons: 季数
    @param number_of_episodes: 总集数
    @param first_air_date: 首播日 YYYY-MM-DD
    @param seasons: 若给出则 DELETE+INSERT 替换该剧全部 seasons
    @param store: 可选 store
    @returns: { ok, tmdb_id, season_count }
    """
    store = _ensure(store)
    now = _utc_now_str()
    tid = int(tmdb_id)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tmdb_tv_series (
                    tmdb_id, name, original_name, number_of_seasons,
                    number_of_episodes, first_air_date, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    original_name = VALUES(original_name),
                    number_of_seasons = VALUES(number_of_seasons),
                    number_of_episodes = VALUES(number_of_episodes),
                    first_air_date = VALUES(first_air_date),
                    updated_at = VALUES(updated_at)
                """,
                (
                    tid,
                    (name or "")[:512],
                    (original_name or "")[:512],
                    number_of_seasons,
                    number_of_episodes,
                    first_air_date or None,
                    now,
                ),
            )
            season_count = 0
            if seasons is not None:
                cur.execute("DELETE FROM tmdb_tv_seasons WHERE tmdb_id = %s", (tid,))
                rows = []
                for s in seasons:
                    sn = int(s.get("season_number") or 0)
                    rows.append(
                        (
                            tid,
                            sn,
                            str(s.get("name") or "")[:256],
                            int(s.get("episode_count") or 0),
                            s.get("air_date") or None,
                            (s.get("poster_path") or None),
                            now,
                        )
                    )
                if rows:
                    cur.executemany(
                        """
                        INSERT INTO tmdb_tv_seasons (
                            tmdb_id, season_number, name, episode_count,
                            air_date, poster_path, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        rows,
                    )
                season_count = len(rows)
        conn.commit()
        return {"ok": True, "tmdb_id": tid, "season_count": season_count}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replace_season_episodes(
    *,
    tmdb_id: int,
    season_number: int,
    episodes: List[Dict[str, Any]],
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    替换某一季的全部分集行。

    @param tmdb_id: 剧集 ID
    @param season_number: 季号
    @param episodes: 分集精简列表
    @param store: 可选 store
    @returns: { ok, tmdb_id, season, episode_count }
    """
    store = _ensure(store)
    now = _utc_now_str()
    tid = int(tmdb_id)
    sn = int(season_number)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tmdb_tv_episodes WHERE tmdb_id = %s AND season_number = %s",
                (tid, sn),
            )
            rows = []
            for ep in episodes:
                en = int(ep.get("episode_number") or 0)
                if en <= 0:
                    continue
                runtime = ep.get("runtime")
                try:
                    runtime_i = int(runtime) if runtime is not None else None
                except (TypeError, ValueError):
                    runtime_i = None
                vote = ep.get("vote_average")
                try:
                    vote_f = float(vote) if vote is not None else None
                except (TypeError, ValueError):
                    vote_f = None
                rows.append(
                    (
                        tid,
                        sn,
                        en,
                        str(ep.get("name") or "")[:512],
                        ep.get("air_date") or None,
                        runtime_i,
                        str(ep.get("overview") or "")[:512],
                        ep.get("still_path") or None,
                        vote_f,
                        now,
                    )
                )
            if rows:
                cur.executemany(
                    """
                    INSERT INTO tmdb_tv_episodes (
                        tmdb_id, season_number, episode_number, name,
                        air_date, runtime, overview, still_path,
                        vote_average, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
        conn.commit()
        return {"ok": True, "tmdb_id": tid, "season": sn, "episode_count": len(rows)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
