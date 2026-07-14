# -*- coding: utf-8 -*-
"""
TMDB Daily Export → MySQL 入库与检索。

@module workflow.ops.tmdb_export_store
@description
  流程：每天**全量下载** .json.gz → **增量入库**（UPSERT + 清理过期 ID）
  → Ops UI 从库搜索筛选 → 再写入工作区。
  亦支持 force replace（TRUNCATE 后全量重建）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from workflow.metadata.tmdb_export_slots import iter_ndjson_gz
from workflow.storage.mysql_store import MySQLStore, _normalize_row, _utc_now_str

# DDL：与 schema/mysql_schema.sql §11–12 对齐（ops serve 幂等建表）
_TMDB_META_DDL: str = """
CREATE TABLE IF NOT EXISTS tmdb_export_meta (
    id                      TINYINT UNSIGNED NOT NULL PRIMARY KEY DEFAULT 1,
    export_date             DATE         NOT NULL,
    movie_count             INT UNSIGNED NOT NULL DEFAULT 0,
    tv_count                INT UNSIGNED NOT NULL DEFAULT 0,
    movie_gz                VARCHAR(128) DEFAULT '',
    tv_gz                   VARCHAR(128) DEFAULT '',
    status                  VARCHAR(16)  NOT NULL DEFAULT 'ready',
    ingest_mode             VARCHAR(16)  NOT NULL DEFAULT 'incremental',
    last_scanned            INT UNSIGNED NOT NULL DEFAULT 0,
    last_deleted            INT UNSIGNED NOT NULL DEFAULT 0,
    loaded_at               DATETIME(3)  NOT NULL,
    updated_at              DATETIME(3)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_TMDB_TITLES_DDL: str = """
CREATE TABLE IF NOT EXISTS tmdb_export_titles (
    media_type              ENUM('movie','tv') NOT NULL,
    tmdb_id                 INT UNSIGNED NOT NULL,
    title                   VARCHAR(512) NOT NULL,
    title_lc                VARCHAR(512) NOT NULL,
    popularity              DOUBLE       NOT NULL DEFAULT 0,
    adult                   TINYINT(1)   NOT NULL DEFAULT 0,
    video                   TINYINT(1)   NOT NULL DEFAULT 0,
    export_date             DATE         NOT NULL,
    updated_at              DATETIME(3)  NOT NULL,
    PRIMARY KEY (media_type, tmdb_id),
    KEY idx_tet_media_pop (media_type, popularity),
    KEY idx_tet_title_lc (title_lc(64)),
    KEY idx_tet_export_date (export_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# 已有库升迁：补增量统计列（幂等）
_META_ALTERS: Tuple[str, ...] = (
    "ALTER TABLE tmdb_export_meta ADD COLUMN ingest_mode VARCHAR(16) NOT NULL DEFAULT 'incremental'",
    "ALTER TABLE tmdb_export_meta ADD COLUMN last_scanned INT UNSIGNED NOT NULL DEFAULT 0",
    "ALTER TABLE tmdb_export_meta ADD COLUMN last_deleted INT UNSIGNED NOT NULL DEFAULT 0",
)

_SCHEMA_ENSURED: bool = False

# UPSERT：主键冲突时更新字段；export_date 始终刷新以便 prune 删除过期 ID
_UPSERT_SQL: str = """
INSERT INTO tmdb_export_titles (
    media_type, tmdb_id, title, title_lc, popularity, adult, video, export_date, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    title_lc = VALUES(title_lc),
    popularity = VALUES(popularity),
    adult = VALUES(adult),
    video = VALUES(video),
    export_date = VALUES(export_date),
    updated_at = VALUES(updated_at)
"""


def ensure_tables(store: Optional[MySQLStore] = None) -> Dict[str, Any]:
    """
    确保 TMDB 导出表存在，并为旧库补齐增量相关列。

    @param store: 可选 MySQLStore
    @returns: { ok }
    """
    global _SCHEMA_ENSURED
    store = store or MySQLStore()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_TMDB_META_DDL)
            cur.execute(_TMDB_TITLES_DDL)
            for alter_sql in _META_ALTERS:
                try:
                    cur.execute(alter_sql)
                except Exception:  # noqa: BLE001 — 列已存在则忽略
                    pass
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


def get_meta(store: Optional[MySQLStore] = None) -> Optional[Dict[str, Any]]:
    """
    读取 tmdb_export_meta 单行。

    @param store: 可选 MySQLStore
    @returns: 元信息 dict 或 None
    """
    store = _ensure(store)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tmdb_export_meta WHERE id = 1 LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            return _normalize_row(dict(row))
    finally:
        conn.close()


def is_db_ready(store: Optional[MySQLStore] = None) -> bool:
    """
    库中是否已有可用导出数据（meta + 实际行数双重校验）。

    @param store: 可选 MySQLStore
    @returns: True 表示可搜索
    """
    store = _ensure(store)
    meta = get_meta(store)
    if not meta:
        return False
    if str(meta.get("status") or "") != "ready":
        return False
    if int(meta.get("movie_count") or 0) <= 0 or int(meta.get("tv_count") or 0) <= 0:
        return False
    # 防止 meta 与表数据脱节后误判「已就绪」而跳过同步
    return _count_media(store, "movie") > 0 and _count_media(store, "tv") > 0


def meta_summary(store: Optional[MySQLStore] = None) -> Dict[str, Any]:
    """
    供进度 / API 的库端就绪摘要。

    @param store: 可选 MySQLStore
    @returns: { ok, ready, export_date, movie_count, tv_count, ingest_mode, … }
    """
    store = _ensure(store)
    meta = get_meta(store)
    if not meta:
        return {
            "ok": True,
            "ready": False,
            "storage": "mysql",
            "export_date": None,
            "movie_count": 0,
            "tv_count": 0,
            "ingest_mode": None,
            "last_scanned": 0,
            "last_deleted": 0,
        }
    export_date = meta.get("export_date")
    if hasattr(export_date, "isoformat"):
        export_date = export_date.isoformat()
    return {
        "ok": True,
        "ready": str(meta.get("status")) == "ready"
        and int(meta.get("movie_count") or 0) > 0,
        "storage": "mysql",
        "export_date": export_date,
        "movie_count": int(meta.get("movie_count") or 0),
        "tv_count": int(meta.get("tv_count") or 0),
        "movie_gz": meta.get("movie_gz") or "",
        "tv_gz": meta.get("tv_gz") or "",
        "loaded_at": str(meta.get("loaded_at") or ""),
        "status": meta.get("status"),
        "ingest_mode": meta.get("ingest_mode") or "incremental",
        "last_scanned": int(meta.get("last_scanned") or 0),
        "last_deleted": int(meta.get("last_deleted") or 0),
    }


def _count_media(store: MySQLStore, media_type: str) -> int:
    """
    统计某 media_type 当前行数。

    @param store: MySQLStore
    @param media_type: movie | tv
    @returns: 行数
    """
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM tmdb_export_titles WHERE media_type = %s",
                (media_type,),
            )
            return int((cur.fetchone() or {}).get("c") or 0)
    finally:
        conn.close()


def _set_meta_loading(
    store: MySQLStore,
    *,
    export_date: date,
    movie_gz: str,
    tv_gz: str,
    ingest_mode: str,
    preserve_counts: bool,
) -> None:
    """
    写入 loading 状态元信息。

    @param store: MySQLStore
    @param export_date: 本次导出日
    @param movie_gz: 电影文件名
    @param tv_gz: 剧集文件名
    @param ingest_mode: incremental | replace
    @param preserve_counts: 增量时保留旧计数（便于加载中仍可读）
    """
    now = _utc_now_str()
    if preserve_counts:
        movie_count_sql = "movie_count"
        tv_count_sql = "tv_count"
    else:
        movie_count_sql = "0"
        tv_count_sql = "0"
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO tmdb_export_meta (
                    id, export_date, movie_count, tv_count, movie_gz, tv_gz,
                    status, ingest_mode, last_scanned, last_deleted,
                    loaded_at, updated_at
                ) VALUES (1, %s, 0, 0, %s, %s, 'loading', %s, 0, 0, %s, %s)
                ON DUPLICATE KEY UPDATE
                    export_date = VALUES(export_date),
                    movie_gz = VALUES(movie_gz),
                    tv_gz = VALUES(tv_gz),
                    status = 'loading',
                    ingest_mode = VALUES(ingest_mode),
                    movie_count = {movie_count_sql},
                    tv_count = {tv_count_sql},
                    updated_at = VALUES(updated_at)
                """,
                (
                    export_date.isoformat(),
                    movie_gz,
                    tv_gz,
                    ingest_mode,
                    now,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _finish_meta(
    store: MySQLStore,
    *,
    export_date: date,
    movie_count: int,
    tv_count: int,
    movie_gz: str,
    tv_gz: str,
    ingest_mode: str,
    last_scanned: int,
    last_deleted: int,
) -> None:
    """
    标记入库完成并写入统计。

    @param store: MySQLStore
    @param export_date: 导出日
    @param movie_count: 电影行数
    @param tv_count: 剧集行数
    @param movie_gz: 电影文件名
    @param tv_gz: 剧集文件名
    @param ingest_mode: incremental | replace
    @param last_scanned: 本次扫描行数（movie+tv）
    @param last_deleted: 本次 prune 删除行数
    """
    now = _utc_now_str()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tmdb_export_meta SET
                    export_date = %s,
                    movie_count = %s,
                    tv_count = %s,
                    movie_gz = %s,
                    tv_gz = %s,
                    status = 'ready',
                    ingest_mode = %s,
                    last_scanned = %s,
                    last_deleted = %s,
                    loaded_at = %s,
                    updated_at = %s
                WHERE id = 1
                """,
                (
                    export_date.isoformat(),
                    movie_count,
                    tv_count,
                    movie_gz,
                    tv_gz,
                    ingest_mode,
                    last_scanned,
                    last_deleted,
                    now,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def truncate_titles(store: Optional[MySQLStore] = None) -> None:
    """
    清空标题表（全量重建前）。

    @param store: 可选 MySQLStore
    """
    store = _ensure(store)
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE tmdb_export_titles")
        conn.commit()
    finally:
        conn.close()


def prune_stale_titles(
    *,
    media_type: str,
    export_date: date,
    store: Optional[MySQLStore] = None,
) -> int:
    """
    删除未出现在本次导出行中的旧 ID（export_date 仍早于本次）。

    @param media_type: movie | tv
    @param export_date: 本次导出日（已 UPSERT 的行均为此日）
    @param store: 可选 MySQLStore
    @returns: 删除行数
    """
    store = _ensure(store)
    media = "movie" if media_type == "movie" else "tv"
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM tmdb_export_titles
                WHERE media_type = %s AND export_date < %s
                """,
                (media, export_date.isoformat()),
            )
            deleted = int(cur.rowcount or 0)
        conn.commit()
        return deleted
    finally:
        conn.close()


def ingest_export_file(
    gz_path: Path,
    *,
    media_type: str,
    export_date: date,
    batch_size: int = 2000,
    on_progress: Optional[Callable[[int], None]] = None,
    store: Optional[MySQLStore] = None,
) -> int:
    """
    将单个 .json.gz 流式 UPSERT 写入 MySQL（全量读文件、增量写库）。

    @param gz_path: 导出文件
    @param media_type: movie | tv
    @param export_date: 导出日
    @param batch_size: 批量 UPSERT 大小
    @param on_progress: 已扫描条数回调
    @param store: 可选 MySQLStore
    @returns: 扫描并写入条数
    """
    store = _ensure(store)
    media = "movie" if media_type == "movie" else "tv"
    now = _utc_now_str()
    export_s = export_date.isoformat()
    batch: List[Tuple[Any, ...]] = []
    total = 0

    def _flush(cur: Any) -> None:
        """刷写一批 UPSERT。"""
        nonlocal batch, total
        if not batch:
            return
        cur.executemany(_UPSERT_SQL, batch)
        total += len(batch)
        batch = []
        if on_progress:
            on_progress(total)

    conn = store._connect()
    try:
        with conn.cursor() as cur:
            for row in iter_ndjson_gz(gz_path):
                tmdb_id = int(row["id"])
                if media == "movie":
                    title = str(
                        row.get("original_title") or row.get("title") or f"movie:{tmdb_id}"
                    )
                    video = 1 if row.get("video") else 0
                else:
                    title = str(
                        row.get("original_name") or row.get("name") or f"tv:{tmdb_id}"
                    )
                    video = 0
                title = title[:512]
                batch.append(
                    (
                        media,
                        tmdb_id,
                        title,
                        title.lower(),
                        float(row.get("popularity") or 0.0),
                        1 if row.get("adult") else 0,
                        video,
                        export_s,
                        now,
                    )
                )
                if len(batch) >= batch_size:
                    _flush(cur)
                    conn.commit()
            _flush(cur)
            conn.commit()
    finally:
        conn.close()
    if on_progress:
        on_progress(total)
    return total


def sync_from_export_files(
    *,
    movie_gz: Path,
    tv_gz: Path,
    export_date: date,
    mode: str = "incremental",
    on_phase: Optional[Callable[[str, int, str], None]] = None,
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    下载完成后将全量导出同步进 MySQL。

    - ``incremental``（默认）：UPSERT 全文件 + 按 export_date prune 消失的 ID。
    - ``replace``：TRUNCATE 后 UPSERT（强制全量重建）。

    @param movie_gz: 电影导出
    @param tv_gz: 剧集导出
    @param export_date: 导出日
    @param mode: incremental | replace
    @param on_phase: (phase, count, message) 进度回调
    @param store: 可选 MySQLStore
    @returns: meta_summary（含 last_scanned / last_deleted）
    """
    store = _ensure(store)
    ingest_mode = "replace" if mode == "replace" else "incremental"
    _set_meta_loading(
        store,
        export_date=export_date,
        movie_gz=movie_gz.name,
        tv_gz=tv_gz.name,
        ingest_mode=ingest_mode,
        preserve_counts=(ingest_mode == "incremental"),
    )

    if ingest_mode == "replace":
        if on_phase:
            on_phase("truncate", 0, "清空旧索引表（全量重建）…")
        truncate_titles(store)

    def _movie_prog(n: int) -> None:
        """电影 UPSERT 进度。"""
        if on_phase:
            on_phase("movies_db", n, f"增量入库电影…已处理 {n:,} 条")

    def _tv_prog(n: int) -> None:
        """剧集 UPSERT 进度。"""
        if on_phase:
            on_phase("tv_db", n, f"增量入库剧集…已处理 {n:,} 条")

    if on_phase:
        on_phase("movies_db", 0, f"开始{'重建' if ingest_mode == 'replace' else '增量'}电影 {movie_gz.name}")
    movie_scanned = ingest_export_file(
        movie_gz,
        media_type="movie",
        export_date=export_date,
        on_progress=_movie_prog,
        store=store,
    )
    movie_deleted = 0
    if ingest_mode == "incremental":
        if on_phase:
            on_phase("prune_movies", movie_scanned, "清理电影库中已下线 ID…")
        movie_deleted = prune_stale_titles(
            media_type="movie", export_date=export_date, store=store
        )

    if on_phase:
        on_phase("tv_db", 0, f"开始{'重建' if ingest_mode == 'replace' else '增量'}剧集 {tv_gz.name}")
    tv_scanned = ingest_export_file(
        tv_gz,
        media_type="tv",
        export_date=export_date,
        on_progress=_tv_prog,
        store=store,
    )
    tv_deleted = 0
    if ingest_mode == "incremental":
        if on_phase:
            on_phase("prune_tv", tv_scanned, "清理剧集库中已下线 ID…")
        tv_deleted = prune_stale_titles(
            media_type="tv", export_date=export_date, store=store
        )

    movie_count = _count_media(store, "movie")
    tv_count = _count_media(store, "tv")
    last_scanned = movie_scanned + tv_scanned
    last_deleted = movie_deleted + tv_deleted
    _finish_meta(
        store,
        export_date=export_date,
        movie_count=movie_count,
        tv_count=tv_count,
        movie_gz=movie_gz.name,
        tv_gz=tv_gz.name,
        ingest_mode=ingest_mode,
        last_scanned=last_scanned,
        last_deleted=last_deleted,
    )
    if on_phase:
        on_phase(
            "done",
            last_scanned,
            (
                f"{'全量重建' if ingest_mode == 'replace' else '增量入库'}完成 · "
                f"movie {movie_count:,} · tv {tv_count:,} · "
                f"扫描 {last_scanned:,} · 删除 {last_deleted:,}"
            ),
        )
    return meta_summary(store)


def replace_from_export_files(
    *,
    movie_gz: Path,
    tv_gz: Path,
    export_date: date,
    on_phase: Optional[Callable[[str, int, str], None]] = None,
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    兼容旧调用：等同 ``sync_from_export_files(mode='replace')``。

    @param movie_gz: 电影导出
    @param tv_gz: 剧集导出
    @param export_date: 导出日
    @param on_phase: 进度回调
    @param store: 可选 MySQLStore
    @returns: meta_summary
    """
    return sync_from_export_files(
        movie_gz=movie_gz,
        tv_gz=tv_gz,
        export_date=export_date,
        mode="replace",
        on_phase=on_phase,
        store=store,
    )


def lookup_titles(
    keys: Sequence[Tuple[str, int]],
    store: Optional[MySQLStore] = None,
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """
    批量按 (media_type, tmdb_id) 查标题。

    @param keys: (media_type, tmdb_id) 列表
    @param store: 可选 MySQLStore
    @returns: 映射
    """
    if not keys:
        return {}
    store = _ensure(store)
    out: Dict[Tuple[str, int], Dict[str, Any]] = {}
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            for media, tmdb_id in keys:
                cur.execute(
                    """
                    SELECT media_type, tmdb_id, title, popularity, adult, video
                    FROM tmdb_export_titles
                    WHERE media_type = %s AND tmdb_id = %s
                    LIMIT 1
                    """,
                    (media, int(tmdb_id)),
                )
                row = cur.fetchone()
                if row:
                    out[(str(row["media_type"]), int(row["tmdb_id"]))] = _normalize_row(
                        dict(row)
                    )
    finally:
        conn.close()
    return out


def search_titles(
    *,
    q: Optional[str] = None,
    media_types: Optional[List[str]] = None,
    pop_min: Optional[float] = None,
    pop_max: Optional[float] = None,
    exclude_adult: bool = True,
    exclude_video: bool = True,
    limit: int = 50,
    offset: int = 0,
    store: Optional[MySQLStore] = None,
) -> Dict[str, Any]:
    """
    从 MySQL 搜索/筛选导出标题。

    @param q: 标题子串或纯数字 TMDB ID
    @param media_types: movie / tv
    @param pop_min: 最低 popularity
    @param pop_max: 最高 popularity
    @param exclude_adult: 排除成人内容
    @param exclude_video: 电影排除 video 标记
    @param limit: 返回条数
    @param offset: 分页偏移
    @param store: 可选 MySQLStore
    @returns: { hits, total_matched, meta }
    """
    store = _ensure(store)
    meta = meta_summary(store)
    if not meta.get("ready"):
        return {
            "ok": False,
            "error": "TMDB 导出尚未入库；请先「下载并入库」",
            "hits": [],
            "total_matched": 0,
            "meta": meta,
        }

    media_set = [m.lower() for m in (media_types or ["movie", "tv"]) if m]
    if not media_set:
        media_set = ["movie", "tv"]
    placeholders = ", ".join(["%s"] * len(media_set))

    where: List[str] = [f"media_type IN ({placeholders})"]
    params: List[Any] = list(media_set)

    if exclude_adult:
        where.append("adult = 0")
    if exclude_video:
        where.append("(media_type = 'tv' OR video = 0)")
    if pop_min is not None:
        where.append("popularity >= %s")
        params.append(float(pop_min))
    if pop_max is not None:
        where.append("popularity <= %s")
        params.append(float(pop_max))

    q_raw = (q or "").strip()
    if q_raw.isdigit():
        where.append("tmdb_id = %s")
        params.append(int(q_raw))
    elif q_raw:
        where.append("title_lc LIKE %s")
        params.append(f"%{q_raw.lower()}%")

    where_sql = " AND ".join(where)
    limit_n = max(1, min(int(limit), 200))
    offset_n = max(0, int(offset))

    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) AS c FROM tmdb_export_titles WHERE {where_sql}",
                params,
            )
            total = int((cur.fetchone() or {}).get("c") or 0)
            cur.execute(
                f"""
                SELECT media_type, tmdb_id, title, popularity, adult, video
                FROM tmdb_export_titles
                WHERE {where_sql}
                ORDER BY popularity DESC
                LIMIT %s OFFSET %s
                """,
                [*params, limit_n, offset_n],
            )
            rows = [_normalize_row(dict(r)) for r in (cur.fetchall() or [])]
    finally:
        conn.close()

    return {
        "ok": True,
        "hits": rows,
        "total_matched": total,
        "offset": offset_n,
        "limit": limit_n,
        "meta": {
            **{
                k: meta[k]
                for k in (
                    "export_date",
                    "movie_count",
                    "tv_count",
                    "storage",
                    "ingest_mode",
                    "last_scanned",
                    "last_deleted",
                )
            },
            "q": q_raw or None,
            "media_types": media_set,
            "pop_min": pop_min,
            "pop_max": pop_max,
            "exclude_adult": exclude_adult,
            "exclude_video": exclude_video,
        },
    }
