# -*- coding: utf-8 -*-
"""
测速任务与结果数据模型。

@module workflow.torrent_sources.speedtest.models
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SpeedTestTask:
    """
    单条测速任务。

    @var infohash: 40 位小写 infohash
    @var page_id: 可选关联页面 ID（如 tv:1396:s04e06）
    @var phase: 1=连接性 2=片段测速
    @var timeout_sec: 超时秒数
    """

    infohash: str
    page_id: Optional[str] = None
    phase: int = 1
    timeout_sec: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return asdict(self)


@dataclass
class ConnectivityResult:
    """
    Phase 1 连接性测试结果。

    @var infohash: 被测 infohash
    @var peers_reachable: 可达 peer 数
    @var peers_total: 观测到的 peer 总数
    @var elapsed_ms: 耗时毫秒
    @var status: ok | timeout | error | dry_run
    @var error: 失败时的错误信息
    @var mode: libtorrent | dry_run
    """

    infohash: str
    peers_reachable: int = 0
    peers_total: int = 0
    elapsed_ms: int = 0
    status: str = "ok"
    error: Optional[str] = None
    mode: str = "dry_run"
    page_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return asdict(self)
