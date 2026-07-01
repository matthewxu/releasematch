#!/usr/bin/env bash
# =============================================================================
# 在本机建立 SSH 动态转发（SOCKS5），经日本 VPS 访问 Nyaa 等被墙站点。
# 无需在 VPS 上部署 Squid/tinyproxy。
#
# 用法：
#   bash scripts/start_ssh_socks_tunnel.sh
#   VPS_HOST=104.105.137.77 LOCAL_PORT=1080 bash scripts/start_ssh_socks_tunnel.sh
#
# 成功后设置：
#   export TORRENT_PROXY=socks5h://127.0.0.1:1080
# =============================================================================

set -euo pipefail

# VPS 公网 IP
VPS_HOST="${VPS_HOST:-104.105.137.77}"
# SSH 用户
VPS_USER="${VPS_USER:-root}"
# 本机 SOCKS5 监听端口
LOCAL_PORT="${LOCAL_PORT:-1080}"

# 若已有同端口监听则跳过
if ss -ltn 2>/dev/null | grep -q ":${LOCAL_PORT} " || lsof -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "端口 ${LOCAL_PORT} 已在监听，假定 SSH SOCKS 隧道已存在。"
  exit 0
fi

echo "=== 建立 SSH SOCKS 隧道 127.0.0.1:${LOCAL_PORT} -> ${VPS_HOST} ==="

# 可选：export SSHPASS=... 后配合 sshpass 非交互登录
SSH_BASE=(ssh -f -N -o StrictHostKeyChecking=no -D "127.0.0.1:${LOCAL_PORT}" "${VPS_USER}@${VPS_HOST}")
if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
  sshpass -e "${SSH_BASE[@]}"
else
  "${SSH_BASE[@]}"
fi

sleep 1
curl -s -o /dev/null -w "Nyaa via SOCKS: HTTP %{http_code}\n" \
  --connect-timeout 15 \
  --proxy "socks5h://127.0.0.1:${LOCAL_PORT}" https://nyaa.si/

echo "隧道就绪。请 export TORRENT_PROXY=socks5h://127.0.0.1:${LOCAL_PORT}"
