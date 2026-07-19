#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch MySQL 存储层。

@module workflow.storage.mysql_store
@description
  读写 schema/mysql_schema.sql 定义的 7 张业务表。
  供总控 pipeline 与页面生成器在本地测试阶段使用。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from workflow.config import (
    MYSQL_SCHEMA_FILE,
    MYSQL_SEED_DEMO_FILE,
    RELEASE_MYSQL_DB,
    RELEASE_MYSQL_HOST,
    RELEASE_MYSQL_PASSWORD,
    RELEASE_MYSQL_PORT,
    RELEASE_MYSQL_USER,
    SITE_ORIGIN,
    release_mysql_configured,
)
from schema.d1_models import (
    DownloadResource,
    EpisodePageContext,
    MediaCatalog,
    MediaPage,
    MoviePageContext,
    ShowHubPageContext,
    SlotSpeedSummary,
    SpeedEvidenceContext,
    SpeedTestResult,
    TorrentMetadataContext,
    TorrentMetadataRecord,
    build_catalog_id,
    build_page_id,
    is_speed_evidence_publishable,
)


def _utc_now_str() -> str:
    """
    返回当前 UTC 时间字符串（MySQL DATETIME(3) 兼容）。

    @returns: 如 2026-06-29 12:00:00.000
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _clip_str(value: object, max_len: int) -> str:
    """
    截断字符串以适配 MySQL VARCHAR 列宽。

    @param value: 任意值（非 str 则 str()）
    @param max_len: 最大字符数
    @returns: 截断后的字符串
    """
    text = str(value or "")
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 PyMySQL 行转为 d1_models.from_row 可消费的 dict。

    @param row: PyMySQL DictCursor 行
    @returns: JSON 友好字典
    """
    out: Dict[str, Any] = {}
    for key, val in row.items():
        if isinstance(val, datetime):
            out[key] = val.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        elif isinstance(val, Decimal):
            out[key] = float(val)
        elif hasattr(val, "isoformat"):  # date
            out[key] = val.isoformat()
        elif isinstance(val, (bytes, bytearray)):
            out[key] = val.decode("utf-8")
        else:
            out[key] = val
    return out


