# -*- coding: utf-8 -*-
"""
Ops 跟踪表持久化（MySQL）— 筛选后槽位贯通「生成 → 上线」。

@module workflow.ops.track_store
@description
  表：ops_track_batches + ops_track_slots（见 schema/mysql_schema.sql）。
  对外仍返回与原先 JSON 批次相同的 dict 形状，供 UI / actions 使用。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from workflow.storage.failed_slots_store import build_slot_key
from workflow.storage.mysql_store import MySQLStore, _normalize_row, _utc_now_str

# 单槽阶段名（生成链路）
SLOT_STAGE_NAMES: tuple[str, ...] = ("pipeline", "generate", "speedtest")
# 批次阶段名（上线链路）
BATCH_STEP_NAMES: tuple[str, ...] = ("seo_c2", "deploy")

# DDL：已有库用 ensure_tables 增量建表（与 mysql_schema.sql §9–10 对齐）
_OPS_BATCHES_DDL: str = """
CREATE TABLE IF NOT EXISTS ops_track_batches (
    batch_id                VARCHAR(64)  NOT NULL PRIMARY KEY,
    is_active               TINYINT(1)   NOT NULL DEFAULT 0,
    source_json             JSON         NULL,
    filter_json             JSON         NULL,
    seo_status              VARCHAR(16)  NOT NULL DEFAULT 'pending',
    seo_at                  DATETIME(3)  NULL,
    seo_detail              TEXT,
    deploy_status           VARCHAR(16)  NOT NULL DEFAULT 'pending',
    deploy_at               DATETIME(3)  NULL,
    deploy_detail           TEXT,
    slot_count              INT UNSIGNED NOT NULL DEFAULT 0,
    created_at              DATETIME(3)  NOT NULL,
    updated_at              DATETIME(3)  NOT NULL,
    KEY idx_ops_batch_active (is_active),
    KEY idx_ops_batch_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_OPS_SLOTS_DDL: str = """
CREATE TABLE IF NOT EXISTS ops_track_slots (
    id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    batch_id                VARCHAR(64)  NOT NULL,
    page_id                 VARCHAR(48)  NOT NULL,
    slot_key                VARCHAR(48)  NOT NULL,
    label                   VARCHAR(256) DEFAULT '',
    tmdb_id                 INT UNSIGNED NOT NULL,
    media_type              VARCHAR(16)  NOT NULL,
    season                  SMALLINT UNSIGNED NULL,
    episode                 SMALLINT UNSIGNED NULL,
    title                   VARCHAR(512) DEFAULT '',
    popularity              DOUBLE       NULL,
    source_tier             VARCHAR(32)  NOT NULL DEFAULT 'unknown',
    selected                TINYINT(1)   NOT NULL DEFAULT 1,
    pipeline_status         VARCHAR(16)  NOT NULL DEFAULT 'pending',
    pipeline_at             DATETIME(3)  NULL,
    pipeline_detail         TEXT,
    generate_status         VARCHAR(16)  NOT NULL DEFAULT 'pending',
    generate_at             DATETIME(3)  NULL,
    generate_detail         TEXT,
    speedtest_status        VARCHAR(16)  NOT NULL DEFAULT 'pending',
    speedtest_at            DATETIME(3)  NULL,
    speedtest_detail        TEXT,
    magnet_count            INT          NULL,
    has_recommended         TINYINT(1)   NULL,
    page_status             VARCHAR(16)  NULL,
    robots_noindex          TINYINT(1)   NULL,
    indexable               TINYINT(1)   NULL,
    canonical_path          VARCHAR(256) NULL,
    error_message           TEXT,
    created_at              DATETIME(3)  NOT NULL,
    updated_at              DATETIME(3)  NOT NULL,
    UNIQUE KEY uk_ops_slot_batch_page (batch_id, page_id),
    KEY idx_ops_slot_batch (batch_id),
    KEY idx_ops_slot_page (page_id),
    CONSTRAINT fk_ops_slot_batch FOREIGN KEY (batch_id)
        REFERENCES ops_track_batches(batch_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

_SCHEMA_ENSURED: bool = False


def _utc_now_iso() -> str:
    """返回当前 UTC ISO8601 字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dt_to_iso(value: Any) -> Optional[str]:
    """
    DATETIME / 字符串 → ISO8601（兼容 UI）。

    @param value: 库字段值
    @returns: ISO 字符串或 None
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        return text if text.endswith("Z") else text + ("Z" if len(text) == 19 else "")
    return text.replace(" ", "T")[:19] + "Z"


def _parse_json_field(value: Any) -> Dict[str, Any]:
    """解析 JSON 列（可能已是 dict / str / bytes）。"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        if not value.strip():
            return {}
        return json.loads(value)
    return {}


def _empty_stage(status: str = "pending") -> Dict[str, Any]:
    """构造空阶段状态块。"""
    return {"status": status, "at": None, "detail": ""}


def _empty_gate() -> Dict[str, Any]:
    """构造空 MySQL 门禁块。"""
    return {
        "magnet_count": None,
        "has_recommended": None,
        "page_status": None,
        "robots_noindex": None,
        "indexable": None,
        "canonical_path": None,
    }


def _store() -> MySQLStore:
    """获取 MySQLStore 实例。"""
    return MySQLStore()


def ensure_tables(store: Optional[MySQLStore] = None) -> Dict[str, Any]:
    """
    确保 ops 跟踪表存在（幂等）。

    @param store: 可选 MySQLStore
    @returns: { ok, ensured }
    """
    global _SCHEMA_ENSURED
    store = store or _store()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_OPS_BATCHES_DDL)
            cur.execute(_OPS_SLOTS_DDL)
        conn.commit()
        _SCHEMA_ENSURED = True
        return {"ok": True, "ensured": True}
    finally:
        conn.close()


