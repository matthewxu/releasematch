#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release 文件名解析（T0 基础版 + 电影多版本展示字段）。

@module workflow.torrent_sources.release_parser
@description 从 title_raw 推断 resolution / source / codec / release_group / video_spec / audio_spec。
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

_RESOLUTION_RE = re.compile(r"\b(2160p|1080p|720p|480p|4K|UHD)\b", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"\b(WEB-DL|WEBRip|WEB\.DL|BluRay|Blu-Ray|BDRip|BRRip|HDTV|DVDRip|REMUX)\b",
    re.IGNORECASE,
)
_CODEC_RE = re.compile(r"\b(H\.?264|H\.?265|HEVC|x264|x265|AVC|XviD|AV1)\b", re.IGNORECASE)
_AUDIO_RE = re.compile(
    r"\b(DDP5\.?1|DD\+5\.?1|DDP2\.0|DD5\.1|Atmos|TrueHD|DTS-HD\s*MA|DTS-HD|DTS|AC3|AAC|FLAC|EAC3)\b",
    re.IGNORECASE,
)
_PLATFORM_RE = re.compile(
    r"\b(AMZN|NF|APTV|HMAX|DSNP|iT|HULU|MAX|WEB)\b",
    re.IGNORECASE,
)
_CAM_RE = re.compile(
    r"\b(CAM|HDCAM|HDTS|TELESYNC|TELE|cams?|TS\b|TELECiNE)\b",
    re.IGNORECASE,
)

_PLATFORM_LABELS: Dict[str, str] = {
    "AMZN": "Amazon",
    "NF": "Netflix",
    "APTV": "Apple TV+",
    "HMAX": "Max",
    "DSNP": "Disney+",
    "IT": "iTunes",
    "HULU": "Hulu",
    "MAX": "Max",
    "WEB": "WEB",
}

_EDITION_LABELS: Dict[str, str] = {
    "web-dl": "WEB-DL / WEBRip",
    "remux": "REMUX",
    "bluray": "BluRay / BDRip",
    "hdtv": "HDTV / WEBRip",
    "cam": "CAM / TS（低质量）",
    "other": "其他版本",
}


def parse_release_title(title_raw: str) -> Dict[str, str]:
    """
    从 release 标题解析规格字段（正则，T0 不依赖 mediainfo）。

    @param title_raw: 原始 torrent 标题
    @returns: release_group、resolution、codec、source、platform 字典（未命中则为空串）
    """
    title = title_raw.strip()
    result = {
        "release_group": "",
        "resolution": "",
        "codec": "",
        "source": "",
        "platform": "",
    }
    if not title:
        return result

    res = _RESOLUTION_RE.search(title)
    if res:
        val = res.group(1).upper()
        result["resolution"] = "2160p" if val in ("4K", "UHD") else val.lower()

    src = _SOURCE_RE.search(title)
    if src:
        token = src.group(1).upper().replace(".", "-")
        if "WEBRIP" in token:
            result["source"] = "WEBRip"
        elif token in ("BLU-RAY", "BLURAY"):
            result["source"] = "BluRay"
        elif "WEB-DL" in token:
            result["source"] = "WEB-DL"
        elif token == "BDRIP":
            result["source"] = "BDRip"
        elif token == "BRRIP":
            result["source"] = "BRRip"
        elif token == "REMUX":
            result["source"] = "REMUX"
        elif token == "HDTV":
            result["source"] = "HDTV"
        else:
            result["source"] = token

    codec = _CODEC_RE.search(title)
    if codec:
        raw_codec = codec.group(1).upper().replace(".", "")
        if raw_codec in ("X264", "H264", "AVC"):
            result["codec"] = "H.264"
        elif raw_codec in ("X265", "H265", "HEVC"):
            result["codec"] = "HEVC"
        elif raw_codec == "AV1":
            result["codec"] = "AV1"
        else:
            result["codec"] = raw_codec

    plat = _PLATFORM_RE.search(title)
    if plat:
        result["platform"] = plat.group(1).upper()

    if "-" in title:
        tail = title.rsplit("-", 1)[-1].strip()
        if tail and not re.match(r"^(S\d+E\d+|\d+p)$", tail, re.I):
            group = re.split(r"[\s(\[]", tail, maxsplit=1)[0].strip()
            if group:
                result["release_group"] = group[:64]

    return result


