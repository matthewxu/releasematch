#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS 侧华语源快速探测 — 利用 VPS 直连 DMHy/Mikan 低延迟。

@file scripts/remote/cn_probe_sources_vps.py
@description 在 Jackett VPS 上运行，仅测 cn_sources Jackett indexers + DMHy RSS。
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# VPS 上 /opt/releasematch/releasematch 或 stdin 传入 APIKEY
APIKEY = sys.argv[1] if len(sys.argv) > 1 else ""
JACKETT = "http://127.0.0.1:9117"
CN_INDEXERS = ["dmhy", "mikan", "acgrip"]

SLOTS = [
    ("庆余年", ["庆余年", "Joy of Life"], 1, 1),
    ("琅琊榜", ["琅琊榜", "Nirvana in Fire"], 1, 1),
    ("三体", ["三体", "Three Body"], 1, 1),
    ("陈情令", ["陈情令", "The Untamed"], 1, 1),
]


def jackett_search(indexer: str, query: str, limit: int = 5) -> list[str]:
    """
    Jackett 文本搜索。

    @param indexer: indexer id
    @param query: 搜索词
    @param limit: 条数上限
    @returns: 标题列表
    """
    enc = urllib.parse.urlencode(
        {"apikey": APIKEY, "t": "search", "q": query, "limit": str(limit)}
    )
    url = f"{JACKETT}/api/v2.0/indexers/{indexer}/results/torznab/api?{enc}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        root = ET.fromstring(resp.read())
    return [(it.findtext("title") or "")[:80] for it in root.findall(".//item")]


def dmhy_rss(keyword: str, limit: int = 5) -> list[str]:
    """
    DMHy RSS 直连。

    @param keyword: 关键词
    @param limit: 条数上限
    @returns: 标题列表
    """
    enc = urllib.parse.urlencode({"keyword": keyword})
    url = f"https://share.dmhy.org/topics/rss/rss.xml?{enc}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        root = ET.fromstring(resp.read())
    titles = []
    for item in root.findall(".//item"):
        t = item.findtext("title") or ""
        if "動漫花園" not in t:
            titles.append(t[:80])
        if len(titles) >= limit:
            break
    return titles


def main() -> int:
    """主入口。"""
    if not APIKEY:
        print(json.dumps({"error": "usage: cn_probe_sources_vps.py APIKEY"}))
        return 1
    report = {"indexers": CN_INDEXERS, "slots": []}
    for label, titles, season, episode in SLOTS:
        slot_row = {"label": label, "sources": {}}
        for t in titles:
            q = f"{t} S{season:02d}E{episode:02d}"
            slot_row["sources"].setdefault("dmhy_rss", []).extend(dmhy_rss(t))
            slot_row["sources"].setdefault("dmhy_rss", []).extend(dmhy_rss(q))
            for idx in CN_INDEXERS:
                key = f"jackett:{idx}"
                try:
                    hits = jackett_search(idx, t) + jackett_search(idx, q)
                    slot_row["sources"].setdefault(key, []).extend(hits)
                except Exception as exc:
                    slot_row["sources"][key] = [f"ERR:{exc}"]
        for k, v in slot_row["sources"].items():
            slot_row["sources"][k] = list(dict.fromkeys(v))[:5]
        slot_row["any_hits"] = any(
            isinstance(v, list) and v and not str(v[0]).startswith("ERR:")
            for v in slot_row["sources"].values()
        )
        report["slots"].append(slot_row)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
