#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
torrent_sources 本地缓存索引（SQLite）。

@module workflow.torrent_sources.cache_index
@description
  记录 (tmdb, season, episode) 槽位的 magnet 清单与 seeders 刷新时间。
  对齐 opensubtitles/cache_index 模式，表结构独立。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.torrent_sources.config import CACHE_DB_PATH, ensure_data_dirs


class CacheIndex:
    """
    SQLite torrent 清单缓存。

    @param db_path: SQLite 文件路径
    """

    def __init__(self, db_path: Path = CACHE_DB_PATH) -> None:
        ensure_data_dirs()
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        """创建 SQLite 连接。"""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """初始化表结构。"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS torrent_cache (
                        cache_key TEXT PRIMARY KEY,
                        tmdb_id INTEGER NOT NULL,
                        media_type TEXT NOT NULL,
                        season INTEGER,
                        episode INTEGER,
                        payload_json TEXT NOT NULL,
                        item_count INTEGER NOT NULL DEFAULT 0,
                        fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                        expires_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_torrent_cache_tmdb
                    ON torrent_cache (tmdb_id, media_type)
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        查询缓存条目。

        @param cache_key: FetchRequest.cache_key()
        @returns: 命中时返回 dict，否则 None
        """
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM torrent_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
                if row is None:
                    return None
                return dict(row)
            finally:
                conn.close()

    def upsert(
        self,
        cache_key: str,
        tmdb_id: int,
        media_type: str,
        payload: List[Dict[str, Any]],
        expires_at: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> None:
        """
        写入或更新缓存。

        @param cache_key: 槽位键
        @param tmdb_id: TMDB ID
        @param media_type: movie 或 tv
        @param payload: ResourceItem 字典列表
        @param expires_at: ISO 过期时间
        @param season: 季号
        @param episode: 集号
        """
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO torrent_cache (
                        cache_key, tmdb_id, media_type, season, episode,
                        payload_json, item_count, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        item_count = excluded.item_count,
                        fetched_at = datetime('now'),
                        expires_at = excluded.expires_at
                    """,
                    (
                        cache_key,
                        tmdb_id,
                        media_type,
                        season,
                        episode,
                        json.dumps(payload, ensure_ascii=False),
                        len(payload),
                        expires_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def count(self) -> int:
        """返回缓存槽位总数。"""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) AS c FROM torrent_cache").fetchone()
                return int(row["c"]) if row else 0
            finally:
                conn.close()
