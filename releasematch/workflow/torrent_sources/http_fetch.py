#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直连 HTTP 请求与可选代理回退。

@module workflow.torrent_sources.http_fetch
@description
  国内访问 Nyaa 等源偶发超时/阻断时，先直连；全部失败后再走本机 SSH SOCKS 隧道
  （ssh -D，无需 VPS 上额外 HTTP 代理）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class ProxySettings:
    """
    代理配置（accounts.local.json 或环境变量）。

    @var url: 代理 URL，如 socks5h://127.0.0.1:1080（SSH -D 隧道）
    @var enabled: 是否启用代理回退
    @var use_when_direct_fails: True=直连失败后再走代理；False=始终走代理
    """

    url: Optional[str] = None
    enabled: bool = True
    use_when_direct_fails: bool = True


def proxy_settings_from_config(cfg: Optional[Dict[str, Any]]) -> ProxySettings:
    """
    从 accounts 配置与环境变量解析 ProxySettings。

    @description
      **优先** ``accounts.local.json`` 的 ``proxy.url``（数据源真相源）。
      仅当 JSON 未配置 url 时，回退环境变量：
      ``TORRENT_PROXY`` > ``TORRENT_HTTP_PROXY`` > ``ALL_PROXY`` > ``HTTPS_PROXY``
      （便于一次性排查，勿再写入 ``.env`` 与 accounts 双轨）。

    @param cfg: accounts JSON 中的 proxy 段；可为 None
    @returns: ProxySettings
    """
    block = dict(cfg or {})
    accounts_url = str(block.get("url") or "").strip()
    env_url = (
        os.getenv("TORRENT_PROXY")
        or os.getenv("TORRENT_HTTP_PROXY")
        or os.getenv("ALL_PROXY")
        or os.getenv("HTTPS_PROXY")
        or ""
    ).strip()
    url = accounts_url or env_url or None
    enabled = block.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() not in ("0", "false", "no")
    use_when = block.get("use_when_direct_fails", True)
    if isinstance(use_when, str):
        use_when = use_when.lower() not in ("0", "false", "no")
    return ProxySettings(
        url=url,
        enabled=bool(enabled) and bool(url),
        use_when_direct_fails=bool(use_when),
    )


def _requests_proxies(proxy_url: str) -> Dict[str, str]:
    """
    构造 requests proxies 字典（支持 http/https/socks5/socks5h）。

    @param proxy_url: 代理根 URL
    @returns: http/https 代理映射
    """
    return {"http": proxy_url, "https": proxy_url}


def http_get(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout_sec: float = 25.0,
    proxy: Optional[ProxySettings] = None,
) -> requests.Response:
    """
    GET 请求：默认直连；配置代理时在直连失败后回退。

    @param url: 完整 URL
    @param headers: 可选请求头
    @param timeout_sec: 超时秒数
    @param proxy: 代理配置
    @returns: 成功 Response
    @raises: 最后一次 requests 异常
    """
    hdrs = headers or {}
    last_error: Optional[Exception] = None

    def _do_get(use_proxy: bool) -> requests.Response:
        """执行单次 GET。"""
        kwargs: Dict[str, Any] = {"headers": hdrs, "timeout": timeout_sec}
        if use_proxy and proxy and proxy.url:
            kwargs["proxies"] = _requests_proxies(proxy.url)
        return requests.get(url, **kwargs)

    if proxy and proxy.enabled and proxy.url and not proxy.use_when_direct_fails:
        response = _do_get(use_proxy=True)
        response.raise_for_status()
        return response

    try:
        response = _do_get(use_proxy=False)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        last_error = exc

    if proxy and proxy.enabled and proxy.url and proxy.use_when_direct_fails:
        try:
            response = _do_get(use_proxy=True)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc

    if last_error:
        raise last_error
    raise RuntimeError("http_get failed without exception")
