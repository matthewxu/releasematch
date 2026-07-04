#!/usr/bin/env bash
# =============================================================================
# C2 SEO 本地一键检查 — 包装 seo_c2_checklist.py（§6.1～6.3）。
#
# @file scripts/seo_c2_checklist.sh
# @description
#   默认检查 portal/dist/；加 --prepare 时先生成 dist 再检查。
#
# 用法：
#   bash scripts/seo_c2_checklist.sh
#   bash scripts/seo_c2_checklist.sh --prepare
#   bash scripts/seo_c2_checklist.sh --json
#   bash scripts/seo_c2_checklist.sh --prepare --no-db
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_python() {
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    echo "${PROJECT_ROOT}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}

PYTHON="$(resolve_python)"
exec "${PYTHON}" "${SCRIPT_DIR}/seo_c2_checklist.py" "$@"
