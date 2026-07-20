#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release 文件名解析（T0 基础版 + 电影多版本展示字段）。

@module workflow.torrent_sources.release_parser
@description
  从 title_raw 推断 resolution / source / codec / release_group / video_spec / audio_spec。
  展示原则：不确定时留空（模板显示 —），禁止把 Source/平台误写入 Audio，
  禁止把 WEB-DL / DTS-HD / 平台码误切成 Release Group。
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

_RESOLUTION_RE = re.compile(r"\b(2160p|1080p|720p|480p|4K|UHD)\b", re.IGNORECASE)
_SOURCE_RE = re.compile(
    r"\b(WEB-DL|WEBRip|WEB\.DL|BluRay|Blu-Ray|BDRip|BRRip|HDTV|DVDRip|REMUX)\b",
    re.IGNORECASE,
)
_CODEC_RE = re.compile(r"\b(H\.?264|H\.?265|HEVC|x264|x265|AVC|XviD|AV1)\b", re.IGNORECASE)
# 含 AAC2.0 / AAC 5.1 等常见写法，避免有音轨却显示 —
_AUDIO_RE = re.compile(
    r"\b("
    r"DDP5\.?1|DD\+5\.?1|DDP2\.0|DD5\.1|"
    r"AAC(?:\s*[25]\.0)?|AAC5\.1|"
    r"Atmos|TrueHD|DTS-HD\s*MA|DTS-HD|DTS|AC3|FLAC|EAC3"
    r")\b",
    re.IGNORECASE,
)
# 流媒体平台（勿含裸 WEB：会与 WEB-DL 冲突，且 WEB 是 source）
_PLATFORM_RE = re.compile(
    r"\b(AMZN|NF|APTV|HMAX|DSNP|iT|HULU|MAX)\b",
    re.IGNORECASE,
)
# YTS「.web-YTS」或 scene「1080p WEB H264」；不匹配 WEB-DL / WEBRip 前缀
_BARE_WEB_SOURCE_RE = re.compile(
    r"(?<![A-Za-z])WEB(?!-?(?:DL|Rip|\.DL))(?![A-Za-z])",
    re.IGNORECASE,
)
# 盗录标记：收紧 TS，避免「TS Eliot」类片名误判；TELE 单独过宽已移除
_CAM_RE = re.compile(
    r"\b(HDCAM|HDTS|TELESYNC|TELECINE|CAMRip|CAM)\b"
    r"|(?<![A-Za-z])TS(?=[\s.\-_]*?(?:720p|1080p|480p|x264|x265|H\.?26[45]))",
    re.IGNORECASE,
)
# 方括号前缀中不作为 release group 的 token（字幕/语言标记）
_BRACKET_GROUP_SKIP = frozenset(
    {
        "hysub",
        "subs",
        "sub",
        "eng",
        "chs",
        "cht",
        "gb",
        "big5",
    }
)
# 连字符尾段绝不能当 Group（Source / 音轨 / 平台 / 容器碎片）
_GROUP_TAIL_BLOCKLIST: Set[str] = frozenset(
    {
        "dl",
        "rip",
        "hd",
        "ma",
        "web",
        "webdl",
        "webrip",
        "bluray",
        "remux",
        "hdtv",
        "bdrip",
        "brrip",
        "dvdrip",
        "nf",
        "amzn",
        "aptv",
        "hmax",
        "dsnp",
        "hulu",
        "max",
        "it",
        "ddp51",
        "ddp5.1",
        "aac",
        "ac3",
        "dts",
        "atmos",
        "truehd",
        "eac3",
        "flac",
        "x264",
        "x265",
        "h264",
        "h265",
        "hevc",
        "avc",
        "mkv",
        "mp4",
        "avi",
    }
)
# Indexer 预填的「组名」；title 能解析出真实组时允许覆盖
_INDEXER_GROUP_NAMES: Set[str] = frozenset({"yts", "yify", "rarbg", "eztv", "nyaa", "dmhy"})

_PLATFORM_LABELS: Dict[str, str] = {
    "AMZN": "Amazon",
    "NF": "Netflix",
    "APTV": "Apple TV+",
    "HMAX": "Max",
    "DSNP": "Disney+",
    "IT": "iTunes",
    "HULU": "Hulu",
    "MAX": "Max",
}

_EDITION_LABELS: Dict[str, str] = {
    "web-dl": "WEB-DL / WEBRip",
    "remux": "REMUX",
    "bluray": "BluRay / BDRip",
    "hdtv": "HDTV / WEBRip",
    "cam": "CAM / TS（低质量）",
    "other": "其他版本",
}


def _is_junk_group(name: str) -> bool:
    """
    判断是否为误切产生的无效 Group（如 DL、HD、NF）。

    @param name: release_group 候选
    @returns: True 表示不应展示给用户
    """
    key = (name or "").strip().lower()
    if not key:
        return True
    if key in _GROUP_TAIL_BLOCKLIST:
        return True
    if key in _PLATFORM_LABELS or key.upper() in _PLATFORM_LABELS:
        return True
    if len(key) <= 2 and key not in {"pa", "sa", "ba"}:  # 极短碎片多为误切
        return True
    return False