def _ensure(store: Optional[MySQLStore] = None) -> MySQLStore:
    """惰性建表后返回 store。"""
    store = store or _store()
    if not _SCHEMA_ENSURED:
        ensure_tables(store)
    return store


def resolve_page_id_from_slot(slot: Dict[str, Any]) -> str:
    """
    从 slot 字典推导 page_id / slot_key。

    @param slot: 含 tmdb_id、media_type、可选 season/episode
    @returns: 如 tv:1396:s04e06
    """
    media = str(slot.get("media_type") or slot.get("media_kind") or "tv")
    tmdb_id = int(slot["tmdb_id"])
    return build_slot_key(
        tmdb_id,
        media,
        season=slot.get("season"),
        episode=slot.get("episode"),
    )


def make_track_row(
    slot: Dict[str, Any],
    *,
    source_tier: str = "unknown",
) -> Dict[str, Any]:
    """
    将清单槽位转为跟踪表行（内存形状）。

    @param slot: 原始 slot
    @param source_tier: anchor | curated | pop | file | manual
    @returns: 跟踪行
    """
    page_id = resolve_page_id_from_slot(slot)
    return {
        "slot_key": page_id,
        "page_id": page_id,
        "label": str(slot.get("label") or page_id),
        "tmdb_id": int(slot["tmdb_id"]),
        "media_type": str(slot.get("media_type") or slot.get("media_kind") or "tv"),
        "season": slot.get("season"),
        "episode": slot.get("episode"),
        "title": slot.get("title") or slot.get("label"),
        "popularity": slot.get("popularity"),
        "source_tier": source_tier,
        "selected": True,
        "stages": {
            "pipeline": _empty_stage(),
            "generate": _empty_stage(),
            "speedtest": _empty_stage(),
        },
        "gate": _empty_gate(),
        "error": None,
    }


