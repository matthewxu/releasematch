# -*- coding: utf-8 -*-
"""
本地运营控制台（Ops Console）。

@module workflow.ops
@description
  四段式 UI：清单来源 → 筛选 → 跑生成流程 → 上线。
  筛选结果导入 MySQL 跟踪表（ops_track_batches / ops_track_slots）后，
  生成与部署进度按槽位跟踪到底。仅绑定 127.0.0.1，勿部署到公网。
"""

from __future__ import annotations

__all__ = ["DEFAULT_OPS_PORT"]

# 默认本地端口（与 portal serve 8080 错开）
DEFAULT_OPS_PORT: int = 8090
