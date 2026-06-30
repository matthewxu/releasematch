#!/usr/bin/env bash
# =============================================================================
# 远端 VPS 一键安装 Jackett + FlareSolverr 栈（在服务器上执行）。
#
# @file scripts/remote/install_jackett_stack.sh
# @description
#   幂等部署 Docker 网络、FlareSolverr、Jackett，并写入 FlareSolverr URL。
#   本机 Nyaa 回退使用 SSH SOCKS（ssh -D），无需在 VPS 安装 HTTP 代理。
#
# 用法（通常由 deploy_jackett_vps.sh 通过 SSH 管道调用）：
#   bash scripts/remote/install_jackett_stack.sh
#   FORCE_RECREATE=1 bash scripts/remote/install_jackett_stack.sh
#
# 环境变量（均可选）：
#   DOCKER_NETWORK      Docker 网络名，默认 jackett-net
#   JACKETT_NAME        Jackett 容器名，默认 jackett
#   JACKETT_IMAGE       Jackett 镜像，默认 linuxserver/jackett:latest
#   JACKETT_PORT        Jackett 公网端口，默认 9117
#   JACKETT_CONFIG      Jackett 配置卷宿主机路径，默认 /opt/jackett/config
#   FLARE_NAME          FlareSolverr 容器名，默认 flaresolverr
#   FLARE_IMAGE         FlareSolverr 镜像
#   FLARE_PORT          FlareSolverr 宿主机端口，默认 8191
#   FLARE_BIND          FlareSolverr 绑定地址，默认 127.0.0.1（不暴露公网）
#   FLARE_MAX_TIMEOUT   Jackett 内 FlareSolverr 超时 ms，默认 55000
#   FORCE_RECREATE      设为 1 时强制删除并重建容器
# =============================================================================

set -euo pipefail

# ── 可配置变量 ──────────────────────────────────────────────

DOCKER_NETWORK="${DOCKER_NETWORK:-jackett-net}"

JACKETT_NAME="${JACKETT_NAME:-jackett}"
JACKETT_IMAGE="${JACKETT_IMAGE:-linuxserver/jackett:latest}"
JACKETT_PORT="${JACKETT_PORT:-9117}"
JACKETT_CONFIG="${JACKETT_CONFIG:-/opt/jackett/config}"

FLARE_NAME="${FLARE_NAME:-flaresolverr}"
FLARE_IMAGE="${FLARE_IMAGE:-ghcr.io/flaresolverr/flaresolverr:latest}"
FLARE_PORT="${FLARE_PORT:-8191}"
FLARE_BIND="${FLARE_BIND:-127.0.0.1}"
FLARE_MAX_TIMEOUT="${FLARE_MAX_TIMEOUT:-55000}"

SERVER_CONFIG="${JACKETT_CONFIG}/Jackett/ServerConfig.json"
FLARE_URL_IN_JACKETT="http://${FLARE_NAME}:8191/"

# ── 日志辅助 ────────────────────────────────────────────────

log() {
  # 打印带前缀的信息行
  echo "[install] $*"
}

die() {
  # 打印错误并退出
  echo "[install] 错误: $*" >&2
  exit 1
}

# ── Docker 环境 ─────────────────────────────────────────────

ensure_docker() {
  # 确保 Docker 已安装并运行
  if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
      log "Docker 已就绪"
      return 0
    fi
    log "启动 docker 服务..."
    systemctl enable --now docker 2>/dev/null || service docker start 2>/dev/null || true
    docker info >/dev/null 2>&1 || die "Docker 未运行，请手动检查"
    return 0
  fi

  log "安装 Docker（Debian/Ubuntu apt）..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg docker.io
  systemctl enable --now docker
  docker info >/dev/null 2>&1 || die "Docker 安装后仍不可用"
}

ensure_network() {
  # 创建 Jackett 与 FlareSolverr 共用 Docker 网络
  if docker network inspect "${DOCKER_NETWORK}" >/dev/null 2>&1; then
    log "Docker 网络 ${DOCKER_NETWORK} 已存在"
  else
    docker network create "${DOCKER_NETWORK}"
    log "已创建 Docker 网络 ${DOCKER_NETWORK}"
  fi
}

container_exists() {
  # 判断容器是否已存在（含已停止）
  local name="$1"
  docker ps -a --format '{{.Names}}' | grep -qx "${name}"
}

remove_container_if_force() {
  # FORCE_RECREATE=1 时删除已有容器
  local name="$1"
  if [[ "${FORCE_RECREATE:-0}" == "1" ]] && container_exists "${name}"; then
    log "FORCE_RECREATE：删除容器 ${name}"
    docker rm -f "${name}" >/dev/null
  fi
}

start_flaresolverr() {
  # 启动 FlareSolverr（仅本机绑定，供 Jackett 容器经 Docker DNS 访问）
  remove_container_if_force "${FLARE_NAME}"
  if container_exists "${FLARE_NAME}"; then
    log "容器 ${FLARE_NAME} 已存在，跳过创建"
    docker start "${FLARE_NAME}" 2>/dev/null || true
    return 0
  fi

  log "拉取并启动 ${FLARE_NAME} ..."
  docker pull "${FLARE_IMAGE}"
  docker run -d \
    --name "${FLARE_NAME}" \
    --restart unless-stopped \
    --network "${DOCKER_NETWORK}" \
    -e LOG_LEVEL=info \
    -p "${FLARE_BIND}:${FLARE_PORT}:8191" \
    "${FLARE_IMAGE}"
}

