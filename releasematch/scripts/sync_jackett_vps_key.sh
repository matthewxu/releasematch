#!/usr/bin/env bash
# =============================================================================
# 从远端 VPS 读取 Jackett API Key 并写入 accounts.local.json。
#
# @file scripts/sync_jackett_vps_key.sh
# @description
#   配合 deploy_jackett_vps.sh 使用；SSH 到 VPS 读取 ServerConfig.json 的 APIKey。
#
# 用法：
#   bash scripts/sync_jackett_vps_key.sh
#   bash scripts/sync_jackett_vps_key.sh --host 172.238.11.37
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVERS_JSON="${PROJECT_ROOT}/workflow/torrent_sources/servers.local.json"

VPS_HOST="${VPS_HOST:-}"
VPS_USER="${VPS_USER:-root}"
VPS_PORT="${VPS_PORT:-22}"
JACKETT_PORT="${JACKETT_PORT:-9117}"
SERVER_CONFIG="${SERVER_CONFIG:-/opt/jackett/config/Jackett/ServerConfig.json}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) VPS_HOST="$2"; shift 2 ;;
    --user) VPS_USER="$2"; shift 2 ;;
    --port) VPS_PORT="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${VPS_HOST}" && -f "${SERVERS_JSON}" ]]; then
  VPS_HOST="$(python3 -c "
import json
from pathlib import Path
data = json.loads(Path('${SERVERS_JSON}').read_text(encoding='utf-8'))
print((data.get('jackett_vps_japan') or {}).get('host') or '')
")"
fi

if [[ -z "${VPS_HOST}" ]]; then
  echo "错误: 请 --host 或配置 servers.local.json" >&2
  exit 1
fi

# -T：禁用伪终端，避免 sshpass 在部分环境下报 “Failed to get a pseudo terminal”
SSH_BASE=(ssh -T -p "${VPS_PORT}" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "${VPS_USER}@${VPS_HOST}")
REMOTE_PY="import json; print(json.load(open('${SERVER_CONFIG}')).get('APIKey',''))"

echo "=== 读取远端 API Key: ${VPS_USER}@${VPS_HOST} ==="

SSH_ERR="$(mktemp)"
if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
  API_KEY="$(sshpass -e "${SSH_BASE[@]}" "python3 -c \"${REMOTE_PY}\"" 2>"${SSH_ERR}" || true)"
else
  API_KEY="$("${SSH_BASE[@]}" "python3 -c \"${REMOTE_PY}\"" 2>"${SSH_ERR}" || true)"
fi

API_KEY="$(echo "${API_KEY}" | tr -d '\r\n')"
if [[ -z "${API_KEY}" ]]; then
  echo "错误: 无法读取 API Key（SSH 不通或 Jackett 未安装）" >&2
  if [[ -s "${SSH_ERR}" ]]; then
    echo "--- SSH 详情 ---" >&2
    cat "${SSH_ERR}" >&2
  fi
  rm -f "${SSH_ERR}"
  exit 1
fi
rm -f "${SSH_ERR}"

BASE_URL="http://${VPS_HOST}:${JACKETT_PORT}"
python3 "${SCRIPT_DIR}/setup_jackett_a4.py" --api-key "${API_KEY}" --jackett-url "${BASE_URL}"

echo "=== 已写入 accounts.local.json · base_url=${BASE_URL} ==="
