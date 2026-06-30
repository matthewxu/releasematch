#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jackett 逐 indexer 探测（跨平台 Python 版）。

@file scripts/poc_jackett_indexers.py
@description
  poc_phase0.py 测 4 条数据通道；本脚本对你配置的每个 Jackett indexer
  分别尝试多种 Torznab 搜索模式。

  用法：
    python scripts/poc_jackett_indexers.py
    python scripts/poc_jackett_indexers.py --jackett-base-url http://linode:9117
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests

from scripts.poc_lib import (  # noqa: E402
    get_configured_indexer_ids,
    indexer_probe_urls,
    is_valid_jackett_key,
    resolve_jackett_credentials,
    torznab_get,
    torznab_item_count,
)


def _probe_indexer(base_url: str, api_key: str, indexer_id: str) -> None:
    """
    对单个 indexer 打印各模式探测结果。

    @param base_url: Jackett URL
    @param api_key: API Key
    @param indexer_id: indexer id
    """
    print(f"[{indexer_id}]")
    best_items = 0
    for name, url in indexer_probe_urls(base_url, api_key, indexer_id):
        try:
            response = torznab_get(url)
            items = torznab_item_count(response.text)
            nbytes = len(response.content)
            line = f"  {name}: HTTP {response.status_code} items={items} bytes={nbytes}"
            if items > 0:
                print(line)
                best_items = max(best_items, items)
            elif response.status_code == 200:
                print(line)
            else:
                print(line)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            print(f"  {name}: FAIL HTTP {code}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: FAIL {exc}")
    if best_items == 0:
        print("  -> No results. Click TEST on this indexer in Jackett Dashboard.")
    print()


def main(argv: List[str] | None = None) -> int:
    """
    CLI 主入口。

    @param argv: 命令行参数
    @returns: 进程退出码
    """
    parser = argparse.ArgumentParser(description="ReleaseMatch Jackett per-indexer probe")
    parser.add_argument("--jackett-base-url", default="", help="覆盖 Jackett URL")
    parser.add_argument("--jackett-api-key", default="", help="覆盖 API Key")
    args = parser.parse_args(argv)

    creds = resolve_jackett_credentials(args.jackett_api_key)
    if args.jackett_base_url:
        creds.base_url = args.jackett_base_url.rstrip("/")

    if not is_valid_jackett_key(creds.api_key):
        print("No valid Jackett API key. Set accounts.local.json or JACKETT_API_KEY.")
        return 1

    print("=== Jackett per-indexer probe ===")
    print("Note: poc_phase0.py = 4 SOURCE CHANNELS; this script = EACH indexer.\n")

    try:
        indexers = get_configured_indexer_ids(creds.base_url, creds.api_key)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to list indexers: {exc}")
        return 1

    if not indexers:
        print("No configured indexers found.")
        return 1

    print(f"Configured indexers ({len(indexers)}): {', '.join(indexers)}\n")
    for idx in indexers:
        _probe_indexer(creds.base_url, creds.api_key, idx)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