def _is_plausible_group(name: str) -> bool:
    """
    判断候选是否像真实 Release Group。

    @param name: 候选组名
    @returns: True 表示可写入展示字段
    """
    token = (name or "").strip()
    if not token or _is_junk_group(token):
        return False
    if token.lower() in _BRACKET_GROUP_SKIP:
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9+._-]{1,24}$", token))


def _extract_release_group(title: str) -> str:
    """
    从标题提取 Release Group；避免 WEB-DL / DTS-HD / -NF 等误切。

    @param title: 原始标题
    @returns: 组名或空串
    """
    if not title:
        return ""

    # 1) [GROUP] 前缀（动漫/字幕组）
    bracket = re.match(r"^\[([^\]]+)\]", title)
    if bracket:
        inner = bracket.group(1).strip()
        token = re.split(r"[\s/\]]", inner, maxsplit=1)[0].strip()
        if _is_plausible_group(token) and token.lower() not in _BRACKET_GROUP_SKIP:
            return token[:64]

    # 2) 末尾 -Group（scene 惯例）；跳过 WEB-DL / DTS-HD / 平台后缀
    last_ok = ""
    for match in re.finditer(r"-([A-Za-z][A-Za-z0-9+.]{1,24})(?=$|[\s(\[])", title):
        cand = match.group(1)
        before = title[: match.start()]
        before_u = before.upper()
        cand_u = cand.upper()
        # WEB-DL / WEB-RIP
        if before_u.endswith("WEB") and cand_u in ("DL", "RIP"):
            continue
        # DTS-HD / DTS-HD.MA 碎片
        if before_u.endswith("DTS") and cand_u in ("HD", "MA"):
            continue
        if before_u.endswith("DTS-HD") and cand_u == "MA":
            continue
        # 平台码当组名（-NF / -AMZN）
        if cand_u in _PLATFORM_LABELS:
            continue
        if _is_plausible_group(cand):
            last_ok = cand
    if last_ok:
        return last_ok[:64]

    # 3) ...Hon3y / ..Group 尾缀
    dotted = re.search(r"\.{2,}([A-Za-z0-9][A-Za-z0-9._-]{1,20})$", title)
    if dotted and _is_plausible_group(dotted.group(1)):
        return dotted.group(1)[:64]

    # 4) 末段 .Group（无连字符）；排除容器与 source 碎片
    dot_tail = re.search(r"\.([A-Za-z][A-Za-z0-9]{1,15})$", title)
    if dot_tail:
        candidate = dot_tail.group(1)
        if candidate.lower() not in {"mkv", "mp4", "avi", "webrip", "webdl"} and _is_plausible_group(
            candidate
        ):
            return candidate[:64]

    return ""


def _parse_cam_source(title: str) -> str:
    """
    从标题识别盗录源类型，供 Source 列与 edition 一致。

    @param title: 原始标题
    @returns: CAM / TS / 空串
    """
    match = _CAM_RE.search(title or "")
    if not match:
        return ""
    raw = (match.group(0) or "").upper().replace(" ", "")
    if raw.startswith("CAM") or raw == "HDCAM" or "CAMRIP" in raw:
        return "CAM"
    return "TS"


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

    # REMUX 优先于 BluRay，避免 Source 显示 BluRay 而分组是 remux
    if re.search(r"\bREMUX\b", title, re.IGNORECASE):
        result["source"] = "REMUX"
    else:
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
            elif token == "HDTV":
                result["source"] = "HDTV"
            elif token == "DVDRIP":
                result["source"] = "DVDRip"
            else:
                result["source"] = token
        elif _BARE_WEB_SOURCE_RE.search(title):
            # 裸 WEB：不升格为 WEB-DL（避免 YTS/粗标记高估）；展示 WEB
            result["source"] = "WEB"

    cam_source = _parse_cam_source(title)
    if cam_source and not result["source"]:
        result["source"] = cam_source

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

    result["release_group"] = _extract_release_group(title)
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
        label = (
            raw.replace("DD+5.1", "DDP5.1")
            .replace("DD5.1", "DD5.1")
            .replace("AAC2.0", "AAC2.0")
            .replace("AAC5.1", "AAC5.1")
        )
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

    if _CAM_RE.search(title_raw or "") or src in ("cam", "ts"):
        return "cam"
    if "remux" in text or src == "remux":
        return "remux"
    if (
        "web-dl" in text
        or "webdl" in text
        or "webrip" in text
        or src in ("web-dl", "webrip", "web")
        or _BARE_WEB_SOURCE_RE.search(title_raw or "")
    ):
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


