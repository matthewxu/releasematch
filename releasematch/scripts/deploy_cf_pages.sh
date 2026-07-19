#!/usr/bin/env bash
# =============================================================================
# Cloudflare Workers Assets 部署脚本（全量 / 增量 / 仅上传）。
#
# @file scripts/deploy_cf_pages.sh
# @description
#   1. prepare：MySQL → portal/dist（full 或 incremental）
#   2. 可选 wrangler deploy（CF 侧按文件 hash 增量上传，缺文件则对账删除）
#
# 用法：
#   bash scripts/deploy_cf_pages.sh
#       # 默认：全量 prepare + wrangler
#   bash scripts/deploy_cf_pages.sh --prepare-only
#       # 全量 prepare，不上传
#   bash scripts/deploy_cf_pages.sh --mode incremental --page-ids tv:1668:s01e01,movie:244786
#       # 增量 bake 指定槽 + home/sitemap + wrangler
#   bash scripts/deploy_cf_pages.sh --mode upload-only
#       # 仅 wrangler（假定 dist 已就绪）
#
# 依赖：项目 .venv、wrangler、CLOUDFLARE_API_TOKEN 或 wrangler login
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST="${PROJECT_ROOT}/portal/dist"
PREPARE_ONLY=0
# 完整注释：full | incremental | upload-only
MODE="full"
# 完整注释：增量模式下的 page_id 列表（逗号分隔）
PAGE_IDS=""
CF_PROJECT="${CF_PROJECT:-releasematch}"

usage() {
  cat <<'EOF'
用法: bash scripts/deploy_cf_pages.sh [选项]

选项:
  --mode MODE          full（默认）| incremental | upload-only
  --page-ids IDS       增量模式必填，逗号分隔 page_id
  --prepare-only       只准备 dist，不执行 wrangler deploy
  -h, --help           显示帮助

环境变量:
  CF_PROJECT           Cloudflare 项目名，默认 releasematch
  CLOUDFLARE_API_TOKEN API Token（替代 wrangler login）
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --prepare-only) PREPARE_ONLY=1; shift ;;
      --mode)
        MODE="${2:-}"; shift 2
        ;;
      --mode=*)
        MODE="${1#*=}"; shift
        ;;
      --page-ids)
        PAGE_IDS="${2:-}"; shift 2
        ;;
      --page-ids=*)
        PAGE_IDS="${1#*=}"; shift
        ;;
      -h|--help) usage; exit 0 ;;
      *) echo "未知参数: $1" >&2; usage; exit 1 ;;
    esac
  done
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

sync_static_shell() {
  # 同步 404/410 与 static；Trust 页由 generate 写入 dist
  local py
  py="$(resolve_python)"
  "${py}" -c "from portal.generator.static_shell import sync_static_shell; sync_static_shell()"
  echo "[deploy] dist 静态壳已同步"
}

prepare_full() {
  # 全量 generate all（含 home / hubs / sitemap / 壳）
  cd "${PROJECT_ROOT}"
  local py
  py="$(resolve_python)"
  echo "[deploy] generate all (${py}) ..."
  "${py}" -m workflow.run generate all
  sync_static_shell
  echo "[deploy] dist 文件数: $(find "${DIST}" -type f | wc -l | tr -d ' ')"
}

prepare_incremental() {
  # 增量：仅 bake 指定 page_id + home + sitemap + 壳（经 Ops actions 同源逻辑）
  cd "${PROJECT_ROOT}"
  local py
  py="$(resolve_python)"
  if [[ -z "${PAGE_IDS}" ]]; then
    echo "错误: --mode incremental 需要 --page-ids" >&2
    exit 1
  fi
  echo "[deploy] incremental prepare page_ids=${PAGE_IDS}"
  "${py}" - <<PY
from workflow.ops.actions import _prepare_dist_incremental
from workflow.ops.track_store import load_active_batch, save_batch

ids = [p.strip() for p in "${PAGE_IDS}".split(",") if p.strip()]
batch = load_active_batch()
batch_id = (batch or {}).get("meta", {}).get("batch_id") if batch else None
# 无活跃批次时仍可按 page_ids 直写：临时构造最小批次语义由 generate page 覆盖
if not batch_id:
    from portal.generator.generate_one import (
        DEFAULT_OUT_ROOT,
        write_page_html,
        write_home_page,
    )
    from portal.generator.sitemap import write_sitemap
    from portal.generator.static_shell import sync_static_shell
    fails = []
    for pid in ids:
        out = write_page_html(page_id=pid)
        if not out.get("ok", True):
            fails.append(pid)
        print(out)
    write_home_page()
    write_sitemap(DEFAULT_OUT_ROOT)
    sync_static_shell()
    if fails:
        raise SystemExit(f"incremental failed: {fails}")
else:
    out = _prepare_dist_incremental(batch_id=batch_id, page_ids=ids)
    print(out)
    if not out.get("ok"):
        raise SystemExit(out.get("error") or "incremental prepare failed")
PY
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
  case "${MODE}" in
    full|incremental|upload-only|upload_only) ;;
    *)
      echo "错误: --mode 应为 full|incremental|upload-only" >&2
      exit 1
      ;;
  esac
  # 统一别名
  if [[ "${MODE}" == "upload_only" ]]; then
    MODE="upload-only"
  fi

  if [[ "${MODE}" == "full" ]]; then
    prepare_full
  elif [[ "${MODE}" == "incremental" ]]; then
    prepare_incremental
  else
    echo "[deploy] upload-only：跳过 prepare，使用现有 ${DIST}"
    if [[ ! -d "${DIST}" ]]; then
      echo "错误: dist 不存在，请先 prepare" >&2
      exit 1
    fi
  fi

  if [[ "${PREPARE_ONLY}" -eq 1 ]]; then
    echo "[deploy] --prepare-only：跳过 wrangler deploy"
    exit 0
  fi
  deploy_wrangler
}

main "$@"
