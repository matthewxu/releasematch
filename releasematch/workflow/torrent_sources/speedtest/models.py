# -*- coding: utf-8 -*-
"""
测速任务与结果数据模型。

@module workflow.torrent_sources.speedtest.models
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from workflow.torrent_sources.speedtest.torrent_metadata import TorrentMetadataResult


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
    @var phase: 固定为 1
    """

    infohash: str
    peers_reachable: int = 0
    peers_total: int = 0
    elapsed_ms: int = 0
    status: str = "ok"
    error: Optional[str] = None
    mode: str = "dry_run"
    page_id: Optional[str] = None
    phase: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return asdict(self)


@dataclass
class FragmentSpeedResult:
    """
    Phase 2 片段下载测速结果（S-06）。

    @var infohash: 被测 infohash
    @var avg_kbps: 平均下载速度 KiB/s
    @var max_kbps: 峰值下载速度 KiB/s
    @var latency_ms: 首包延迟（metadata 就绪至首字节 payload）
    @var bytes_downloaded: 实际下载字节数
    @var peers_reachable: 结束时已连接 peer 数
    @var peers_total: 结束时观测 peer 总数
    @var elapsed_ms: 总耗时毫秒
    @var status: ok | timeout | error | dry_run
    @var error: 失败时的错误信息
    @var mode: libtorrent | dry_run
    @var phase: 固定为 2
    @var torrent_metadata: Phase 2 期间从 swarm 读取的 torrent 结构（可选）
    """

    infohash: str
    avg_kbps: float = 0.0
    max_kbps: float = 0.0
    latency_ms: int = 0
    bytes_downloaded: int = 0
    peers_reachable: int = 0
    peers_total: int = 0
    elapsed_ms: int = 0
    status: str = "ok"
    error: Optional[str] = None
    mode: str = "dry_run"
    page_id: Optional[str] = None
    phase: int = 2
    torrent_metadata: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        data = asdict(self)
        meta = self.torrent_metadata
        if meta is not None and hasattr(meta, "to_dict"):
            data["torrent_metadata"] = meta.to_dict()
        return data


@dataclass
class FullSpeedResult:
    """
    Phase 1 + Phase 2 组合结果，含聚合展示字段。

    @var phase1: 连接性结果
    @var phase2: 片段测速结果
    @var recommended_speed: 页面展示速度文案（S-06）
    @var reachability: 可达性等级（A-01）
    """

    phase1: ConnectivityResult
    phase2: FragmentSpeedResult
    recommended_speed: str = ""
    reachability: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典。"""
        return {
            "phase1": self.phase1.to_dict(),
            "phase2": self.phase2.to_dict(),
            "recommended_speed": self.recommended_speed,
            "reachability": self.reachability,
        }
