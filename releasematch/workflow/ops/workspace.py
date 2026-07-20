# -*- coding: utf-8 -*-
"""
Ops 内存工作区 — 清单来源与筛选中间态（导入跟踪表前）。

@module workflow.ops.workspace
@description
  进程内保存当前加载的候选 slots 与筛选结果；
  筛选「导入跟踪」后写入 MySQL ops_track_* 表。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from workflow.ops.filter_service import apply_filters
from workflow.ops.track_store import create_batch, make_track_row
from workflow.storage.mysql_store import MySQLStore


class OpsWorkspace:
    """
    运营工作区状态。

    @ivar source: 来源元信息
    @ivar candidates: 来源加载的全量候选
    @ivar filtered: 最近一次筛选结果
    @ivar filter_meta: 筛选条件元信息
    """

    def __init__(self) -> None:
        """初始化空工作区。"""
        self.source: Dict[str, Any] = {}
        self.candidates: List[Dict[str, Any]] = []
        self.filtered: List[Dict[str, Any]] = []
        self.filter_meta: Dict[str, Any] = {}

    def set_source(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        设置清单来源结果（覆盖工作区）。

        @param payload: source_service 返回体（含 slots）
        @returns: 摘要
        """
        self.source = {
            "kind": payload.get("kind"),
            "path": payload.get("path"),
            "abs_path": payload.get("abs_path"),
            "meta": payload.get("meta") or {},
            "tier_counts": payload.get("tier_counts") or {},
            "logic": payload.get("logic"),
            "count": payload.get("count"),
        }
        self.candidates = list(payload.get("slots") or [])
        self.filtered = list(self.candidates)
        self.filter_meta = {
            "count_before": len(self.candidates),
            "count_after": len(self.filtered),
        }
        return self.snapshot()

    def add_slots(
        self,
        slots: List[Dict[str, Any]],
        *,
        mode: str = "append",
        source_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        将手动勾选槽位写入工作区。

        @param slots: 已标注 page_id / source_tier 的槽位
        @param mode: append=按 page_id 去重合并；replace=整表替换
        @param source_meta: 可选覆盖/合并来源元信息
        @returns: 快照摘要
        """
        if mode == "replace":
            self.candidates = list(slots)
            self.source = {
                "kind": (source_meta or {}).get("kind") or "tmdb_export_manual",
                "path": (source_meta or {}).get("path"),
                "meta": (source_meta or {}).get("meta") or {},
                "count": len(self.candidates),
                "tier_counts": (source_meta or {}).get("tier_counts") or {},
            }
        else:
            by_id = {str(s.get("page_id")): s for s in self.candidates}
            for slot in slots:
                by_id[str(slot.get("page_id"))] = slot
            self.candidates = list(by_id.values())
            prev_kind = self.source.get("kind") or "empty"
            self.source = {
                **self.source,
                "kind": (
                    "mixed"
                    if prev_kind not in ("", "empty", "tmdb_export_manual")
                    else "tmdb_export_manual"
                ),
                "meta": {
                    **(self.source.get("meta") or {}),
                    **((source_meta or {}).get("meta") or {}),
                    "last_manual_add": len(slots),
                },
                "count": len(self.candidates),
            }
            if source_meta and source_meta.get("tier_counts"):
                self.source["tier_counts"] = source_meta.get("tier_counts")

        self.filtered = list(self.candidates)
        self.filter_meta = {
            "count_before": len(self.candidates),
            "count_after": len(self.filtered),
            "note": f"manual_{mode}",
        }
        return {
            "ok": True,
            "mode": mode,
            "added": len(slots),
            "workspace": self.snapshot(),
        }

    def apply_filter(self, **kwargs: Any) -> Dict[str, Any]:
        """
        对候选清单执行筛选。

        @param kwargs: 传给 apply_filters 的参数
        @returns: 筛选结果摘要
        """
        result = apply_filters(self.candidates, **kwargs)
        self.filtered = list(result.get("slots") or [])
        self.filter_meta = result.get("filter") or {}
        return {
            "ok": True,
            "count_before": result.get("count_before"),
            "count_after": result.get("count_after"),
            "filter": self.filter_meta,
            "slots": self.filtered,
            "source": self.source,
        }

    def import_to_track(
        self,
        *,
        selected_page_ids: Optional[List[str]] = None,
        confirm_published: bool = False,
    ) -> Dict[str, Any]:
        """
        将筛选结果导入跟踪表（贯通生成 + 上线）。

        @param selected_page_ids: 若给定，仅导入勾选
        @param confirm_published: 与统管 published 重叠时须为 True，否则返回需确认
        @returns: 新建批次；或 needs_confirm + published_overlap
        """
        slots = self.filtered if self.filtered else self.candidates
        if selected_page_ids is not None:
            allow = set(selected_page_ids)
            slots = [s for s in slots if s.get("page_id") in allow]
        if not slots:
            return {"ok": False, "error": "没有可导入的槽位；请先加载清单并筛选"}

        rows = [
            make_track_row(s, source_tier=str(s.get("source_tier") or "unknown"))
            for s in slots
        ]

        # 与统管表对齐：提示已 published，避免无意识重复生成
        published_overlap: List[str] = []
        try:
            published = set(MySQLStore().list_published_page_ids())
            published_overlap = [r["page_id"] for r in rows if r.get("page_id") in published]
        except Exception:  # noqa: BLE001
            published_overlap = []

        if published_overlap and not confirm_published:
            return {
                "ok": False,
                "needs_confirm": True,
                "error": (
                    f"其中 {len(published_overlap)} 个已在统管表 published；"
                    "确认后请带 confirm_published=true 再导入"
                ),
                "published_overlap": published_overlap,
                "published_overlap_count": len(published_overlap),
                "would_import": len(rows),
            }

        batch = create_batch(
            rows,
            source_meta=self.source,
            filter_meta=self.filter_meta,
        )
        return {
            "ok": True,
            "batch": batch,
            "imported": len(rows),
            "published_overlap": published_overlap,
            "published_overlap_count": len(published_overlap),
            "warning": (
                f"其中 {len(published_overlap)} 个已在统管表 published；已确认导入"
                if published_overlap
                else None
            ),
        }

    def snapshot(self) -> Dict[str, Any]:
        """返回工作区快照（供 UI）。"""
        return {
            "source": self.source,
            "candidates_count": len(self.candidates),
            "filtered_count": len(self.filtered),
            "filter": self.filter_meta,
            "candidates": self.candidates,
            "filtered": self.filtered,
        }


# 进程单例工作区
WORKSPACE = OpsWorkspace()
