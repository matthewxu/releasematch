#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PoC 脚本共享工具（跨平台）。

@module scripts.poc_lib
@description
  poc_phase0.py / poc_jackett_indexers.py 共用的 HTTP 探测、
  Jackett Torznab 解析与配置读取。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

# releasematch 根目录加入 sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests

from workflow.config import JACKETT_API_KEY as ENV_JACKETT_API_KEY
from workflow.config import JACKETT_BASE_URL as ENV_JACKETT_BASE_URL
from workflow.torrent_sources.config import (
    is_jackett_api_key_configured,
    load_accounts_config,
)

# 浏览器风格请求头（降低部分站点拒连概率）
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/rss+xml, application/xml, */*",
}

# YTS 镜像列表（按优先级）
YTS_MIRRORS: Tuple[str, ...] = (
    "https://yts.lt",
    "https://yts.rs",
    "https://yts.mx",
    "https://yts.gg",
)

# Nyaa 直连镜像（国内常失败，仅作 PoC 探测）
NYAA_MIRRORS: Tuple[str, ...] = (
    "https://nyaa.si",
    "https://nyaa.iss.ink",
)

_ITEM_RE = re.compile(r"<item>", re.IGNORECASE)
_INDEXER_RE = re.compile(r'<indexer id="([^"]+)" configured="true"', re.IGNORECASE)


@dataclass
class JackettCredentials:
    """Jackett 连接凭据。"""

    base_url: str
    api_key: str


@dataclass
class HttpProbeResult:
    """单次 HTTP 探测结果。"""

    ok: bool
    detail: str
    status_code: Optional[int] = None
    byte_length: int = 0
    item_count: int = 0


def resolve_jackett_credentials(api_key_override: str = "") -> JackettCredentials:
    """
    从环境变量、CLI 参数、accounts.local.json 解析 Jackett 配置。

    @param api_key_override: CLI 传入的 API Key（优先）
    @returns: JackettCredentials
    """
    cfg = load_accounts_config()
    jackett = cfg.get("jackett", {})
    base_url = str(jackett.get("base_url") or ENV_JACKETT_BASE_URL).rstrip("/")
    api_key = (
        api_key_override.strip()
        or ENV_JACKETT_API_KEY.strip()
        or str(jackett.get("api_key") or "").strip()
    )
    return JackettCredentials(base_url=base_url, api_key=api_key)


def torznab_item_count(xml_text: str) -> int:
    """
    统计 Torznab/RSS XML 中的 item 条数。

    @param xml_text: 响应正文
    @returns: <item> 出现次数
    """
    return len(_ITEM_RE.findall(xml_text))


def get_configured_indexer_ids(base_url: str, api_key: str, timeout: float = 30.0) -> List[str]:
    """
    通过 Torznab t=indexers 获取已配置的 Jackett indexer ID 列表。

    @param base_url: Jackett 根 URL
    @param api_key: API Key
    @param timeout: 超时秒数
    @returns: indexer id 列表（如 1337x, yts）
    """
    url = (
        f"{base_url}/api/v2.0/indexers/all/results/torznab/api"
        f"?apikey={api_key}&t=indexers&configured=true"
    )
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    ids = _INDEXER_RE.findall(response.text)
    # 去重保序
    seen: set[str] = set()
    ordered: List[str] = []
    for idx in ids:
        if idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    return ordered


def get_nyaa_indexer_ids(base_url: str, api_key: str) -> List[str]:
    """
    从已配置 indexer 中筛选 Nyaa 相关 ID。

    @param base_url: Jackett 根 URL
    @param api_key: API Key
    @returns: 含 nyaa 的 indexer id
    """
    return [i for i in get_configured_indexer_ids(base_url, api_key) if "nyaa" in i.lower()]


def run_probe(label: str, fn: Callable[[], str]) -> HttpProbeResult:
    """
    执行探测函数并捕获异常。

    @param label: 日志标签（未写入 detail，供扩展）
    @param fn: 成功时返回描述字符串
    @returns: HttpProbeResult
    """
    _ = label
    try:
        detail = fn()
        return HttpProbeResult(ok=True, detail=detail)
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None
        return HttpProbeResult(ok=False, detail=str(exc), status_code=code)
    except Exception as exc:  # noqa: BLE001 — PoC 需汇总所有失败
        return HttpProbeResult(ok=False, detail=str(exc))


def torznab_get(url: str, timeout: float = 90.0) -> requests.Response:
    """
    发起 Torznab GET 请求。

    @param url: 完整 URL
    @param timeout: 超时秒数
    @returns: requests.Response
    """
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def build_torznab_api(base_url: str, indexer_id: str, api_key: str) -> str:
    """
    构建 indexer Torznab API 前缀（不含 t= 参数）。

    @param base_url: Jackett 根 URL
    @param indexer_id: indexer id 或 all
    @param api_key: API Key
    @returns: API URL 前缀
    """
    return (
        f"{base_url}/api/v2.0/indexers/{indexer_id}/results/torznab/api"
        f"?apikey={api_key}&cache=false"
    )


def jackett_tv_slot_probes(base_url: str, api_key: str) -> List[Tuple[str, str]]:
    """
    Breaking Bad S04E06 剧集槽位的 Torznab 探测 URL 列表。

    @param base_url: Jackett 根 URL
    @param api_key: API Key
    @returns: (模式名, URL) 列表
    """
    api = build_torznab_api(base_url, "all", api_key)
    q = quote("Breaking Bad")
    return [
        ("tvdbid", f"{api}&t=tvsearch&tvdbid=81189&season=4&ep=6"),
        ("q+s+e", f"{api}&t=tvsearch&q={q}&season=4&ep=6"),
    ]


def indexer_probe_urls(base_url: str, api_key: str, indexer_id: str) -> List[Tuple[str, str]]:
    """
    单 indexer 多模式探测 URL（与 poc_jackett_indexers 一致）。

    @param base_url: Jackett 根 URL
    @param api_key: API Key
    @param indexer_id: indexer id
    @returns: (模式名, URL) 列表
    """
    api = build_torznab_api(base_url, indexer_id, api_key)
    q = quote("Breaking Bad")
    q_rel = quote("Breaking.Bad.S04E06")
    return [
        ("tvsearch+tvdbid", f"{api}&t=tvsearch&tvdbid=81189&season=4&ep=6"),
        ("tvsearch+q+s+e", f"{api}&t=tvsearch&q={q}&season=4&ep=6"),
        ("search+release", f"{api}&t=search&q={q_rel}"),
        ("movie+imdb", f"{api}&t=movie&imdbid=0133093"),
    ]


def test_yts_direct(imdb_id: str = "tt0133093", timeout: float = 25.0) -> str:
    """
    直连 YTS API，镜像依次回退。

    @param imdb_id: IMDb ID
    @param timeout: 单次请求超时
    @returns: 成功描述字符串
    @raises: RuntimeError 全部镜像失败
    """
    errors: List[str] = []
    for base in YTS_MIRRORS:
        url = f"{base}/api/v2/movie_details.json?imdb_id={imdb_id}"
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            response.raise_for_status()
            return f"OK status={response.status_code} mirror={base}"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {exc}")
    raise RuntimeError(" | ".join(errors))


def test_nyaa_rss_direct(query: str = "Breaking+Bad", timeout: float = 25.0) -> str:
    """
    直连 Nyaa RSS。

    @param query: RSS 查询串
    @param timeout: 超时秒数
    @returns: 成功描述
    @raises: RuntimeError 全部镜像失败
    """
    errors: List[str] = []
    for base in NYAA_MIRRORS:
        url = f"{base}/?page=rss&q={query}&c=1_0"
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            response.raise_for_status()
            return f"OK status={response.status_code} mirror={base} bytes={len(response.content)}"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base}: {exc}")
    raise RuntimeError(" | ".join(errors))


def is_valid_jackett_key(api_key: str) -> bool:
    """API Key 是否已配置且非占位符。"""
    return is_jackett_api_key_configured(api_key)
