#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
torrent_metadata 纯函数自检（无需 libtorrent）。

@file scripts/torrent_metadata_selftest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.torrent_sources.speedtest.torrent_metadata import (  # noqa: E402
    compare_torrent_sizes,
    pick_primary_video_file,
)


def main() -> int:
    """运行断言并打印结果。"""
    match, delta = compare_torrent_sizes(2_500_000_000, 2_499_000_000)
    assert match == "ok", match
    assert delta == 1_000_000

    match2, _ = compare_torrent_sizes(2_500_000_000, 2_000_000_000)
    assert match2 == "mismatch", match2

    path, size = pick_primary_video_file(
        [
            ("sample.txt", 1000),
            ("Breaking.Bad.S04E06.1080p.WEB-DL.mkv", 2_400_000_000),
        ]
    )
    assert path.endswith(".mkv"), path
    assert size == 2_400_000_000

    print("torrent_metadata_selftest: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
