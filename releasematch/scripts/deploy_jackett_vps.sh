#!/usr/bin/env bash
# =============================================================================
# 从本机 SSH 远程一键安装 Jackett + FlareSolverr（日本/海外 VPS）。
#
# @file scripts/deploy_jackett_vps.sh
# @description
#   读取 workflow/torrent_sources/servers.local.json（或环境变量/参数），
#   通过 SSH 将 scripts/remote/install_jackett_stack.sh 推送到远端执行。
#   VPS 侧仅部署 Jackett + FlareSolverr；Nyaa 回退在本机用 SSH SOCKS。
#
# 用法：
#   cd releasematch
#   bash scripts/deploy_jackett_vps.sh
#   bash scripts/deploy_jackett_vps.sh --host 1.2.3.4 --user root
#   SSHPASS='your-pass' bash scripts/deploy_jackett_vps.sh --host 1.2.3.4
#   bash scripts/deploy_jackett_vps.sh --dry-run
#
# 依赖：
#   ssh；非交互密码登录需 sshpass + SSHPASS 环境变量
# =============================================================================

set -euo pipefail

# ── 路径 ────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REMOTE_INSTALL="${SCRIPT_DIR}/remote/install_jackett_stack.sh"
DEFAULT_SERVERS_JSON="${PROJECT_ROOT}/workflow/torrent_sources/servers.local.json"

# ── 默认连接参数（可被 CLI / JSON / 环境变量覆盖）────────────

VPS_HOST="${VPS_HOST:-}"
VPS_USER="${VPS_USER:-root}"
VPS_PORT="${VPS_PORT:-22}"
SERVERS_JSON="${SERVERS_JSON:-${DEFAULT_SERVERS_JSON}}"
DRY_RUN=0
SSH_EXTRA_OPTS=()

# ── 辅助函数 ────────────────────────────────────────────────

usage() {
  # 打印帮助
  cat <<'EOF'
用法: bash scripts/deploy_jackett_vps.sh [选项]

从本机 SSH 到海外 VPS，一键安装 Docker + Jackett + FlareSolverr。

选项:
  --host HOST          VPS IP 或域名（默认从 servers.local.json 读取）
  --user USER          SSH 用户，默认 root
  --port PORT          SSH 端口，默认 22
  --servers-json PATH  服务器凭据 JSON，默认 workflow/torrent_sources/servers.local.json
  --dry-run            仅打印将要执行的 SSH 命令，不实际连接
  -h, --help           显示本帮助

环境变量:
  VPS_HOST, VPS_USER, VPS_PORT, SSHPASS
  FORCE_RECREATE=1     传给远端脚本，强制重建 Docker 容器
  JACKETT_ADMIN_PASSWORD  Dashboard 密码，默认 345621（传给远端）

示例:
  bash scripts/deploy_jackett_vps.sh
  SSHPASS='secret' bash scripts/deploy_jackett_vps.sh --host 172.237.11.232
EOF
}

load_servers_json() {
  # 从 servers.local.json 读取 jackett_vps_japan 段
  local json_path="$1"
  if [[ ! -f "${json_path}" ]]; then
    return 0
  fi
  python3 <<PY
import json
import sys
from pathlib import Path

path = Path("${json_path}")
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"警告: 无法解析 {path}: {exc}", file=sys.stderr)
    sys.exit(0)

block = data.get("jackett_vps_japan") or data.get("vps") or {}
host = block.get("host") or ""
ssh = block.get("ssh") or {}
user = ssh.get("user") or "root"
port = ssh.get("port") or 22
password = ssh.get("password") or ""

# 输出 shell 可 source 的变量（password 不含引号冲突字符时安全）
def esc(s):
    return s.replace("'", "'\\''")

print(f"VPS_HOST='{esc(host)}'")
print(f"VPS_USER='{esc(user)}'")
print(f"VPS_PORT='{esc(str(port))}'")
if password and not __import__("os").environ.get("SSHPASS"):
    print(f"SSHPASS='{esc(password)}'")
PY
}

parse_args() {
  # 解析命令行参数
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        VPS_HOST="$2"
        shift 2
        ;;
      --user)
        VPS_USER="$2"
        shift 2
        ;;
      --port)
        VPS_PORT="$2"
        shift 2
        ;;
      --servers-json)
        SERVERS_JSON="$2"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

resolve_connection() {
  # 从 JSON 补全未指定的连接参数（CLI / 环境变量优先）
  if [[ -f "${SERVERS_JSON}" ]]; then
    local loaded
    loaded="$(load_servers_json "${SERVERS_JSON}" 2>/dev/null || true)"
    if [[ -n "${loaded}" ]]; then
      # 先加载 JSON 默认值，再保留 CLI/环境变量已设置的项
      local saved_host="${VPS_HOST}"
      local saved_user="${VPS_USER}"
      local saved_port="${VPS_PORT}"
      # shellcheck disable=SC1090
      eval "${loaded}"
      [[ -n "${saved_host}" ]] && VPS_HOST="${saved_host}"
      [[ -n "${saved_user}" ]] && VPS_USER="${saved_user}"
      [[ -n "${saved_port}" ]] && VPS_PORT="${saved_port}"
    fi
  fi

  VPS_USER="${VPS_USER:-root}"
  VPS_PORT="${VPS_PORT:-22}"

  if [[ -z "${VPS_HOST}" ]]; then
    echo "错误: 未指定 VPS_HOST。请 --host 或配置 ${SERVERS_JSON}" >&2
    exit 1
  fi
}

build_ssh_command() {
  # 构造 ssh 基础命令数组
  SSH_BASE=(ssh)
  SSH_BASE+=(-p "${VPS_PORT}")
  SSH_BASE+=(-o StrictHostKeyChecking=no)
  SSH_BASE+=(-o ConnectTimeout=15)
  SSH_BASE+=("${SSH_EXTRA_OPTS[@]}")
  SSH_BASE+=("${VPS_USER}@${VPS_HOST}")
}

run_remote_install() {
  # 通过 SSH 管道执行远端安装脚本
  if [[ ! -f "${REMOTE_INSTALL}" ]]; then
    echo "错误: 找不到 ${REMOTE_INSTALL}" >&2
    exit 1
  fi

  build_ssh_command

  local admin_pw="${JACKETT_ADMIN_PASSWORD:-345621}"
  # 单引号包裹密码，避免远端 shell 解析特殊字符
  local remote_prefix="FORCE_RECREATE=${FORCE_RECREATE:-0} JACKETT_ADMIN_PASSWORD='${admin_pw//\'/\'\\\'\'}'"

  echo "=== 远程安装目标: ${VPS_USER}@${VPS_HOST}:${VPS_PORT} ==="

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] ${remote_prefix} bash -s  < ${REMOTE_INSTALL}"
    echo "[dry-run] ssh -p ${VPS_PORT} ${VPS_USER}@${VPS_HOST}"
    exit 0
  fi

  # 远端 bash -s 读取 stdin 上的 install 脚本
  if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
    sshpass -e "${SSH_BASE[@]}" "${remote_prefix} bash -s" < "${REMOTE_INSTALL}"
  else
    "${SSH_BASE[@]}" "${remote_prefix} bash -s" < "${REMOTE_INSTALL}"
  fi
}

main() {
  parse_args "$@"
  resolve_connection
  run_remote_install
}

main "$@"