def _row_to_slot(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    ops_track_slots 行 → UI 槽位 dict。

    @param row: 规范化后的 DB 行
    @returns: 跟踪行
    """
    def _stage(prefix: str) -> Dict[str, Any]:
        return {
            "status": row.get(f"{prefix}_status") or "pending",
            "at": _dt_to_iso(row.get(f"{prefix}_at")),
            "detail": row.get(f"{prefix}_detail") or "",
        }

    has_rec = row.get("has_recommended")
    robots = row.get("robots_noindex")
    indexable = row.get("indexable")
    return {
        "slot_key": row.get("slot_key") or row.get("page_id"),
        "page_id": row["page_id"],
        "label": row.get("label") or row["page_id"],
        "tmdb_id": int(row["tmdb_id"]),
        "media_type": row.get("media_type") or "tv",
        "season": row.get("season"),
        "episode": row.get("episode"),
        "title": row.get("title"),
        "popularity": row.get("popularity"),
        "source_tier": row.get("source_tier") or "unknown",
        "selected": bool(int(row.get("selected") if row.get("selected") is not None else 1)),
        "stages": {
            "pipeline": _stage("pipeline"),
            "generate": _stage("generate"),
            "speedtest": _stage("speedtest"),
        },
        "gate": {
            "magnet_count": row.get("magnet_count"),
            "has_recommended": None if has_rec is None else bool(int(has_rec)),
            "page_status": row.get("page_status"),
            "robots_noindex": None if robots is None else bool(int(robots)),
            "indexable": None if indexable is None else bool(int(indexable)),
            "canonical_path": row.get("canonical_path"),
        },
        "error": row.get("error_message"),
    }


def _batch_row_to_meta(row: Dict[str, Any], slot_count: Optional[int] = None) -> Dict[str, Any]:
    """批次表行 → meta dict。"""
    return {
        "batch_id": row["batch_id"],
        "created_at": _dt_to_iso(row.get("created_at")),
        "updated_at": _dt_to_iso(row.get("updated_at")),
        "source": _parse_json_field(row.get("source_json")),
        "filter": _parse_json_field(row.get("filter_json")),
        "batch_steps": {
            "seo_c2": {
                "status": row.get("seo_status") or "pending",
                "at": _dt_to_iso(row.get("seo_at")),
                "detail": row.get("seo_detail") or "",
            },
            "deploy": {
                "status": row.get("deploy_status") or "pending",
                "at": _dt_to_iso(row.get("deploy_at")),
                "detail": row.get("deploy_detail") or "",
            },
        },
        "slot_count": int(slot_count if slot_count is not None else (row.get("slot_count") or 0)),
        "storage": "mysql",
        "tables": ["ops_track_batches", "ops_track_slots"],
    }


def create_batch(
    slots: List[Dict[str, Any]],
    *,
    source_meta: Optional[Dict[str, Any]] = None,
    filter_meta: Optional[Dict[str, Any]] = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    """
    从筛选结果创建新批次并设为 active（写 MySQL）。

    @param slots: 跟踪行或原始 slot
    @param source_meta: 清单来源元信息
    @param filter_meta: 筛选元信息
    @returns: 完整批次 dict
    """
    store = _ensure()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    rows: List[Dict[str, Any]] = []
    for item in slots:
        if "stages" in item and "gate" in item:
            rows.append(item)
        else:
            tier = str(item.get("source_tier") or "unknown")
            rows.append(make_track_row(item, source_tier=tier))

    now = _utc_now_str()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE ops_track_batches SET is_active = 0 WHERE is_active = 1")
            cur.execute(
                """
                INSERT INTO ops_track_batches (
                    batch_id, is_active, source_json, filter_json,
                    seo_status, deploy_status, slot_count, created_at, updated_at
                ) VALUES (%s, 1, %s, %s, 'pending', 'pending', %s, %s, %s)
                """,
                (
                    batch_id,
                    json.dumps(source_meta or {}, ensure_ascii=False),
                    json.dumps(filter_meta or {}, ensure_ascii=False),
                    len(rows),
                    now,
                    now,
                ),
            )
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO ops_track_slots (
                        batch_id, page_id, slot_key, label, tmdb_id, media_type,
                        season, episode, title, popularity, source_tier, selected,
                        pipeline_status, generate_status, speedtest_status,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        'pending', 'pending', 'pending',
                        %s, %s
                    )
                    """,
                    (
                        batch_id,
                        row["page_id"],
                        row.get("slot_key") or row["page_id"],
                        str(row.get("label") or "")[:256],
                        int(row["tmdb_id"]),
                        str(row.get("media_type") or "tv")[:16],
                        row.get("season"),
                        row.get("episode"),
                        str(row.get("title") or "")[:512],
                        row.get("popularity"),
                        str(row.get("source_tier") or "unknown")[:32],
                        1 if row.get("selected", True) else 0,
                        now,
                        now,
                    ),
                )
        conn.commit()
    finally:
        conn.close()

    batch = load_batch(batch_id)
    assert batch is not None
    return batch


