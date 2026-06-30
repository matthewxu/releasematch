#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReleaseMatch Phase 0 PoC：验证四层数据源连通性（跨平台 Python 版）。

@file scripts/poc_phase0.py
@description
  对应 docs/02 §十二。测 4 条「数据通道」，不是 Jackett 内每个 indexer 各测一项。
  逐 indexer 诊断请用 poc_jackett_indexers.py。

  用法：
    cd releasematch
    python scripts/poc_phase0.py
    python scripts/poc_phase0.py --jackett-api-key YOUR_KEY
    python scripts/poc_phase0.py --jackett-base-url http://linode-ip:9117
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.poc_lib import (
    HttpProbeResult,
    get_nyaa_indexer_ids,
    is_valid_jackett_key,
    jackett_tv_slot_probes,
    resolve_jackett_credentials,
    run_probe,
    test_nyaa_rss_direct,
    test_yts_direct,
    torznab_get,
    torznab_item_count,
)

import requests


def _print_probe(prefix: str, result: HttpProbeResult, ok_color: str = "ok") -> bool:
    """
    打印单项探测结果。

    @param prefix: 行前缀（如 OK / FAIL）
    @param result: 探测结果
    @param ok_color: 保留参数（CLI 无颜色）
    @returns: 是否通过
    """
    _ = ok_color
    if result.ok:
        print(f"  OK {result.detail}")
        return True
    print(f"  FAIL: {result.detail}")
    return False


def _test_jackett_all(creds) -> str:
    """Jackett /all 剧集槽位探测，多模式回退。"""
    errors: list[str] = []
    for mode, url in jackett_tv_slot_probes(creds.base_url, creds.api_key):
        try:
            response = torznab_get(url)
            items = torznab_item_count(response.text)
            return (
                f"status={response.status_code} items={items} "
                f"bytes={len(response.content)} mode={mode}"
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{mode}: {exc}")
    raise RuntimeError(" | ".join(errors))


def _test_nyaa_via_jackett(creds) -> str:
    """经 Jackett Nyaa indexer 回退搜索。"""
    indexer_ids = get_nyaa_indexer_ids(creds.base_url, creds.api_key)
    if not indexer_ids:
        raise RuntimeError("No Nyaa indexer in Jackett (add Nyaa.si; id usually nyaasi)")
    errors: list[str] = []
    q = "Breaking%20Bad"
    for idx in indexer_ids:
        url = (
            f"{creds.base_url}/api/v2.0/indexers/{idx}/results/torznab/api"
            f"?apikey={creds.api_key}&t=search&q={q}&cache=false"
        )
        try:
            response = torznab_get(url, timeout=60.0)
            items = torznab_item_count(response.text)
            return f"OK status=200 via Jackett/{idx} items={items} bytes={len(response.content)}"
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            errors.append(f"{idx}: HTTP {code}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{idx}: {exc}")
    raise RuntimeError(" | ".join(errors))


def main(argv: list[str] | None = None) -> int:
    """
    CLI 主入口。

    @param argv: 命令行参数
    @returns: 0 表示 T0 块 B 可接受（>=3 通道通过）
    """
    parser = argparse.ArgumentParser(description="ReleaseMatch Phase 0 PoC (4 source channels)")
    parser.add_argument("--jackett-base-url", default="", help="覆盖 Jackett URL")
    parser.add_argument("--jackett-api-key", default="", help="覆盖 API Key")
    args = parser.parse_args(argv)

    creds = resolve_jackett_credentials(args.jackett_api_key)
    if args.jackett_base_url:
        creds.base_url = args.jackett_base_url.rstrip("/")

    passed = 0
    warnings = 0

    print("=== ReleaseMatch Phase 0 PoC (4 source channels) ===")
    print("Tip: 5 Jackett indexers are aggregated in [1/4].")
    print("     Per-indexer: python scripts/poc_jackett_indexers.py\n")

    # [1/4] Jackett
    print("[1/4] Jackett Torznab /all (Breaking Bad S04E06)...")
    if is_valid_jackett_key(creds.api_key):
        probe = run_probe("jackett", lambda: _test_jackett_all(creds))
        if probe.ok:
            passed += 1
            _print_probe("", probe)
            if "items=0" in probe.detail:
                print("  WARN: HTTP 200 but 0 torrents - TEST each indexer in Jackett Dashboard")
                print("        Then: python scripts/poc_jackett_indexers.py")
                warnings += 1
        else:
            _print_probe("", probe)
    else:
        print("  SKIPPED (no valid API key in accounts.local.json or JACKETT_API_KEY)")

    # [2/4] EZTV direct
    print("\n[2/4] EZTV direct API...")
    probe = run_probe(
        "eztv",
        lambda: (
            f"status="
            f"{requests.get('https://eztvx.to/api/get-torrents?imdb_id=904747&limit=5&page=1', timeout=30).status_code}"
        ),
    )
    if _print_probe("", probe):
        passed += 1

    # [3/4] YTS direct
    print("\n[3/4] YTS direct API...")
    probe = run_probe("yts", test_yts_direct)
    if probe.ok:
        print(f"  {probe.detail}")
        passed += 1
    else:
        print(f"  FAIL: {probe.detail}")

    # [4/4] Nyaa
    print("\n[4/4] Nyaa direct RSS...")
    probe = run_probe("nyaa", test_nyaa_rss_direct)
    if probe.ok:
        print(f"  {probe.detail}")
        passed += 1
    else:
        print(f"  Direct RSS FAIL: {probe.detail}")
        if is_valid_jackett_key(creds.api_key):
            print("  Trying Jackett Nyaa indexers...")
            probe2 = run_probe("nyaa-jackett", lambda: _test_nyaa_via_jackett(creds))
            if probe2.ok:
                print(f"  {probe2.detail}")
                passed += 1
                if "items=0" in probe2.detail:
                    warnings += 1
            else:
                print(f"  FAIL: {probe2.detail}")

    print(f"\n=== Summary: {passed}/4 channels passed, {warnings} warning(s) ===")
    if passed >= 3:
        print("T0 Block B OK. If [1/4] items=0, fix indexers before jackett_client.")
    print("Per-indexer: python scripts/poc_jackett_indexers.py")
    return 0 if passed >= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
