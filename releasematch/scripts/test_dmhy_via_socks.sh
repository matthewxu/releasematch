#!/usr/bin/env bash
# =============================================================================
# 经 SSH SOCKS 隧道测试 DMHy RSS 连通性与 Python 客户端解析。
#
# 前置：bash scripts/start_ssh_socks_tunnel.sh（或本脚本自动检测 1080 端口）
#
# 用法：
#   bash scripts/test_dmhy_via_socks.sh
#   KEYWORD=庆余年 bash scripts/test_dmhy_via_socks.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_PORT="${LOCAL_PORT:-1080}"
KEYWORD="${KEYWORD:-三体}"
PROXY_URL="socks5h://127.0.0.1:${LOCAL_PORT}"

cd "${PROJECT_ROOT}"

# 若 SOCKS 未就绪则尝试启动隧道
if ! lsof -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "=== 端口 ${LOCAL_PORT} 未监听，尝试启动 SSH SOCKS 隧道 ==="
  bash scripts/start_ssh_socks_tunnel.sh
fi

ENC_KEYWORD="$(python3 -c "import urllib.parse; print(urllib.parse.quote('${KEYWORD}'))")"
RSS_URL="https://share.dmhy.org/topics/rss/rss.xml?keyword=${ENC_KEYWORD}&sort_id=0&team_id=0"

echo "=== curl DMHy 直连（可能超时）==="
curl -s -o /dev/null -w "DMHy direct: HTTP %{http_code} time %{time_total}s\n" \
  --connect-timeout 8 --max-time 12 \
  "${RSS_URL}" || echo "DMHy direct: FAILED（预期，将走 SOCKS 回退）"

echo "=== curl DMHy via SOCKS ==="
curl -s -o /dev/null -w "DMHy SOCKS: HTTP %{http_code} time %{time_total}s\n" \
  --connect-timeout 15 --max-time 20 \
  --proxy "${PROXY_URL}" \
  "${RSS_URL}"

echo "=== Python DmhyClient（accounts.local.json proxy 回退）==="
export TORRENT_PROXY="${PROXY_URL}"
.venv/bin/python - <<PY
# -*- coding: utf-8 -*-
"""经 SSH SOCKS 测试 DMHy RSS 解析。"""
from workflow.torrent_sources.config import load_accounts_config
from workflow.torrent_sources.dmhy_client import DmhyClient
from workflow.torrent_sources.http_fetch import proxy_settings_from_config

keyword = "${KEYWORD}"
accounts = load_accounts_config()
proxy = proxy_settings_from_config(accounts.get("proxy"))
dmhy_cfg = accounts.get("dmhy") or {}
client = DmhyClient(
    base_url=str(dmhy_cfg.get("base_url") or "https://share.dmhy.org"),
    timeout_sec=15.0,
    proxy=proxy,
)
items = client.search_rss(keyword, limit=5)
print(f"keyword={keyword!r} hits={len(items)} unreachable={client.unreachable}")
for it in items[:3]:
    print(f"  [{it.infohash[:12]}…] {it.title_raw[:70]}")
PY

echo "=== 完成。生产环境请 export TORRENT_PROXY=${PROXY_URL} ==="