def normalize_source_label(source: str) -> str:
    """
    将粗粒度 source 归一为站点展示标签（不升格猜测）。

    @param source: 原始 source（如 YTS 的 web）
    @returns: 展示用 source；空串原样返回
    """
    raw = (source or "").strip()
    if not raw:
        return ""
    key = raw.upper().replace(" ", "")
    if key in ("WEBDL", "WEB-DL"):
        return "WEB-DL"
    if key in ("WEB",):
        return "WEB"
    if key in ("WEBRIP", "WEB-RIP"):
        return "WEBRip"
    if key in ("BLURAY", "BLU-RAY", "BLU.RAY"):
        return "BluRay"
    if key in ("CAM", "CAMRIP", "HDCAM"):
        return "CAM"
    if key in ("TS", "TELESYNC", "HDTS", "TELECINE"):
        return "TS"
    return raw


def build_display_specs(parsed: Dict[str, str], title_raw: str) -> Tuple[str, str]:
    """
    组装页面 Video / Audio 展示行。

    Audio 仅含真实音轨 token；可选前置流媒体平台（AMZN/NF），
    **绝不**把 Source（WEB / WEB-DL 等）写入 Audio。

    @param parsed: parse_release_title 结果
    @param title_raw: 原始标题
    @returns: (video_spec, audio_spec)；无把握时为空串（模板显示 —）
    """
    codec = parsed.get("codec") or ""
    resolution = parsed.get("resolution") or ""
    platform = parsed.get("platform") or ""

    # Video：有编码才展示；仅分辨率时留空（Quality 列已有）
    if codec and resolution:
        video_spec = f"{codec} {resolution}".strip()
    elif codec:
        video_spec = codec
    else:
        video_spec = ""

    audio_tokens = extract_audio_tokens(title_raw)
    platform_label = _PLATFORM_LABELS.get(platform.upper(), platform) if platform else ""

    audio_parts: List[str] = []
    if audio_tokens and platform_label:
        audio_parts.append(platform_label)
    audio_parts.extend(audio_tokens)
    audio_spec = " · ".join(audio_parts).strip()
    return video_spec, audio_spec


def enrich_item_dict(
    item: Dict[str, object],
    *,
    force_specs: bool = False,
) -> Dict[str, object]:
    """
    用 parse_release_title 填充/纠正 ResourceItem 字典。

    策略：title 解析结果优先于 indexer 粗填；误切 Group（DL/HD/NF）与
    indexer 占位组名可被 title 覆盖；展示字段不确定时写空串。

    @param item: 含 title_raw 的字典（原地更新并返回）
    @param force_specs: True 时始终重算 video_spec / audio_spec
    @returns: 同一字典引用
    """
    title = str(item.get("title_raw") or "")
    parsed = parse_release_title(title)

    # resolution / codec：title 命中则覆盖（纠正 DB 陈旧值）
    for key in ("resolution", "codec"):
        if parsed.get(key):
            item[key] = parsed[key]
        elif not item.get(key):
            item[key] = ""

    # source：title 优先；裸 WEB 不覆盖 indexer 更具体的 WEBRip/WEB-DL
    _coarse = {"WEB"}
    if parsed.get("source"):
        parsed_src = normalize_source_label(parsed["source"])
        existing_src = normalize_source_label(str(item.get("source") or ""))
        if (
            existing_src
            and parsed_src in _coarse
            and existing_src not in _coarse
        ):
            item["source"] = existing_src
        else:
            item["source"] = parsed_src
    elif item.get("source"):
        item["source"] = normalize_source_label(str(item.get("source") or ""))
    else:
        item["source"] = ""

    # YTS/YIFY 重编码：库内 WEB/WEB-DL 统一展示为 WEBRip，避免高估为 scene WEB-DL
    _rg = str(item.get("release_group") or "").strip().lower()
    if _rg in ("yts", "yify") and str(item.get("source") or "").upper() in ("WEB", "WEB-DL"):
        item["source"] = "WEBRip"

    # release_group：纠正 junk；indexer 占位可被 title 覆盖
    existing_group = str(item.get("release_group") or "").strip()
    parsed_group = parsed.get("release_group") or ""
    if parsed_group and _is_plausible_group(parsed_group):
        if (
            not existing_group
            or _is_junk_group(existing_group)
            or existing_group.lower() in _INDEXER_GROUP_NAMES
        ):
            item["release_group"] = parsed_group
        # 已有合理 scene group 则保留
    elif existing_group and _is_junk_group(existing_group):
        item["release_group"] = ""

    if parsed.get("platform"):
        item["platform"] = parsed["platform"]

    parsed["source"] = str(item.get("source") or "")
    video_spec, audio_spec = build_display_specs(parsed, title)
    if force_specs or not item.get("video_spec"):
        item["video_spec"] = video_spec
    if force_specs or not item.get("audio_spec"):
        item["audio_spec"] = audio_spec
    # force 时清空历史错误 audio（如曾写入 WEB）
    if force_specs:
        item["video_spec"] = video_spec
        item["audio_spec"] = audio_spec
    return item