def append_slots_to_active_batch(slots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    将槽位追加到当前活跃跟踪批（已存在的 page_id 跳过）。

    @param slots: 跟踪行或原始 slot（会经 make_track_row 规范化）
    @returns: {ok, batch, added, skipped_existing, batch_id}
    @description
      无活跃批时返回 ok=False，由调用方改走 create_batch。
      用于页面台账「加入当前跟踪批」重跑，不新建假全库批次。
    """
    store = _ensure()
    active_id = get_active_batch_id()
    if not active_id:
        return {"ok": False, "error": "无活跃跟踪批次；请先导入筛选结果或勾选「新建批次」"}

    rows: List[Dict[str, Any]] = []
    for item in slots:
        if "stages" in item and "gate" in item:
            rows.append(item)
        else:
            tier = str(item.get("source_tier") or "inventory")
            rows.append(make_track_row(item, source_tier=tier))
            # 保留调用方显式 page_id（如 show_hub）
            if item.get("page_id"):
                rows[-1]["page_id"] = str(item["page_id"])
                rows[-1]["slot_key"] = str(item.get("slot_key") or item["page_id"])

    now = _utc_now_str()
    added: List[str] = []
    skipped: List[str] = []
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            for row in rows:
                page_id = str(row["page_id"])
                cur.execute(
                    """
                    SELECT id FROM ops_track_slots
                    WHERE batch_id = %s AND page_id = %s LIMIT 1
                    """,
                    (active_id, page_id),
                )
                if cur.fetchone():
                    skipped.append(page_id)
                    continue
                cur.execute(
                    """
                    INSERT INTO ops_track_slots (
                        batch_id, page_id, slot_key, label, tmdb_id, media_type,
                        season, episode, title, popularity, source_tier, selected,
                        pipeline_status, generate_status, speedtest_status,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        'pending', 'pending', 'pending',
                        %s, %s
                    )
                    """,
                    (
                        active_id,
                        page_id,
                        row.get("slot_key") or page_id,
                        str(row.get("label") or "")[:256],
                        int(row["tmdb_id"]),
                        str(row.get("media_type") or "tv")[:16],
                        row.get("season"),
                        row.get("episode"),
                        str(row.get("title") or "")[:512],
                        row.get("popularity"),
                        str(row.get("source_tier") or "inventory")[:32],
                        1 if row.get("selected", True) else 0,
                        now,
                        now,
                    ),
                )
                added.append(page_id)
            cur.execute(
                """
                UPDATE ops_track_batches
                SET slot_count = (
                      SELECT COUNT(*) FROM ops_track_slots WHERE batch_id = %s
                    ),
                    updated_at = %s
                WHERE batch_id = %s
                """,
                (active_id, now, active_id),
            )
        conn.commit()
    finally:
        conn.close()

    batch = load_batch(active_id)
    return {
        "ok": True,
        "batch_id": active_id,
        "batch": batch,
        "added": added,
        "skipped_existing": skipped,
        "created_new_batch": False,
    }


def save_batch(batch: Dict[str, Any], **_ignored: Any) -> str:
    """
    将内存中的批次写回 MySQL（整批 upsert）。

    @param batch: 批次 dict
    @returns: batch_id
    """
    store = _ensure()
    meta = batch.get("meta") or {}
    batch_id = str(meta["batch_id"])
    steps = meta.get("batch_steps") or {}
    seo = steps.get("seo_c2") or {}
    deploy = steps.get("deploy") or {}
    slots = batch.get("slots") or []
    now = _utc_now_str()

    def _stage_at(stage: Dict[str, Any]) -> Optional[str]:
        at = stage.get("at")
        if not at:
            return None
        # ISO → MySQL DATETIME
        text = str(at).replace("Z", "").replace("T", " ")
        return text[:23] if text else None

    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ops_track_batches SET
                    source_json = %s,
                    filter_json = %s,
                    seo_status = %s,
                    seo_at = %s,
                    seo_detail = %s,
                    deploy_status = %s,
                    deploy_at = %s,
                    deploy_detail = %s,
                    slot_count = %s,
                    updated_at = %s
                WHERE batch_id = %s
                """,
                (
                    json.dumps(meta.get("source") or {}, ensure_ascii=False),
                    json.dumps(meta.get("filter") or {}, ensure_ascii=False),
                    str(seo.get("status") or "pending")[:16],
                    _stage_at(seo),
                    seo.get("detail") or "",
                    str(deploy.get("status") or "pending")[:16],
                    _stage_at(deploy),
                    deploy.get("detail") or "",
                    len(slots),
                    now,
                    batch_id,
                ),
            )
            for row in slots:
                stages = row.get("stages") or {}
                gate = row.get("gate") or {}
                pipe = stages.get("pipeline") or {}
                gen = stages.get("generate") or {}
                speed = stages.get("speedtest") or {}
                has_rec = gate.get("has_recommended")
                robots = gate.get("robots_noindex")
                indexable = gate.get("indexable")
                cur.execute(
                    """
                    UPDATE ops_track_slots SET
                        label = %s,
                        selected = %s,
                        pipeline_status = %s,
                        pipeline_at = %s,
                        pipeline_detail = %s,
                        generate_status = %s,
                        generate_at = %s,
                        generate_detail = %s,
                        speedtest_status = %s,
                        speedtest_at = %s,
                        speedtest_detail = %s,
                        magnet_count = %s,
                        has_recommended = %s,
                        page_status = %s,
                        robots_noindex = %s,
                        indexable = %s,
                        canonical_path = %s,
                        error_message = %s,
                        updated_at = %s
                    WHERE batch_id = %s AND page_id = %s
                    """,
                    (
                        str(row.get("label") or "")[:256],
                        1 if row.get("selected", True) else 0,
                        str(pipe.get("status") or "pending")[:16],
                        _stage_at(pipe),
                        pipe.get("detail") or "",
                        str(gen.get("status") or "pending")[:16],
                        _stage_at(gen),
                        gen.get("detail") or "",
                        str(speed.get("status") or "pending")[:16],
                        _stage_at(speed),
                        speed.get("detail") or "",
                        gate.get("magnet_count"),
                        None if has_rec is None else (1 if has_rec else 0),
                        gate.get("page_status"),
                        None if robots is None else (1 if robots else 0),
                        None if indexable is None else (1 if indexable else 0),
                        (gate.get("canonical_path") or None),
                        row.get("error"),
                        now,
                        batch_id,
                        row["page_id"],
                    ),
                )
        conn.commit()
    finally:
        conn.close()

    meta["updated_at"] = _utc_now_iso()
    meta["slot_count"] = len(slots)
    meta["storage"] = "mysql"
    return batch_id


