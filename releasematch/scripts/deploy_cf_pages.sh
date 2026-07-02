#!/usr/bin/env bash
# =============================================================================
# Cloudflare Pages 部署脚本（Direct Upload / Workers Assets）。
#
# @file scripts/deploy_cf_pages.sh
# @description
#   1. generate all — MySQL → portal/dist 内容页
#   2. 同步 Trust 壳、static、404、robots 到 dist
#   3. wrangler deploy — 上传 portal/dist
#
# 用法：
#   bash scripts/deploy_cf_pages.sh
#   bash scripts/deploy_cf_pages.sh --prepare-only   # 仅生成 dist，不上传
#   CF_PROJECT=releasematch bash scripts/deploy_cf_pages.sh
#
# 依赖：
#   python、wrangler（npm i -g wrangler 或 brew install wrangler）
#   wrangler login 或 CLOUDFLARE_API_TOKEN
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST="${PROJECT_ROOT}/portal/dist"
PORTAL="${PROJECT_ROOT}/portal"
PREPARE_ONLY=0
CF_PROJECT="${CF_PROJECT:-releasematch}"

usage() {
  cat <<'EOF'
用法: bash scripts/deploy_cf_pages.sh [选项]

选项:
  --prepare-only   仅 generate + 同步静态壳，不执行 wrangler deploy
  -h, --help       显示帮助

环境变量:
  CF_PROJECT       Cloudflare 项目名，默认 releasematch
  CLOUDFLARE_API_TOKEN  API Token（替代 wrangler login）
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --prepare-only) PREPARE_ONLY=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "未知参数: $1" >&2; usage; exit 1 ;;
    esac
  done
}

sync_static_shell() {
  # 将 Trust 四页、404、static 资源复制到 dist（index.html 由 generate all 生成）
  mkdir -p "${DIST}"

  for item in 404.html; do
    if [[ -f "${PORTAL}/${item}" ]]; then
      cp "${PORTAL}/${item}" "${DIST}/${item}"
    fi
  done

  if [[ -d "${PORTAL}/static" ]]; then
    rsync -a "${PORTAL}/static/" "${DIST}/static/"
  fi

  if [[ -d "${PORTAL}/trust" ]]; then
    rsync -a "${PORTAL}/trust/" "${DIST}/trust/"
  fi

  echo "[deploy] dist 静态壳已同步"
}

resolve_python() {
  # 优先使用项目 .venv，其次 python / python3
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    echo "${PROJECT_ROOT}/.venv/bin/python"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    echo "python3"
  fi
}

prepare_dist() {
  cd "${PROJECT_ROOT}"
  local py
  py="$(resolve_python)"
  echo "[deploy] generate all (${py}) ..."
  "${py}" -m workflow.run generate all
  sync_static_shell
  echo "[deploy] dist 文件数: $(find "${DIST}" -type f | wc -l | tr -d ' ')"
}

deploy_wrangler() {
  cd "${PROJECT_ROOT}"
  if ! command -v wrangler >/dev/null 2>&1; then
    echo "错误: 未找到 wrangler。请 npm i -g wrangler 或 brew install wrangler" >&2
    exit 1
  fi
  echo "[deploy] wrangler deploy (project=${CF_PROJECT}) ..."
  wrangler deploy
}

main() {
  parse_args "$@"
  prepare_dist
  if [[ "${PREPARE_ONLY}" -eq 1 ]]; then
    echo "[deploy] --prepare-only：跳过 wrangler deploy"
    exit 0
  fi
  deploy_wrangler
}

main "$@"
