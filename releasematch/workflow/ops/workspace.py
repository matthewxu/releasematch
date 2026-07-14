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
        设置清单来源结果。

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

    def import_to_track(self, *, selected_page_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        将筛选结果导入跟踪表（贯通生成 + 上线）。

        @param selected_page_ids: 若给定，仅导入勾选
        @returns: 新建批次
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
        batch = create_batch(
            rows,
            source_meta=self.source,
            filter_meta=self.filter_meta,
        )
        return {"ok": True, "batch": batch, "imported": len(rows)}

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
