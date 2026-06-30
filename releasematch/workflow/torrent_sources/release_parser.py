#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release 文件名解析（T0 基础版）。

@module workflow.torrent_sources.release_parser
@description 从 title_raw 推断 resolution / source / codec / release_group。
"""

from __future__ import annotations

import re
from typing import Dict

_RESOLUTION_RE = re.compile(r"\b(2160p|1080p|720p|480p|4K)\b", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"\b(WEB-DL|WEBRip|WEB\.DL|BluRay|BDRip|BRRip|HDTV|DVDRip|REMUX)\b",
    re.IGNORECASE,
)
_CODEC_RE = re.compile(r"\b(H\.?264|H\.?265|HEVC|x264|x265|AVC|XviD)\b", re.IGNORECASE)


def parse_release_title(title_raw: str) -> Dict[str, str]:
    """
    从 release 标题解析规格字段（正则，T0 不依赖 mediainfo）。

    @param title_raw: 原始 torrent 标题
    @returns: release_group、resolution、codec、source 字典（未命中则为空串）
    """
    title = title_raw.strip()
    result = {
        "release_group": "",
        "resolution": "",
        "codec": "",
        "source": "",
    }
    if not title:
        return result

    res = _RESOLUTION_RE.search(title)
    if res:
        val = res.group(1).upper()
        result["resolution"] = "2160p" if val == "4K" else val.lower()

    src = _SOURCE_RE.search(title)
    if src:
        result["source"] = src.group(1).upper().replace(".", "-").replace("WEBRIP", "WEBRip")

    codec = _CODEC_RE.search(title)
    if codec:
        raw_codec = codec.group(1).upper().replace(".", "")
        if raw_codec in ("X264", "H264", "AVC"):
            result["codec"] = "H.264"
        elif raw_codec in ("X265", "H265", "HEVC"):
            result["codec"] = "HEVC"
        else:
            result["codec"] = raw_codec

    # 压制组：最后一个 - 后的首段 token（排除季集/分辨率；MySQL VARCHAR(64) 上限）
    if "-" in title:
        tail = title.rsplit("-", 1)[-1].strip()
        if tail and not re.match(r"^(S\d+E\d+|\d+p)$", tail, re.I):
            group = re.split(r"[\s(\[]", tail, maxsplit=1)[0].strip()
            if group:
                result["release_group"] = group[:64]

    return result


def enrich_item_dict(item: Dict[str, object]) -> Dict[str, object]:
    """
    用 parse_release_title 填充 ResourceItem 字典中的空字段。

    @param item: 含 title_raw 的字典（原地更新并返回）
    @returns: 同一字典引用
    """
    title = str(item.get("title_raw") or "")
    parsed = parse_release_title(title)
    for key in ("release_group", "resolution", "codec", "source"):
        if not item.get(key):
            item[key] = parsed[key]
    return item