def load_batch(batch_id: str, **_ignored: Any) -> Optional[Dict[str, Any]]:
    """
    从 MySQL 加载完整批次。

    @param batch_id: 批次 ID
    @returns: 批次或 None
    """
    store = _ensure()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM ops_track_batches WHERE batch_id = %s LIMIT 1",
                (batch_id,),
            )
            batch_row = cur.fetchone()
            if not batch_row:
                return None
            batch_row = _normalize_row(dict(batch_row))
            cur.execute(
                """
                SELECT * FROM ops_track_slots
                WHERE batch_id = %s
                ORDER BY id ASC
                """,
                (batch_id,),
            )
            slot_rows = [_normalize_row(dict(r)) for r in (cur.fetchall() or [])]
    finally:
        conn.close()

    slots = [_row_to_slot(r) for r in slot_rows]
    return {
        "meta": _batch_row_to_meta(batch_row, slot_count=len(slots)),
        "slots": slots,
    }


def set_active_batch_id(batch_id: str, **_ignored: Any) -> None:
    """设置当前活跃批次（is_active=1）。"""
    store = _ensure()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE ops_track_batches SET is_active = 0 WHERE is_active = 1")
            cur.execute(
                """
                UPDATE ops_track_batches
                SET is_active = 1, updated_at = %s
                WHERE batch_id = %s
                """,
                (_utc_now_str(), batch_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_active_batch_id(**_ignored: Any) -> Optional[str]:
    """读取当前活跃批次 ID。"""
    store = _ensure()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT batch_id FROM ops_track_batches WHERE is_active = 1 LIMIT 1"
            )
            row = cur.fetchone()
            return str(row["batch_id"]) if row else None
    finally:
        conn.close()


def load_active_batch(**_ignored: Any) -> Optional[Dict[str, Any]]:
    """加载活跃批次。"""
    batch_id = get_active_batch_id()
    if not batch_id:
        return None
    return load_batch(batch_id)


def list_batches(**_ignored: Any) -> List[Dict[str, Any]]:
    """列出历史批次摘要（新→旧）。"""
    store = _ensure()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT batch_id, is_active, source_json, slot_count, created_at, updated_at
                FROM ops_track_batches
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
            rows = [_normalize_row(dict(r)) for r in (cur.fetchall() or [])]
    finally:
        conn.close()

    items: List[Dict[str, Any]] = []
    for row in rows:
        source = _parse_json_field(row.get("source_json"))
        items.append(
            {
                "batch_id": row.get("batch_id"),
                "created_at": _dt_to_iso(row.get("created_at")),
                "updated_at": _dt_to_iso(row.get("updated_at")),
                "slot_count": row.get("slot_count"),
                "is_active": bool(int(row.get("is_active") or 0)),
                "source_kind": source.get("kind"),
                "storage": "mysql",
            }
        )
    return items


def update_slot_stage(
    batch: Dict[str, Any],
    page_id: str,
    stage: str,
    *,
    status: str,
    detail: str = "",
) -> bool:
    """
    更新单槽阶段状态（内存 + 立刻写库）。

    @param batch: 批次（就地修改）
    @param page_id: 槽位 ID
    @param stage: pipeline | generate | speedtest
    @param status: pending|running|ok|skipped|failed
    @param detail: 说明
    @returns: 是否找到槽位
    """
    if stage not in SLOT_STAGE_NAMES:
        return False
    found = False
    for row in batch.get("slots") or []:
        if row.get("page_id") == page_id:
            row.setdefault("stages", {})[stage] = {
                "status": status,
                "at": _utc_now_iso(),
                "detail": detail,
            }
            if status == "failed" and detail:
                row["error"] = detail
            found = True
            break
    if not found:
        return False

    store = _ensure()
    batch_id = str((batch.get("meta") or {}).get("batch_id") or "")
    col_status = f"{stage}_status"
    col_at = f"{stage}_at"
    col_detail = f"{stage}_detail"
    now = _utc_now_str()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            sql = f"""
                UPDATE ops_track_slots SET
                    {col_status} = %s,
                    {col_at} = %s,
                    {col_detail} = %s,
                    error_message = CASE WHEN %s = 'failed' THEN %s ELSE error_message END,
                    updated_at = %s
                WHERE batch_id = %s AND page_id = %s
            """
            cur.execute(
                sql,
                (
                    status[:16],
                    now,
                    detail,
                    status,
                    detail if status == "failed" else None,
                    now,
                    batch_id,
                    page_id,
                ),
            )
            cur.execute(
                "UPDATE ops_track_batches SET updated_at = %s WHERE batch_id = %s",
                (now, batch_id),
            )
        conn.commit()
    finally:
        conn.close()
    return True


def update_slot_gate(batch: Dict[str, Any], page_id: str, gate: Dict[str, Any]) -> bool:
    """更新单槽门禁字段（内存 + 写库）。"""
    found = False
    for row in batch.get("slots") or []:
        if row.get("page_id") == page_id:
            row["gate"] = {**_empty_gate(), **gate}
            found = True
            break
    if not found:
        return False

    store = _ensure()
    batch_id = str((batch.get("meta") or {}).get("batch_id") or "")
    g = {**_empty_gate(), **gate}
    has_rec = g.get("has_recommended")
    robots = g.get("robots_noindex")
    indexable = g.get("indexable")
    now = _utc_now_str()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ops_track_slots SET
                    magnet_count = %s,
                    has_recommended = %s,
                    page_status = %s,
                    robots_noindex = %s,
                    indexable = %s,
                    canonical_path = %s,
                    updated_at = %s
                WHERE batch_id = %s AND page_id = %s
                """,
                (
                    g.get("magnet_count"),
                    None if has_rec is None else (1 if has_rec else 0),
                    g.get("page_status"),
                    None if robots is None else (1 if robots else 0),
                    None if indexable is None else (1 if indexable else 0),
                    g.get("canonical_path"),
                    now,
                    batch_id,
                    page_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return True


def update_batch_step(
    batch: Dict[str, Any],
    step: str,
    *,
    status: str,
    detail: str = "",
) -> None:
    """更新批次级步骤（seo_c2 / deploy）并写库。"""
    batch.setdefault("meta", {}).setdefault("batch_steps", {})[step] = {
        "status": status,
        "at": _utc_now_iso(),
        "detail": detail,
    }
    if step not in BATCH_STEP_NAMES:
        return

    store = _ensure()
    batch_id = str((batch.get("meta") or {}).get("batch_id") or "")
    prefix = "seo" if step == "seo_c2" else "deploy"
    now = _utc_now_str()
    conn = store._connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE ops_track_batches SET
                    {prefix}_status = %s,
                    {prefix}_at = %s,
                    {prefix}_detail = %s,
                    updated_at = %s
                WHERE batch_id = %s
                """,
                (status[:16], now, detail, now, batch_id),
            )
        conn.commit()
    finally:
        conn.close()


def summarize_batch(batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    汇总跟踪表计数，供 UI 顶部指标。

    @param batch: 批次
    @returns: 摘要 dict
    """
    slots = batch.get("slots") or []
    selected = [s for s in slots if s.get("selected", True)]

    def _count_stage(name: str, status: str) -> int:
        return sum(
            1
            for s in selected
            if (s.get("stages") or {}).get(name, {}).get("status") == status
        )

    indexable = sum(1 for s in selected if (s.get("gate") or {}).get("indexable"))
    return {
        "batch_id": (batch.get("meta") or {}).get("batch_id"),
        "total": len(slots),
        "selected": len(selected),
        "pipeline_ok": _count_stage("pipeline", "ok") + _count_stage("pipeline", "skipped"),
        "pipeline_failed": _count_stage("pipeline", "failed"),
        "generate_ok": _count_stage("generate", "ok"),
        "speedtest_ok": _count_stage("speedtest", "ok"),
        "indexable": indexable,
        "batch_steps": (batch.get("meta") or {}).get("batch_steps") or {},
        "storage": "mysql",
    }