class MySQLStore:
    """
    Release 业务 MySQL 访问对象。

    @var host: MySQL 主机
    @var port: 端口
    @var database: 数据库名
    @var user: 用户名
    @var password: 密码
    """

    def __init__(
        self,
        host: str = RELEASE_MYSQL_HOST,
        port: int = RELEASE_MYSQL_PORT,
        database: str = RELEASE_MYSQL_DB,
        user: str = RELEASE_MYSQL_USER,
        password: str = RELEASE_MYSQL_PASSWORD,
    ) -> None:
        """初始化连接参数（延迟连接）。"""
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

    def _connect_server(self):
        """
        连接 MySQL 实例（不指定 database），用于建库。

        @returns: pymysql Connection
        """
        if not release_mysql_configured():
            raise RuntimeError(
                "Release MySQL 未配置：请设置 RM_RELEASE_MYSQL_USER（及 PASSWORD/DB）"
            )
        try:
            import pymysql  # noqa: WPS433
        except ImportError as exc:
            raise RuntimeError("请安装 PyMySQL：pip install PyMySQL") from exc

        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @staticmethod
    def _validate_database_name(database: str) -> str:
        """
        校验数据库名，防止 SQL 注入。

        @param database: 来自环境变量的库名
        @returns: 合法库名
        @raises ValueError: 含非法字符时
        """
        name = database.strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            raise ValueError(f"非法数据库名: {database!r}（仅允许字母、数字、下划线）")
        return name

    def ensure_database(self) -> Dict[str, Any]:
        """
        创建 Release 业务库（不存在则 CREATE DATABASE）。

        @returns: 建库摘要
        """
        db_name = self._validate_database_name(self.database)
        try:
            conn = self._connect_server()
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                cur.execute(
                    """
                    SELECT SCHEMA_NAME AS db_name
                    FROM information_schema.SCHEMATA
                    WHERE SCHEMA_NAME = %s
                    """,
                    (db_name,),
                )
                row = cur.fetchone()
            conn.close()
            return {
                "ok": bool(row),
                "step": "create_database",
                "host": self.host,
                "port": self.port,
                "database": db_name,
                "charset": "utf8mb4",
                "collation": "utf8mb4_unicode_ci",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "step": "create_database",
                "host": self.host,
                "database": db_name,
                "error": str(exc),
            }

    def _connect(self):
        """
        创建 PyMySQL 连接。

        @returns: pymysql Connection
        @raises RuntimeError: 未安装 pymysql 或未配置 user
        """
        if not release_mysql_configured():
            raise RuntimeError(
                "Release MySQL 未配置：请设置 RM_RELEASE_MYSQL_USER（及 PASSWORD/DB）"
            )
        try:
            import pymysql  # noqa: WPS433
        except ImportError as exc:
            raise RuntimeError("请安装 PyMySQL：pip install PyMySQL") from exc

        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def ping(self) -> Dict[str, Any]:
        """
        检测 MySQL 连通性与表是否存在。

        @returns: 状态字典
        """
        if not release_mysql_configured():
            return {
                "ok": False,
                "backend": "mysql",
                "error": "RM_RELEASE_MYSQL_USER 未设置",
                "database": self.database,
            }

        expected_tables = [
            "release_groups",
            "media_catalog",
            "media_pages",
            "download_resources",
            "slot_speed_summary",
            "speedtest_results",
            "torrent_metadata",
            "sync_runs",
            "download_inventory",
        ]
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute("SELECT DATABASE() AS db_name, VERSION() AS version")
                meta = cur.fetchone()
                cur.execute("SHOW TABLES")
                existing = {list(r.values())[0] for r in cur.fetchall()}
            conn.close()
            missing = [t for t in expected_tables if t not in existing]
            return {
                "ok": len(missing) == 0,
                "backend": "mysql",
                "host": self.host,
                "port": self.port,
                "database": meta.get("db_name") if meta else self.database,
                "mysql_version": meta.get("version") if meta else None,
                "tables_found": sorted(existing),
                "tables_missing": missing,
            }
        except Exception as exc:  # noqa: BLE001 — CLI 需捕获并展示
            err = str(exc)
            hint = None
            if "Unknown database" in err or "1049" in err:
                hint = f"请先执行: python -m workflow.run db init（将自动创建库 {self.database}）"
            return {
                "ok": False,
                "backend": "mysql",
                "host": self.host,
                "database": self.database,
                "error": err,
                "hint": hint,
            }

    def execute_sql_file(self, sql_path: Path) -> Dict[str, Any]:
        """
        执行 SQL 文件（按语句分割，跳过空行与注释块）。

        @param sql_path: .sql 文件路径
        @returns: 执行摘要
        """
        if not sql_path.is_file():
            raise FileNotFoundError(f"SQL 文件不存在: {sql_path}")

        raw = sql_path.read_text(encoding="utf-8")
        statements = self._split_sql_statements(raw)
        conn = self._connect()
        executed = 0
        errors: List[str] = []
        with conn.cursor() as cur:
            for stmt in statements:
                try:
                    cur.execute(stmt)
                    executed += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{exc}: {stmt[:120]}...")
        conn.close()
        return {
            "file": str(sql_path),
            "statements_executed": executed,
            "errors": errors,
            "ok": len(errors) == 0,
        }

    @staticmethod
    def _split_sql_statements(sql_text: str) -> List[str]:
        """
        将 SQL 文件拆分为可执行语句列表。

        @param sql_text: 原始 SQL 文本
        @returns: 语句列表
        """
        # 去掉单行注释
        lines = []
        for line in sql_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines)
        parts = re.split(r";\s*\n", cleaned)
        return [p.strip() for p in parts if p.strip()]

    def init_schema(self, create_database: bool = True) -> Dict[str, Any]:
        """
        初始化 Release 存储：建库（可选）+ 建表。

        @param create_database: True 时先 CREATE DATABASE IF NOT EXISTS
        @returns: 各步骤执行摘要
        """
        steps: Dict[str, Any] = {}
        if create_database:
            steps["create_database"] = self.ensure_database()
            if not steps["create_database"].get("ok"):
                return {"ok": False, "steps": steps}

        steps["init_schema"] = self.execute_sql_file(MYSQL_SCHEMA_FILE)
        return {
            "ok": steps["init_schema"].get("ok", False),
            "steps": steps,
        }

    def seed_demo(self) -> Dict[str, Any]:
        """
        导入演示种子数据（执行 mysql_seed_demo.sql）。

        @returns: execute_sql_file 摘要
        """
        return self.execute_sql_file(MYSQL_SEED_DEMO_FILE)

    def count_rows(self) -> Dict[str, int]:
        """
        统计各业务表行数。

        @returns: 表名 → 行数
        """
        tables = [
            "release_groups",
            "media_catalog",
            "media_pages",
            "download_resources",
            "slot_speed_summary",
        ]
        conn = self._connect()
        counts: Dict[str, int] = {}
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"SELECT COUNT(*) AS c FROM `{table}`")
                row = cur.fetchone()
                counts[table] = int(row["c"]) if row else 0
        conn.close()
        return counts

    def get_episode_page_context(self, page_id: str) -> Optional[EpisodePageContext]:
        """
        加载单集页完整上下文（供生成器 / query CLI）。

        @param page_id: 如 tv:1396:s04e06
        @returns: EpisodePageContext 或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM media_pages WHERE page_id = %s AND page_type = 'episode'",
                (page_id,),
            )
            raw_page = cur.fetchone()
            if not raw_page:
                conn.close()
                return None
            page_row = _normalize_row(raw_page)
            cur.execute(
                "SELECT * FROM media_catalog WHERE catalog_id = %s",
                (page_row["catalog_id"],),
            )
            catalog_row = _normalize_row(cur.fetchone())

            cur.execute(
                """
                SELECT * FROM download_resources
                WHERE page_id = %s
                ORDER BY is_recommended DESC, match_score DESC
                """,
                (page_id,),
            )
            source_rows = [_normalize_row(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT * FROM slot_speed_summary WHERE page_id = %s",
                (page_id,),
            )
            speed_row = cur.fetchone()
        conn.close()

        catalog = MediaCatalog.from_row(catalog_row)
        page = MediaPage.from_row(page_row)
        sources = [DownloadResource.from_row(r) for r in source_rows]
        recommended = next((s for s in sources if s.is_recommended), None)
        speed = SlotSpeedSummary.from_row(_normalize_row(speed_row)) if speed_row else None

        speed_evidence = self._build_speed_evidence_context(
            page_id, speed, recommended
        )
        torrent_metadata = self._build_torrent_metadata_context(recommended)

        return EpisodePageContext(
            catalog=catalog,
            page=page,
            sources=sources,
            recommended=recommended,
            speed_summary=speed,
            speed_evidence=speed_evidence,
            torrent_metadata=torrent_metadata,
            canonical_url=(SITE_ORIGIN.rstrip("/") + page.canonical_path),
        )

    def _load_page_bundle(
        self, page_id: str
    ) -> Optional[tuple[MediaPage, MediaCatalog, List[DownloadResource], Optional[SlotSpeedSummary]]]:
        """
        加载槽位通用数据包：page + catalog + resources + speed。

        @param page_id: 页面主键
        @returns: 四元组或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM media_pages WHERE page_id = %s", (page_id,))
            raw_page = cur.fetchone()
            if not raw_page:
                conn.close()
                return None
            page_row = _normalize_row(raw_page)
            cur.execute(
                "SELECT * FROM media_catalog WHERE catalog_id = %s",
                (page_row["catalog_id"],),
            )
            catalog_row = _normalize_row(cur.fetchone())
            cur.execute(
                """
                SELECT * FROM download_resources
                WHERE page_id = %s
                ORDER BY is_recommended DESC, match_score DESC
                """,
                (page_id,),
            )
            source_rows = [_normalize_row(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT * FROM slot_speed_summary WHERE page_id = %s",
                (page_id,),
            )
            speed_row = cur.fetchone()
        conn.close()

        page = MediaPage.from_row(page_row)
        catalog = MediaCatalog.from_row(catalog_row)
        sources = [DownloadResource.from_row(r) for r in source_rows]
        speed = SlotSpeedSummary.from_row(_normalize_row(speed_row)) if speed_row else None
        return page, catalog, sources, speed

    def _build_speed_evidence_context(
        self,
        page_id: str,
        speed: Optional[SlotSpeedSummary],
        recommended: Optional[DownloadResource],
    ) -> Optional[SpeedEvidenceContext]:
        """
        由 slot_speed_summary + Phase1/2 明细组装测速 IG 证据上下文。

        @param page_id: 页面主键
        @param speed: 槽位测速摘要
        @param recommended: Recommended release（取 infohash / seeders）
        @returns: SpeedEvidenceContext 或 None
        """
        if not speed:
            return None
        infohash = speed.recommended_infohash or (
            recommended.infohash if recommended else ""
        )
        phase1 = self.get_latest_speedtest_result(
            page_id, phase=1, infohash=infohash or None
        )
        phase2 = self.get_latest_speedtest_result(
            page_id, phase=2, infohash=infohash or None
        )
        if not is_speed_evidence_publishable(speed, phase1, phase2):
            return None
        return SpeedEvidenceContext.from_parts(
            speed,
            phase1,
            phase2,
            indexed_seeders=recommended.seeders if recommended else 0,
        )

    def _build_torrent_metadata_context(
        self,
        recommended: Optional[DownloadResource],
    ) -> Optional[TorrentMetadataContext]:
        """
        加载 Recommended infohash 的 torrent 结构 metadata（测速提取）。

        @param recommended: Recommended release
        @returns: TorrentMetadataContext 或 None
        """
        if not recommended or not (recommended.infohash or "").strip():
            return None
        record = self.get_torrent_metadata(recommended.infohash)
        if not record:
            return None
        ctx = TorrentMetadataContext.from_record(record)
        if not ctx.is_publishable():
            return None
        return ctx

    def get_torrent_metadata(self, infohash: str) -> Optional[TorrentMetadataRecord]:
        """
        按 infohash 读取 torrent_metadata 行。

        @param infohash: 40 位 infohash
        @returns: TorrentMetadataRecord 或 None
        """
        ih = (infohash or "").lower().strip()
        if len(ih) != 40:
            return None
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM torrent_metadata WHERE infohash = %s",
                (ih,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return TorrentMetadataRecord.from_row(_normalize_row(row))

    def upsert_torrent_metadata(
        self,
        meta: Any,
        *,
        page_id: Optional[str] = None,
    ) -> None:
        """
        写入或更新 torrent_metadata（Phase 2 测速提取）。

        @param meta: TorrentMetadataResult 或等价 dict
        @param page_id: 关联页面 ID
        @returns: None
        """
        from workflow.torrent_sources.speedtest.torrent_metadata import TorrentMetadataResult

        if isinstance(meta, TorrentMetadataResult):
            row = meta
        else:
            row = TorrentMetadataResult(**meta)

        now = _utc_now_str()
        slot_page_id = page_id or row.page_id
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO torrent_metadata (
                    infohash, page_id, torrent_name, total_size_bytes,
                    file_count, piece_length, is_private,
                    primary_file, primary_file_size_bytes, files_json,
                    indexer_size_bytes, size_match, size_delta_bytes,
                    status, extracted_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    page_id=VALUES(page_id),
                    torrent_name=VALUES(torrent_name),
                    total_size_bytes=VALUES(total_size_bytes),
                    file_count=VALUES(file_count),
                    piece_length=VALUES(piece_length),
                    is_private=VALUES(is_private),
                    primary_file=VALUES(primary_file),
                    primary_file_size_bytes=VALUES(primary_file_size_bytes),
                    files_json=VALUES(files_json),
                    indexer_size_bytes=VALUES(indexer_size_bytes),
                    size_match=VALUES(size_match),
                    size_delta_bytes=VALUES(size_delta_bytes),
                    status=VALUES(status),
                    extracted_at=VALUES(extracted_at)
                """,
                (
                    row.infohash.lower(),
                    slot_page_id,
                    _clip_str(row.torrent_name, 1024),
                    int(row.total_size_bytes),
                    int(row.file_count),
                    int(row.piece_length),
                    1 if row.is_private else 0,
                    _clip_str(row.primary_file, 1024),
                    int(row.primary_file_size_bytes),
                    row.files_json(),
                    int(row.indexer_size_bytes),
                    _clip_str(row.size_match, 16),
                    int(row.size_delta_bytes),
                    _clip_str(row.status, 16),
                    now,
                ),
            )
        conn.close()

    def get_movie_page_context(self, page_id: str) -> Optional[MoviePageContext]:
        """
        加载电影页完整上下文。

        @param page_id: 如 movie:27205
        @returns: MoviePageContext 或 None
        """
        bundle = self._load_page_bundle(page_id)
        if not bundle:
            return None
        page, catalog, sources, speed = bundle
        if page.page_type != "movie":
            return None
        recommended = next((s for s in sources if s.is_recommended), None)
        speed_evidence = self._build_speed_evidence_context(
            page_id, speed, recommended
        )
        torrent_metadata = self._build_torrent_metadata_context(recommended)
        return MoviePageContext(
            catalog=catalog,
            page=page,
            sources=sources,
            recommended=recommended,
            speed_summary=speed,
            speed_evidence=speed_evidence,
            torrent_metadata=torrent_metadata,
            canonical_url=(SITE_ORIGIN.rstrip("/") + page.canonical_path),
        )

    def get_show_hub_page_context(
        self,
        page_id: str,
        active_season: Optional[int] = None,
        active_episode: Optional[int] = None,
    ) -> Optional[ShowHubPageContext]:
        """
        加载剧集 Hub 页上下文（含季集芯片）。

        @param page_id: 如 tv:1396:hub
        @param active_season: 高亮季号
        @param active_episode: 高亮集号
        @returns: ShowHubPageContext 或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM media_pages WHERE page_id = %s AND page_type = 'show_hub'",
                (page_id,),
            )
            raw_hub = cur.fetchone()
            if not raw_hub:
                conn.close()
                return None
            hub_row = _normalize_row(raw_hub)
            cur.execute(
                "SELECT * FROM media_catalog WHERE catalog_id = %s",
                (hub_row["catalog_id"],),
            )
            catalog_row = _normalize_row(cur.fetchone())
            cur.execute(
                """
                SELECT season, episode FROM media_pages
                WHERE catalog_id = %s AND page_type = 'episode'
                ORDER BY season ASC, episode ASC
                """,
                (hub_row["catalog_id"],),
            )
            ep_rows = cur.fetchall()
        conn.close()

        seasons_map: Dict[int, List[Dict[str, int]]] = {}
        for row in ep_rows:
            s = int(row["season"])
            e = int(row["episode"])
            seasons_map.setdefault(s, []).append({"number": e})

        seasons = [
            {"number": s, "episodes": seasons_map[s]}
            for s in sorted(seasons_map.keys())
        ]
        page = MediaPage.from_row(hub_row)
        catalog = MediaCatalog.from_row(catalog_row)
        return ShowHubPageContext(
            catalog=catalog,
            page=page,
            seasons=seasons,
            active_season=active_season,
            active_episode=active_episode,
            canonical_url=(SITE_ORIGIN.rstrip("/") + page.canonical_path),
        )

    def get_catalog_by_slug(self, slug: str) -> Optional[MediaCatalog]:
        """
        按 URL slug 查询作品主数据。

        @param slug: 如 breaking-bad
        @returns: MediaCatalog 或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM media_catalog WHERE slug = %s LIMIT 1", (slug,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return MediaCatalog.from_row(_normalize_row(row))

    def list_published_page_ids(self) -> List[str]:
        """
        列出可生成静态页的 page_id（published 且 magnet≥2）。

        @returns: page_id 列表
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id FROM media_pages
                WHERE page_status = 'published' AND magnet_count >= 2
                ORDER BY catalog_id, page_type, season, episode
                """
            )
            rows = cur.fetchall()
        conn.close()
        return [str(r["page_id"]) for r in rows]

    def list_renderable_page_ids(self) -> List[str]:
        """
        列出应写入 portal/dist 的 episode/movie page_id。

        - published 且 magnet≥2：index,follow（进 sitemap）
        - thin（magnet<2 且已 pipeline）：仍生成 HTML，meta robots 为 noindex,follow（Hub 内链 UX）

        @returns: page_id 列表
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id FROM media_pages
                WHERE page_type IN ('episode', 'movie')
                  AND (
                    (page_status = 'published' AND magnet_count >= 2)
                    OR page_status = 'thin'
                  )
                ORDER BY catalog_id, page_type, season, episode
                """
            )
            rows = cur.fetchall()
        conn.close()
        return [str(r["page_id"]) for r in rows]

    def list_sitemap_content_pages(self) -> List[Dict[str, Any]]:
        """
        列出可纳入 sitemap 的内容页（indexable + 有 Recommended）。

        @returns: 含 page_id、canonical_path、updated_at 的字典列表
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.page_id, p.canonical_path, p.updated_at, p.magnet_count,
                       p.robots_noindex, p.page_type
                FROM media_pages p
                WHERE p.page_status = 'published'
                  AND p.page_type IN ('episode', 'movie')
                  AND p.magnet_count >= 2
                  AND (p.robots_noindex IS NULL OR p.robots_noindex = 0)
                  AND EXISTS (
                    SELECT 1 FROM download_resources d
                    WHERE d.page_id = p.page_id AND d.is_recommended = 1
                  )
                ORDER BY p.catalog_id, p.season, p.episode
                """
            )
            rows = cur.fetchall()
        conn.close()
        return [_normalize_row(r) for r in rows]

    def list_show_hub_page_ids(self) -> List[str]:
        """
        列出所有 show_hub 页面 ID（供 generate all 生成 Hub 静态页）。

        @returns: page_id 列表
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id FROM media_pages
                WHERE page_type = 'show_hub'
                ORDER BY catalog_id
                """
            )
            rows = cur.fetchall()
        conn.close()
        return [str(r["page_id"]) for r in rows]

    def list_home_catalog_entries(self) -> List[Dict[str, Any]]:
        """
        聚合 published 页面为首页目录卡片（按作品 catalog 分组）。

        @returns: 含 title、href、meta、poster_url、media_kind 的列表
        """
        from schema.d1_models import poster_url_from_path

        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.page_id, p.page_type, p.canonical_path, p.season, p.episode,
                       c.catalog_id, c.slug, c.title, c.media_kind, c.year, c.poster_path
                FROM media_pages p
                JOIN media_catalog c ON p.catalog_id = c.catalog_id
                WHERE p.page_status = 'published' AND p.magnet_count >= 2
                  AND p.page_type IN ('episode', 'movie')
                ORDER BY c.title, p.season, p.episode
                """
            )
            rows = cur.fetchall()
            cur.execute(
                """
                SELECT catalog_id, canonical_path FROM media_pages
                WHERE page_type = 'show_hub'
                """
            )
            hub_rows = cur.fetchall()
        conn.close()

        hub_by_catalog = {str(r["catalog_id"]): str(r["canonical_path"]) for r in hub_rows}
        grouped: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            catalog_id = str(row["catalog_id"])
            media_kind = str(row["media_kind"])
            if catalog_id not in grouped:
                grouped[catalog_id] = {
                    "catalog_id": catalog_id,
                    "title": str(row["title"] or ""),
                    "slug": str(row["slug"] or ""),
                    "media_kind": media_kind,
                    "year": row.get("year"),
                    "poster_url": poster_url_from_path(str(row.get("poster_path") or "")),
                    "pages": [],
                }
            grouped[catalog_id]["pages"].append(
                {
                    "page_id": str(row["page_id"]),
                    "canonical_path": str(row["canonical_path"]),
                    "season": row.get("season"),
                    "episode": row.get("episode"),
                }
            )

        entries: List[Dict[str, Any]] = []
        for item in sorted(grouped.values(), key=lambda x: x["title"].lower()):
            pages = item["pages"]
            media_kind = item["media_kind"]
            hub_path = hub_by_catalog.get(item["catalog_id"])

            if media_kind == "movie":
                href = pages[0]["canonical_path"]
                year = item.get("year")
                meta = f"电影 · {year}" if year else "电影"
            elif hub_path and len(pages) > 1:
                href = hub_path
                meta = f"剧集 · {len(pages)} 集"
            elif len(pages) == 1:
                pg = pages[0]
                href = pg["canonical_path"]
                season = int(pg["season"] or 1)
                episode = int(pg["episode"] or 1)
                meta = f"剧集 · S{season:02d}E{episode:02d}"
            else:
                href = pages[0]["canonical_path"]
                meta = f"剧集 · {len(pages)} 集"

            entries.append(
                {
                    "title": item["title"],
                    "href": href,
                    "meta": meta,
                    "poster_url": item["poster_url"],
                    "media_kind": media_kind,
                    "page_count": len(pages),
                }
            )
        return entries

    def resolve_url_path(self, url_path: str) -> Optional[Dict[str, Any]]:
        """
        将 URL 路径解析为页面类型与 page_id。

        @param url_path: 如 /breaking-bad/s4e6/ 或 /inception-2010/
        @returns: 含 page_type、page_id、season、episode 的字典
        """
        path = url_path.split("?", 1)[0].strip()
        if not path.startswith("/"):
            path = f"/{path}"
        path = path.rstrip("/") or "/"
        if path == "/":
            return None

        ep_match = re.match(r"^/([^/]+)/s(\d+)e(\d+)$", path, re.IGNORECASE)
        if ep_match:
            slug, season_s, episode_s = ep_match.groups()
            catalog = self.get_catalog_by_slug(slug)
            if not catalog or catalog.media_kind != "tv":
                return None
            season, episode = int(season_s), int(episode_s)
            page_id = build_page_id(catalog.tmdb_id, "tv", season=season, episode=episode)
            return {
                "page_type": "episode",
                "page_id": page_id,
                "slug": slug,
                "season": season,
                "episode": episode,
            }

        slug_match = re.match(r"^/([^/]+)$", path)
        if not slug_match:
            return None
        slug = slug_match.group(1)
        catalog = self.get_catalog_by_slug(slug)
        if not catalog:
            return None
        if catalog.media_kind == "movie":
            return {
                "page_type": "movie",
                "page_id": build_page_id(catalog.tmdb_id, "movie", page_type="movie"),
                "slug": slug,
            }
        return {
            "page_type": "show_hub",
            "page_id": build_page_id(catalog.tmdb_id, "tv", page_type="show_hub"),
            "slug": slug,
        }

    def load_page_for_url(self, url_path: str) -> Optional[Dict[str, Any]]:
        """
        按 URL 路径加载任意页面上下文（episode / movie / show_hub）。

        @param url_path: HTTP 路径
        @returns: 含 template、context 对象的字典
        """
        resolved = self.resolve_url_path(url_path)
        if not resolved:
            return None

        page_type = resolved["page_type"]
        page_id = resolved["page_id"]

        if page_type == "episode":
            ctx = self.get_episode_page_context(page_id)
            if not ctx:
                return None
            return {"template": "episode.html", "context": ctx, "page_id": page_id}

        if page_type == "movie":
            ctx = self.get_movie_page_context(page_id)
            if not ctx:
                return None
            return {"template": "movie.html", "context": ctx, "page_id": page_id}

        ctx = self.get_show_hub_page_context(page_id)
        if not ctx:
            return None
        return {"template": "show_hub.html", "context": ctx, "page_id": page_id}

    def upsert_slot_resources(
        self,
        page_id: str,
        tmdb_id: int,
        media_type: str,
        season: Optional[int],
        episode: Optional[int],
        items: List[Dict[str, Any]],
        ranked: List[Any],
        expires_hours: int = 168,
        cross_source_page_count: Optional[int] = None,
        cross_source_page_total: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        将 scorer 输出写入 download_resources，并更新 media_pages。

        @param page_id: 页面槽位 ID
        @param tmdb_id: TMDB ID
        @param media_type: tv_episode | movie
        @param season: 季号
        @param episode: 集号
        @param items: ResourceItem 字典列表（含 cross_source_count/confidence）
        @param ranked: scorer.rank_items 返回的 Order 列表
        @param expires_hours: magnet TTL 小时数
        @param cross_source_page_count: Hero badge 分子；缺省从 items 推断
        @param cross_source_page_total: Hero badge 分母；缺省按媒体类型默认
        @returns: 写入摘要
        """
        from workflow.torrent_sources.cross_source import compute_page_cross_source

        media_kind = "movie" if media_type == "movie" else "tv"
        if cross_source_page_count is None or cross_source_page_total is None:
            inferred_count, inferred_total = compute_page_cross_source(
                items,
                media_type=media_kind,
            )
            if cross_source_page_count is None:
                cross_source_page_count = inferred_count
            if cross_source_page_total is None:
                cross_source_page_total = inferred_total
        now = _utc_now_str()
        expires = datetime.now(timezone.utc)
        from datetime import timedelta

        expires_str = (expires + timedelta(hours=expires_hours)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        order_by_hash = {o.infohash: o for o in ranked}
        conn = self._connect()
        upserted = 0
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE download_resources SET is_recommended = 0 WHERE page_id = %s",
                (page_id,),
            )
            for item in items:
                infohash = str(item.get("infohash") or "")
                if not infohash:
                    continue
                order = order_by_hash.get(infohash)
                is_rec = 1 if order and order.is_recommended else 0
                reason = order.recommend_reason if order else ""
                score = order.score if order else 0.0
                tier = order.group_tier if order else "L4"
                cur.execute(
                    """
                    INSERT INTO download_resources (
                        id, page_id, tmdb_id, media_type, season, episode, infohash,
                        title_raw, release_group, source, resolution, codec,
                        video_spec, audio_spec, size_bytes, seeders, peers, magnet_uri, indexer,
                        is_recommended, match_score, recommend_reason, group_tier,
                        cross_source_count, cross_source_confidence, indexed_at, expires_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        title_raw=VALUES(title_raw),
                        release_group=VALUES(release_group),
                        source=VALUES(source),
                        resolution=VALUES(resolution),
                        codec=VALUES(codec),
                        video_spec=VALUES(video_spec),
                        audio_spec=VALUES(audio_spec),
                        seeders=VALUES(seeders),
                        peers=VALUES(peers),
                        magnet_uri=VALUES(magnet_uri),
                        is_recommended=VALUES(is_recommended),
                        match_score=VALUES(match_score),
                        recommend_reason=VALUES(recommend_reason),
                        group_tier=VALUES(group_tier),
                        cross_source_count=VALUES(cross_source_count),
                        cross_source_confidence=VALUES(cross_source_confidence),
                        indexed_at=VALUES(indexed_at),
                        expires_at=VALUES(expires_at)
                    """,
                    (
                        infohash,
                        page_id,
                        tmdb_id,
                        media_type,
                        season,
                        episode,
                        infohash,
                        item.get("title_raw", ""),
                        _clip_str(item.get("release_group", ""), 64),
                        _clip_str(item.get("source", ""), 64),
                        _clip_str(item.get("resolution", ""), 16),
                        _clip_str(item.get("codec", ""), 32),
                        _clip_str(item.get("video_spec", ""), 256),
                        _clip_str(item.get("audio_spec", ""), 256),
                        int(item.get("size_bytes") or 0),
                        int(item.get("seeders") or 0),
                        int(item.get("peers") or 0),
                        item.get("magnet_uri", ""),
                        _clip_str(item.get("indexer", ""), 32),
                        is_rec,
                        score,
                        _clip_str(reason, 512),
                        tier,
                        int(item.get("cross_source_count") or 1),
                        float(item.get("cross_source_confidence") or 0.0),
                        now,
                        expires_str,
                    ),
                )
                upserted += 1

            # 移除本槽位已不在当前拉取结果中的旧 magnet（避免页面仍显示历史误匹配条目）
            active_hashes = [
                str(item.get("infohash") or "")
                for item in items
                if len(str(item.get("infohash") or "")) == 40
            ]
            if active_hashes:
                placeholders = ", ".join(["%s"] * len(active_hashes))
                cur.execute(
                    f"DELETE FROM download_resources WHERE page_id = %s "
                    f"AND infohash NOT IN ({placeholders})",
                    [page_id, *active_hashes],
                )
            else:
                cur.execute(
                    "DELETE FROM download_resources WHERE page_id = %s",
                    (page_id,),
                )

            magnet_count = len(active_hashes)
            page_status = "published" if magnet_count >= 2 else "thin"
            has_rec = any(o.is_recommended for o in ranked) if ranked else False
            robots_noindex = 0 if (magnet_count >= 2 and has_rec) else 1
            cur.execute(
                """
                UPDATE media_pages
                SET magnet_count = %s,
                    cross_source_count = %s,
                    cross_source_total = %s,
                    page_status = %s,
                    robots_noindex = %s,
                    updated_at = %s
                WHERE page_id = %s
                """,
                (
                    magnet_count,
                    int(cross_source_page_count),
                    int(cross_source_page_total),
                    page_status,
                    robots_noindex,
                    now,
                    page_id,
                ),
            )
        conn.close()
        return {
            "page_id": page_id,
            "resources_upserted": upserted,
            "magnet_count": magnet_count,
            "page_status": page_status,
            "cross_source_count": int(cross_source_page_count),
            "cross_source_total": int(cross_source_page_total),
        }

    def record_sync_run(
        self,
        run_id: str,
        source: str,
        slots_processed: int = 0,
        resources_upserted: int = 0,
        pages_published: int = 0,
        error_message: str = "",
        finished: bool = True,
    ) -> None:
        """
        写入 sync_runs 审计记录。

        @param run_id: 批次 ID
        @param source: batch | on_demand | pipeline 等
        @param slots_processed: 处理槽位数
        @param resources_upserted: 写入 resource 数
        @param pages_published: 发布页数
        @param error_message: 错误信息
        @param finished: 是否已完成
        @returns: None
        """
        now = _utc_now_str()
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_runs (
                    run_id, source, slots_processed, resources_upserted,
                    pages_published, error_message, started_at, finished_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    slots_processed=VALUES(slots_processed),
                    resources_upserted=VALUES(resources_upserted),
                    pages_published=VALUES(pages_published),
                    error_message=VALUES(error_message),
                    finished_at=VALUES(finished_at)
                """,
                (
                    run_id,
                    source,
                    slots_processed,
                    resources_upserted,
                    pages_published,
                    error_message,
                    now,
                    now if finished else None,
                ),
            )
        conn.close()

    def get_recommended_resource(self, page_id: str) -> Optional[DownloadResource]:
        """
        读取槽位 Recommended release（is_recommended=1）。

        @param page_id: 页面槽位 ID
        @returns: DownloadResource 或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM download_resources
                WHERE page_id = %s AND is_recommended = 1
                ORDER BY match_score DESC
                LIMIT 1
                """,
                (page_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return DownloadResource.from_row(_normalize_row(row))

    def get_slot_speed_summary(self, page_id: str) -> Optional[SlotSpeedSummary]:
        """
        读取槽位测速摘要行。

        @param page_id: 页面主键
        @returns: SlotSpeedSummary 或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM slot_speed_summary WHERE page_id = %s",
                (page_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return SlotSpeedSummary.from_row(_normalize_row(row))

    def get_latest_speedtest_result(
        self,
        page_id: str,
        *,
        phase: int,
        infohash: Optional[str] = None,
    ) -> Optional[SpeedTestResult]:
        """
        读取某 page_id 最近一条测速明细（按 tested_at 降序）。

        @param page_id: 页面槽位 ID
        @param phase: 1=连接性 2=片段测速
        @param infohash: 可选；限定 Recommended infohash
        @returns: SpeedTestResult 或 None
        """
        conn = self._connect()
        with conn.cursor() as cur:
            if infohash:
                cur.execute(
                    """
                    SELECT * FROM speedtest_results
                    WHERE page_id = %s AND phase = %s AND infohash = %s
                    ORDER BY tested_at DESC
                    LIMIT 1
                    """,
                    (page_id, int(phase), infohash.lower()),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM speedtest_results
                    WHERE page_id = %s AND phase = %s
                    ORDER BY tested_at DESC
                    LIMIT 1
                    """,
                    (page_id, int(phase)),
                )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return SpeedTestResult.from_row(_normalize_row(row))

    def insert_speedtest_result(
        self,
        *,
        result_id: str,
        infohash: str,
        page_id: Optional[str],
        phase: int,
        peers_reachable: int = 0,
        peers_total: int = 0,
        avg_kbps: float = 0.0,
        max_kbps: float = 0.0,
        latency_ms: int = 0,
        status: str = "ok",
        tested_at: Optional[str] = None,
    ) -> None:
        """
        写入单条 speedtest_results 明细。

        @param result_id: 主键 UUID
        @param infohash: magnet infohash
        @param page_id: 关联页面；可为 None
        @param phase: 1=连接性 2=片段测速
        @param peers_reachable: 已连接 peer 数
        @param peers_total: 观测 peer 总数
        @param avg_kbps: 平均 KiB/s（Phase 2）
        @param max_kbps: 峰值 KiB/s（Phase 2）
        @param latency_ms: 首包延迟毫秒（Phase 2）
        @param status: ok | timeout | error | dry_run | skipped
        @param tested_at: 测试时间；缺省为当前 UTC
        @returns: None
        """
        now = tested_at or _utc_now_str()
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO speedtest_results (
                    id, infohash, page_id, phase,
                    peers_reachable, peers_total,
                    avg_kbps, max_kbps, latency_ms,
                    status, tested_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    peers_reachable=VALUES(peers_reachable),
                    peers_total=VALUES(peers_total),
                    avg_kbps=VALUES(avg_kbps),
                    max_kbps=VALUES(max_kbps),
                    latency_ms=VALUES(latency_ms),
                    status=VALUES(status),
                    tested_at=VALUES(tested_at)
                """,
                (
                    result_id,
                    infohash,
                    page_id,
                    int(phase),
                    int(peers_reachable),
                    int(peers_total),
                    float(avg_kbps),
                    float(max_kbps),
                    int(latency_ms),
                    _clip_str(status, 16),
                    now,
                ),
            )
        conn.close()

    def upsert_slot_speed_summary(
        self,
        page_id: str,
        recommended_infohash: str,
        recommended_speed: str,
        reachability: str,
    ) -> None:
        """
        写入或更新槽位测速摘要（S-06 / S-07）。

        @param page_id: 页面槽位 ID
        @param recommended_infohash: Recommended infohash
        @param recommended_speed: 展示速度文案，如 4.2 MB/s
        @param reachability: 高 | 中 | 低 | 不可达
        @returns: None
        """
        now = _utc_now_str()
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO slot_speed_summary (
                    page_id, recommended_infohash, recommended_speed,
                    reachability, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    recommended_infohash=VALUES(recommended_infohash),
                    recommended_speed=VALUES(recommended_speed),
                    reachability=VALUES(reachability),
                    updated_at=VALUES(updated_at)
                """,
                (
                    page_id,
                    recommended_infohash,
                    _clip_str(recommended_speed, 32),
                    _clip_str(reachability, 16),
                    now,
                ),
            )
        conn.close()

    def resolve_page_id(
        self,
        tmdb_id: int,
        media_kind: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
    ) -> str:
        """
        根据 TMDB 槽位参数解析 page_id。

        @param tmdb_id: TMDB ID
        @param media_kind: tv | movie
        @param season: 季号
        @param episode: 集号
        @returns: page_id 字符串
        """
        if media_kind == "movie":
            return build_page_id(tmdb_id, "movie", page_type="movie")
        return build_page_id(tmdb_id, "tv", season=season, episode=episode)

    def ensure_show_hub_page(
        self,
        tmdb_id: int,
        *,
        title: Optional[str] = None,
        slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        确保剧集 Hub 行 ``tv:{tmdb_id}:hub`` 存在（canonical ``/{slug}/``）。

        @param tmdb_id: TMDB 剧集 ID
        @param title: 可选标题（用于生成 slug）
        @param slug: 可选已解析 slug；缺省时从 catalog / slot 元数据推断
        @returns: hub_page_id、canonical_path、是否新建
        """
        from workflow.metadata.external_ids import resolve_external_ids
        from workflow.metadata.slot_catalog import (
            canonical_path_for_slot,
            get_slot_catalog_meta,
            slugify_title,
        )

        catalog_id = build_catalog_id(tmdb_id, "tv")
        hub_page_id = build_page_id(tmdb_id, "tv", page_type="show_hub")
        slot_meta = get_slot_catalog_meta(tmdb_id) or {}
        ext = resolve_external_ids(tmdb_id, "tv", title=title)
        resolved_title = slot_meta.get("title") or ext.get("title") or title or f"TMDB {tmdb_id}"
        resolved_slug = (
            slug
            or slot_meta.get("slug")
            or slugify_title(str(resolved_title), year=slot_meta.get("year"))
        )
        hub_canonical = canonical_path_for_slot(
            {"slug": resolved_slug, "media_kind": "tv"}
        )
        now = _utc_now_str()
        created = False
        conn = self._connect()
        with conn.cursor() as cur:
            # Hub 依赖 catalog；无则先占位
            cur.execute(
                "SELECT slug FROM media_catalog WHERE catalog_id = %s LIMIT 1",
                (catalog_id,),
            )
            cat_row = cur.fetchone()
            if cat_row and cat_row.get("slug"):
                hub_canonical = canonical_path_for_slot(
                    {"slug": cat_row["slug"], "media_kind": "tv"}
                )
            elif not cat_row:
                tmdb_url = f"https://www.themoviedb.org/tv/{tmdb_id}"
                cur.execute(
                    """
                    INSERT INTO media_catalog (
                        catalog_id, tmdb_id, media_kind, slug, title, overview, year,
                        runtime_minutes, poster_path, tmdb_url, streaming_providers,
                        subtitle_url_pattern, updated_at
                    ) VALUES (
                        %s, %s, 'tv', %s, %s, '', %s,
                        NULL, '', %s, '[]', '', %s
                    )
                    """,
                    (
                        catalog_id,
                        tmdb_id,
                        resolved_slug,
                        resolved_title,
                        slot_meta.get("year"),
                        tmdb_url,
                        now,
                    ),
                )
            cur.execute(
                "SELECT page_id FROM media_pages WHERE page_id = %s LIMIT 1",
                (hub_page_id,),
            )
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO media_pages (
                        page_id, catalog_id, page_type, season, episode, episode_title,
                        air_date, overview, cross_source_count, cross_source_total,
                        prev_season, prev_episode, next_season, next_episode,
                        magnet_count, page_status, robots_noindex, canonical_path,
                        subtitle_url, generated_at, updated_at
                    ) VALUES (
                        %s, %s, 'show_hub', NULL, NULL, '', NULL, '', 0, 3,
                        NULL, NULL, NULL, NULL, 0, 'published', 1, %s, '', NULL, %s
                    )
                    """,
                    (hub_page_id, catalog_id, hub_canonical, now),
                )
                created = True
        conn.close()

        # Hub 创建后补齐作品海报/简介（空则补）
        display_meta: Dict[str, Any] = {}
        try:
            display_meta = self.enrich_tmdb_display_meta(
                tmdb_id=tmdb_id,
                media_kind="tv",
                page_id=hub_page_id,
                force=False,
            )
        except Exception as exc:  # noqa: BLE001
            display_meta = {"ok": False, "error": str(exc)}

        return {
            "hub_page_id": hub_page_id,
            "canonical_path": hub_canonical,
            "created": created,
            "display_meta": display_meta,
        }

    def ensure_slot_page(
        self,
        tmdb_id: int,
        media_kind: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        确保 media_catalog / media_pages 占位行存在（扩槽 pipeline 前置）。

        @param tmdb_id: TMDB 作品 ID
        @param media_kind: tv | movie
        @param season: 季号（剧集）
        @param episode: 集号（剧集）
        @param title: 可选 slot 标题（无 catalog 元数据时生成 slug）
        @returns: catalog_id、page_id 及是否新建；剧集另含 hub 信息
        @description
          剧集会同步 ``ensure_show_hub_page``，避免只有 ``/sNeN/`` 而无 ``/{slug}/`` Hub。
        """
        from workflow.metadata.external_ids import resolve_external_ids
        from workflow.metadata.slot_catalog import (
            canonical_path_for_slot,
            get_slot_catalog_meta,
            slugify_title,
        )

        catalog_id = build_catalog_id(tmdb_id, media_kind)
        page_id = self.resolve_page_id(tmdb_id, media_kind, season, episode)
        slot_meta = get_slot_catalog_meta(tmdb_id) or {}
        ext = resolve_external_ids(tmdb_id, media_kind, title=title)
        resolved_title = slot_meta.get("title") or ext.get("title") or title or f"TMDB {tmdb_id}"
        slug = slot_meta.get("slug") or slugify_title(
            str(resolved_title), year=slot_meta.get("year")
        )
        year = slot_meta.get("year")
        tmdb_path = "movie" if media_kind == "movie" else "tv"
        tmdb_url = f"https://www.themoviedb.org/{tmdb_path}/{tmdb_id}"
        path_meta = {"slug": slug, "media_kind": media_kind}
        if media_kind == "movie":
            canonical = canonical_path_for_slot(path_meta)
            page_type = "movie"
        else:
            canonical = canonical_path_for_slot(path_meta, season=season, episode=episode)
            page_type = "episode"

        now = _utc_now_str()
        conn = self._connect()
        created_catalog = False
        created_page = False
        year = slot_meta.get("year")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT catalog_id FROM media_catalog WHERE catalog_id = %s LIMIT 1",
                (catalog_id,),
            )
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO media_catalog (
                        catalog_id, tmdb_id, media_kind, slug, title, overview, year,
                        runtime_minutes, poster_path, tmdb_url, streaming_providers,
                        subtitle_url_pattern, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        NULL, '', %s, '[]', '', %s
                    )
                    """,
                    (
                        catalog_id,
                        tmdb_id,
                        media_kind,
                        slug,
                        resolved_title,
                        "",
                        year,
                        tmdb_url,
                        now,
                    ),
                )
                created_catalog = True

            cur.execute(
                "SELECT page_id FROM media_pages WHERE page_id = %s LIMIT 1",
                (page_id,),
            )
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO media_pages (
                        page_id, catalog_id, page_type, season, episode, episode_title,
                        air_date, overview, cross_source_count, cross_source_total,
                        prev_season, prev_episode, next_season, next_episode,
                        magnet_count, page_status, robots_noindex, canonical_path,
                        subtitle_url, generated_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, '', NULL, '', 0, 3,
                        NULL, NULL, NULL, NULL, 0, 'draft', 1, %s, '', NULL, %s
                    )
                    """,
                    (page_id, catalog_id, page_type, season, episode, canonical, now),
                )
                created_page = True
        conn.close()

        hub_info: Dict[str, Any] = {}
        if media_kind == "tv":
            hub_info = self.ensure_show_hub_page(
                tmdb_id, title=resolved_title, slug=slug
            )

        # 首次建槽：空则补 TMDB 海报/简介（缺 Key 不阻断）
        display_meta: Dict[str, Any] = {}
        try:
            display_meta = self.enrich_tmdb_display_meta(
                tmdb_id=tmdb_id,
                media_kind=media_kind,
                season=season,
                episode=episode,
                page_id=page_id,
                force=False,
            )
        except Exception as exc:  # noqa: BLE001 — 展示元数据失败不阻断建槽
            display_meta = {"ok": False, "error": str(exc)}

        return {
            "catalog_id": catalog_id,
            "page_id": page_id,
            "created_catalog": created_catalog,
            "created_page": created_page,
            "hub": hub_info,
            "display_meta": display_meta,
        }

    def ensure_overview_zh_columns(self) -> Dict[str, Any]:
        """
        幂等补齐 ``overview_zh`` 列（旧库迁移）。

        @returns: 是否已应用变更的摘要
        """
        added: List[str] = []
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for table in ("media_catalog", "media_pages"):
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s AND COLUMN_NAME = 'overview_zh'
                        """,
                        (table,),
                    )
                    row = cur.fetchone() or {}
                    if int(row.get("n") or 0) > 0:
                        continue
                    cur.execute(
                        f"ALTER TABLE `{table}` "
                        "ADD COLUMN overview_zh TEXT NULL "
                        "COMMENT '简介（zh-CN）' AFTER overview"
                    )
                    added.append(table)
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "added": added}

    def upsert_catalog_display_meta(
        self,
        catalog_id: str,
        *,
        poster_path: str = "",
        overview_en: str = "",
        overview_zh: str = "",
        title: Optional[str] = None,
        year: Optional[int] = None,
        runtime_minutes: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        补齐作品级海报/简介（默认仅写空字段）。

        @param catalog_id: media_catalog 主键
        @param poster_path: TMDB poster_path
        @param overview_en: 英文简介
        @param overview_zh: 中文简介
        @param title: 可选标题（仅空时写）
        @param year: 可选年份
        @param runtime_minutes: 可选片长
        @param force: True 时覆盖已有非空字段
        @returns: 更新字段列表
        """
        self.ensure_overview_zh_columns()
        conn = self._connect()
        updated: List[str] = []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT poster_path, overview, overview_zh, title, year, runtime_minutes
                    FROM media_catalog WHERE catalog_id = %s LIMIT 1
                    """,
                    (catalog_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"ok": False, "error": "catalog_not_found", "updated": []}

                sets: List[str] = []
                vals: List[Any] = []

                def _need(cur_val: Any, new_val: Any) -> bool:
                    """判断是否应写入新值。"""
                    if new_val in (None, ""):
                        return False
                    if force:
                        return True
                    return cur_val in (None, "")

                if _need(row.get("poster_path"), poster_path):
                    sets.append("poster_path = %s")
                    vals.append(poster_path)
                    updated.append("poster_path")
                if _need(row.get("overview"), overview_en):
                    sets.append("overview = %s")
                    vals.append(overview_en)
                    updated.append("overview")
                if _need(row.get("overview_zh"), overview_zh):
                    sets.append("overview_zh = %s")
                    vals.append(overview_zh)
                    updated.append("overview_zh")
                if title and _need(row.get("title"), title):
                    # 占位标题 TMDB {id} 时允许用真实标题替换
                    cur_title = str(row.get("title") or "")
                    if force or cur_title.startswith("TMDB ") or not cur_title:
                        sets.append("title = %s")
                        vals.append(title)
                        updated.append("title")
                if year is not None and _need(row.get("year"), year):
                    sets.append("year = %s")
                    vals.append(year)
                    updated.append("year")
                if runtime_minutes is not None and _need(
                    row.get("runtime_minutes"), runtime_minutes
                ):
                    sets.append("runtime_minutes = %s")
                    vals.append(runtime_minutes)
                    updated.append("runtime_minutes")

                if not sets:
                    return {"ok": True, "updated": [], "skipped": True}

                sets.append("updated_at = %s")
                vals.append(_utc_now_str())
                vals.append(catalog_id)
                cur.execute(
                    f"UPDATE media_catalog SET {', '.join(sets)} WHERE catalog_id = %s",
                    tuple(vals),
                )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "updated": updated}

    def upsert_page_display_meta(
        self,
        page_id: str,
        *,
        overview_en: str = "",
        overview_zh: str = "",
        episode_title: str = "",
        air_date: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        补齐槽位级简介/集标题（默认仅写空字段）。

        @param page_id: media_pages 主键
        @param overview_en: 英文简介
        @param overview_zh: 中文简介
        @param episode_title: 单集标题
        @param air_date: 播出日 YYYY-MM-DD
        @param force: True 时覆盖已有非空字段
        @returns: 更新字段列表
        """
        self.ensure_overview_zh_columns()
        conn = self._connect()
        updated: List[str] = []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT overview, overview_zh, episode_title, air_date
                    FROM media_pages WHERE page_id = %s LIMIT 1
                    """,
                    (page_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"ok": False, "error": "page_not_found", "updated": []}

                sets: List[str] = []
                vals: List[Any] = []

                def _need(cur_val: Any, new_val: Any) -> bool:
                    """判断是否应写入新值。"""
                    if new_val in (None, ""):
                        return False
                    if force:
                        return True
                    return cur_val in (None, "")

                if _need(row.get("overview"), overview_en):
                    sets.append("overview = %s")
                    vals.append(overview_en)
                    updated.append("overview")
                if _need(row.get("overview_zh"), overview_zh):
                    sets.append("overview_zh = %s")
                    vals.append(overview_zh)
                    updated.append("overview_zh")
                if _need(row.get("episode_title"), episode_title):
                    sets.append("episode_title = %s")
                    vals.append(episode_title)
                    updated.append("episode_title")
                if air_date and _need(row.get("air_date"), air_date):
                    sets.append("air_date = %s")
                    vals.append(air_date)
                    updated.append("air_date")

                if not sets:
                    return {"ok": True, "updated": [], "skipped": True}

                sets.append("updated_at = %s")
                vals.append(_utc_now_str())
                vals.append(page_id)
                cur.execute(
                    f"UPDATE media_pages SET {', '.join(sets)} WHERE page_id = %s",
                    tuple(vals),
                )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "updated": updated}

    def enrich_tmdb_display_meta(
        self,
        *,
        tmdb_id: int,
        media_kind: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        page_id: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        从 TMDB 拉取海报/简介并空则补写入 MySQL。

        @param tmdb_id: TMDB ID
        @param media_kind: tv | movie
        @param season: 剧集季号
        @param episode: 剧集集号
        @param page_id: 可选页主键；缺省时按槽位解析
        @param force: True 时覆盖已有展示字段
        @returns: 拉取与写入摘要
        """
        from workflow.metadata.tmdb_api import (
            TmdbApiClient,
            fetch_display_metadata,
            fetch_episode_display_metadata,
        )

        self.ensure_overview_zh_columns()
        catalog_id = build_catalog_id(tmdb_id, media_kind)
        resolved_page_id = page_id or self.resolve_page_id(
            tmdb_id, media_kind, season, episode
        )
        client = TmdbApiClient()
        if not client.configured():
            return {
                "ok": False,
                "skipped": True,
                "reason": "tmdb_api_key_missing",
                "catalog_id": catalog_id,
                "page_id": resolved_page_id,
            }

        # 若非 force 且作品海报+双语简介已齐，跳过作品级 API
        need_catalog = force
        need_episode = False
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT poster_path, overview, overview_zh
                    FROM media_catalog WHERE catalog_id = %s LIMIT 1
                    """,
                    (catalog_id,),
                )
                cat = cur.fetchone() or {}
                if force or not (
                    str(cat.get("poster_path") or "").strip()
                    and (
                        str(cat.get("overview") or "").strip()
                        or str(cat.get("overview_zh") or "").strip()
                    )
                ):
                    need_catalog = True

                if media_kind == "tv" and season is not None and episode is not None:
                    cur.execute(
                        """
                        SELECT overview, overview_zh, episode_title
                        FROM media_pages WHERE page_id = %s LIMIT 1
                        """,
                        (resolved_page_id,),
                    )
                    pg = cur.fetchone() or {}
                    if force or not (
                        str(pg.get("overview") or "").strip()
                        or str(pg.get("overview_zh") or "").strip()
                    ):
                        need_episode = True
                elif media_kind == "movie":
                    cur.execute(
                        """
                        SELECT overview, overview_zh FROM media_pages
                        WHERE page_id = %s LIMIT 1
                        """,
                        (resolved_page_id,),
                    )
                    pg = cur.fetchone() or {}
                    if force or not (
                        str(pg.get("overview") or "").strip()
                        or str(pg.get("overview_zh") or "").strip()
                    ):
                        need_episode = True  # 电影页镜像 catalog overview
        finally:
            conn.close()

        catalog_result: Dict[str, Any] = {"skipped": True}
        page_result: Dict[str, Any] = {"skipped": True}
        show_meta: Optional[Dict[str, Any]] = None

        if need_catalog:
            show_meta = fetch_display_metadata(
                tmdb_id, media_kind, client=client
            )
            if show_meta:
                catalog_result = self.upsert_catalog_display_meta(
                    catalog_id,
                    poster_path=str(show_meta.get("poster_path") or ""),
                    overview_en=str(show_meta.get("overview_en") or ""),
                    overview_zh=str(show_meta.get("overview_zh") or ""),
                    title=show_meta.get("title"),
                    year=show_meta.get("year"),
                    runtime_minutes=show_meta.get("runtime_minutes"),
                    force=force,
                )
            else:
                catalog_result = {"ok": False, "error": "fetch_display_failed"}

        if need_episode and media_kind == "tv" and season is not None and episode is not None:
            ep_meta = fetch_episode_display_metadata(
                tmdb_id, int(season), int(episode), client=client
            )
            if ep_meta:
                page_result = self.upsert_page_display_meta(
                    resolved_page_id,
                    overview_en=str(ep_meta.get("overview_en") or ""),
                    overview_zh=str(ep_meta.get("overview_zh") or ""),
                    episode_title=str(ep_meta.get("episode_title") or ""),
                    air_date=ep_meta.get("air_date"),
                    force=force,
                )
            else:
                page_result = {"ok": False, "error": "fetch_episode_failed"}
        elif need_episode and media_kind == "movie":
            # 电影页 overview 空时镜像 catalog
            if show_meta is None and need_catalog is False:
                show_meta = fetch_display_metadata(
                    tmdb_id, media_kind, client=client
                )
            en = str((show_meta or {}).get("overview_en") or "")
            zh = str((show_meta or {}).get("overview_zh") or "")
            if not en or not zh:
                conn = self._connect()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT overview, overview_zh FROM media_catalog "
                            "WHERE catalog_id = %s LIMIT 1",
                            (catalog_id,),
                        )
                        crow = cur.fetchone() or {}
                        en = en or str(crow.get("overview") or "")
                        zh = zh or str(crow.get("overview_zh") or "")
                finally:
                    conn.close()
            page_result = self.upsert_page_display_meta(
                resolved_page_id,
                overview_en=en,
                overview_zh=zh,
                force=force,
            )

        # Hub 页：把 catalog overview 镜像到 hub page（空则补）
        if media_kind == "tv":
            hub_id = build_page_id(tmdb_id, "tv", page_type="show_hub")
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT overview, overview_zh FROM media_catalog "
                        "WHERE catalog_id = %s LIMIT 1",
                        (catalog_id,),
                    )
                    crow = cur.fetchone() or {}
            finally:
                conn.close()
            self.upsert_page_display_meta(
                hub_id,
                overview_en=str(crow.get("overview") or ""),
                overview_zh=str(crow.get("overview_zh") or ""),
                force=force,
            )

        return {
            "ok": True,
            "catalog_id": catalog_id,
            "page_id": resolved_page_id,
            "catalog": catalog_result,
            "page": page_result,
            "force": force,
        }

    def list_pages_needing_display_meta(self, *, limit: int = 500) -> List[Dict[str, Any]]:
        """
        列出海报或简介仍缺的页面（供 meta enrich --all-empty）。

        @param limit: 最大返回条数
        @returns: 含 page_id / tmdb_id / media_kind / season / episode 的字典列表
        """
        self.ensure_overview_zh_columns()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.page_id, c.tmdb_id, c.media_kind, p.page_type,
                           p.season, p.episode,
                           c.poster_path, c.overview AS cat_overview,
                           c.overview_zh AS cat_overview_zh,
                           p.overview AS page_overview,
                           p.overview_zh AS page_overview_zh
                    FROM media_pages p
                    JOIN media_catalog c ON c.catalog_id = p.catalog_id
                    WHERE p.page_type IN ('episode', 'movie', 'show_hub')
                      AND (
                        IFNULL(c.poster_path, '') = ''
                        OR (
                          IFNULL(c.overview, '') = ''
                          AND IFNULL(c.overview_zh, '') = ''
                        )
                        OR (
                          p.page_type = 'episode'
                          AND IFNULL(p.overview, '') = ''
                          AND IFNULL(p.overview_zh, '') = ''
                        )
                        OR (
                          p.page_type = 'movie'
                          AND IFNULL(p.overview, '') = ''
                          AND IFNULL(p.overview_zh, '') = ''
                        )
                      )
                    ORDER BY p.updated_at DESC
                    LIMIT %s
                    """,
                    (int(limit),),
                )
                rows = cur.fetchall() or []
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def page_has_resources(self, page_id: str, min_magnets: int = 2) -> bool:
        """
        判断页面是否已有足够 magnet（可跳过重复拉取）。

        @param page_id: 页面 ID
        @param min_magnets: 最少 magnet 数
        @returns: True 表示可跳过
        """
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT magnet_count, page_status FROM media_pages WHERE page_id = %s LIMIT 1",
                (page_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return False
        return int(row.get("magnet_count") or 0) >= min_magnets