def extract_audio_tokens(title_raw: str) -> List[str]:
    """
    从标题提取音轨 token 列表（去重保序）。

    @param title_raw: release 标题
    @returns: 如 ["DDP5.1", "Atmos"]
    """
    seen = set()
    tokens: List[str] = []
    for match in _AUDIO_RE.finditer(title_raw or ""):
        raw = match.group(1).upper().replace(" ", "")
        label = raw.replace("DD+5.1", "DDP5.1").replace("DD5.1", "DD5.1")
        if label not in seen:
            seen.add(label)
            tokens.append(label)
    return tokens


def classify_edition(title_raw: str, source: str = "") -> str:
    """
    归类电影版本类型（供分组与 scorer tie-break）。

    @param title_raw: release 标题
    @param source: 已解析 source 字段
    @returns: web-dl | remux | bluray | hdtv | cam | other
    """
    text = (title_raw or "").lower()
    src = (source or "").lower()

    if _CAM_RE.search(title_raw or ""):
        return "cam"
    if "remux" in text or src == "remux":
        return "remux"
    if "web-dl" in text or "webdl" in text or src in ("web-dl", "webrip"):
        return "web-dl"
    if "bluray" in text or "blu-ray" in text or src in ("bluray", "bdrip", "brrip"):
        return "bluray"
    if "hdtv" in text or src == "hdtv":
        return "hdtv"
    return "other"


def edition_label(edition_type: str) -> str:
    """
    版本类型的人类可读标签。

    @param edition_type: classify_edition 返回值
    @returns: 中文/英文展示标签
    """
    return _EDITION_LABELS.get(edition_type, _EDITION_LABELS["other"])


def edition_sort_rank(title_raw: str, source: str = "") -> int:
    """
    版本类型排序分（越大越优先，与 scorer 电影 tie-break 一致）。

    @param title_raw: release 标题
    @param source: source 字段
    @returns: 5~50
    """
    edition = classify_edition(title_raw, source)
    return {
        "web-dl": 50,
        "remux": 40,
        "bluray": 45,
        "hdtv": 30,
        "other": 25,
        "cam": 5,
    }.get(edition, 25)


def build_display_specs(parsed: Dict[str, str], title_raw: str) -> Tuple[str, str]:
    """
    组装页面 Video / Audio 展示行。

    @param parsed: parse_release_title 结果
    @param title_raw: 原始标题
    @returns: (video_spec, audio_spec)
    """
    codec = parsed.get("codec") or ""
    resolution = parsed.get("resolution") or ""
    source = parsed.get("source") or ""
    platform = parsed.get("platform") or ""

    video_parts = [p for p in (codec, resolution) if p]
    if not video_parts and source:
        video_parts = [source, resolution] if resolution else [source]
    video_spec = " ".join(video_parts).strip()

    audio_tokens = extract_audio_tokens(title_raw)
    platform_label = _PLATFORM_LABELS.get(platform.upper(), platform) if platform else ""
    source_part = source if source and source not in ("WEB-DL", "WEBRip") else ""
    if source in ("WEB-DL", "WEBRip") and not platform_label:
        source_part = source

    audio_parts: List[str] = []
    if platform_label:
        audio_parts.append(platform_label)
    elif source_part:
        audio_parts.append(source_part)
    audio_parts.extend(audio_tokens)
    audio_spec = " · ".join(audio_parts).strip()
    return video_spec, audio_spec


def enrich_item_dict(
    item: Dict[str, object],
    *,
    force_specs: bool = False,
) -> Dict[str, object]:
    """
    用 parse_release_title 填充 ResourceItem 字典；可选强制刷新 video/audio 展示行。

    @param item: 含 title_raw 的字典（原地更新并返回）
    @param force_specs: True 时始终重算 video_spec / audio_spec
    @returns: 同一字典引用
    """
    title = str(item.get("title_raw") or "")
    parsed = parse_release_title(title)
    for key in ("release_group", "resolution", "codec", "source"):
        if not item.get(key):
            item[key] = parsed[key]
    if parsed.get("platform"):
        item["platform"] = parsed["platform"]

    video_spec, audio_spec = build_display_specs(parsed, title)
    if force_specs or not item.get("video_spec"):
        item["video_spec"] = video_spec
    if force_specs or not item.get("audio_spec"):
        item["audio_spec"] = audio_spec
    return item
