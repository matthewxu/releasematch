# -*- coding: utf-8 -*-
"""
磁力测速子模块（T2）。

@package workflow.torrent_sources.speedtest
@description
  Phase 1：peer 可达性探测（libtorrent 或 dry-run 占位）。
  Phase 2：片段下载测速，输出 avg_kbps / max_kbps（S-06）。
"""

from workflow.torrent_sources.speedtest.models import (
    ConnectivityResult,
    FragmentSpeedResult,
    FullSpeedResult,
    SpeedTestTask,
)

__all__ = [
    "ConnectivityResult",
    "FragmentSpeedResult",
    "FullSpeedResult",
    "SpeedTestTask",
]