start_jackett() {
  # 启动 Jackett 并挂载配置卷
  remove_container_if_force "${JACKETT_NAME}"
  if container_exists "${JACKETT_NAME}"; then
    log "容器 ${JACKETT_NAME} 已存在，跳过创建"
    docker start "${JACKETT_NAME}" 2>/dev/null || true
    return 0
  fi

  mkdir -p "${JACKETT_CONFIG}"
  log "拉取并启动 ${JACKETT_NAME} ..."
  docker pull "${JACKETT_IMAGE}"
  docker run -d \
    --name "${JACKETT_NAME}" \
    --restart unless-stopped \
    --network "${DOCKER_NETWORK}" \
    -p "0.0.0.0:${JACKETT_PORT}:9117" \
    -v "${JACKETT_CONFIG}:/config" \
    "${JACKETT_IMAGE}"
}

wait_for_server_config() {
  # 等待 Jackett 首次启动并生成 ServerConfig.json
  local i
  log "等待 ${SERVER_CONFIG} 生成（最多 120s）..."
  for i in $(seq 1 60); do
    if [[ -f "${SERVER_CONFIG}" ]]; then
      log "ServerConfig.json 已就绪"
      return 0
    fi
    sleep 2
  done
  die "超时：未找到 ${SERVER_CONFIG}"
}

configure_flaresolverr_in_jackett() {
  # 写入 FlareSolverr URL（Docker 同网必须用容器名，不能用 127.0.0.1）
  log "配置 Jackett FlareSolverrUrl = ${FLARE_URL_IN_JACKETT}"
  python3 <<PY
import json
from pathlib import Path

path = Path("${SERVER_CONFIG}")
data = json.loads(path.read_text(encoding="utf-8"))
data["FlareSolverrUrl"] = "${FLARE_URL_IN_JACKETT}"
data["FlareSolverrMaxTimeout"] = int("${FLARE_MAX_TIMEOUT}")
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("FlareSolverrUrl:", data.get("FlareSolverrUrl"))
PY
  docker restart "${JACKETT_NAME}" >/dev/null
  sleep 5
}

print_api_key() {
  # 输出 API Key 供本机 accounts.local.json 使用
  if [[ ! -f "${SERVER_CONFIG}" ]]; then
    log "警告：无法读取 API Key"
    return 0
  fi
  python3 <<PY
import json
from pathlib import Path
d = json.load(open("${SERVER_CONFIG}", encoding="utf-8"))
print(d.get("APIKey", ""))
PY
}

verify_stack() {
  # 健康检查：Jackett HTTP、FlareSolverr 容器内连通
  local code api_key

  log "验证 Jackett HTTP ..."
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${JACKETT_PORT}/" || echo 000)"
  [[ "${code}" == "200" || "${code}" == "301" || "${code}" == "302" ]] \
    || die "Jackett 未响应 HTTP ${code}"

  log "验证 Jackett 容器 → FlareSolverr ..."
  code="$(docker exec "${JACKETT_NAME}" curl -s -o /dev/null -w '%{http_code}' \
    "http://${FLARE_NAME}:8191/" 2>/dev/null || echo 000)"
  [[ "${code}" == "200" || "${code}" == "404" || "${code}" == "405" ]] \
    || log "警告：Jackett 容器访问 FlareSolverr 返回 ${code}（可稍后在 Dashboard 再测）"

  log "验证 FlareSolverr 本机 API ..."
  curl -s -o /dev/null -w "FlareSolverr sessions.list HTTP %{http_code}\n" \
    -X POST "http://${FLARE_BIND}:${FLARE_PORT}/v1" \
    -H 'Content-Type: application/json' \
    -d '{"cmd":"sessions.list"}' || true
}

print_summary() {
  # 安装完成摘要
  local api_key public_ip
  api_key="$(print_api_key)"
  public_ip="$(curl -4 -s --max-time 5 ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"

  cat <<EOF

================================================================================
  Jackett + FlareSolverr 安装完成
================================================================================
  Jackett URL    : http://${public_ip}:${JACKETT_PORT}
  Dashboard      : http://${public_ip}:${JACKETT_PORT}/UI/Dashboard
  API Key        : ${api_key}
  FlareSolverr   : 容器内 ${FLARE_URL_IN_JACKETT}（宿主机 ${FLARE_BIND}:${FLARE_PORT}）
  配置卷         : ${JACKETT_CONFIG}
  Docker 网络    : ${DOCKER_NETWORK}

  本机 accounts.local.json 示例：
    "jackett": {
      "base_url": "http://${public_ip}:${JACKETT_PORT}",
      "api_key": "${api_key}",
      "indexers": {
        "tv": ["thepiratebay", "nyaasi"],
        "movie": ["yts"],
        "jp_tv": ["nyaasi", "thepiratebay"],
        "kr_tv": ["nyaasi", "thepiratebay"]
      }
    }

  Nyaa 回退（本机，非 VPS）：
    bash scripts/start_ssh_socks_tunnel.sh
    export TORRENT_PROXY=socks5h://127.0.0.1:1080

  请在 Jackett Dashboard 手动添加 Indexer（若尚未配置）：
    thepiratebay, nyaasi, eztv
    可选（需 FlareSolverr）：1337x, torrentgalaxyclone

  验证（在本机项目目录）：
    python -m workflow.torrent_sources.run status
================================================================================

EOF
}

main() {
  # 主流程
  [[ "$(id -u)" -eq 0 ]] || die "请用 root 执行（或 sudo bash）"

  log "开始安装 Jackett 栈 ..."
  ensure_docker
  ensure_network
  start_flaresolverr
  start_jackett
  wait_for_server_config
  configure_flaresolverr_in_jackett
  verify_stack
  print_summary
}

main "$@"
