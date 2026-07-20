#!/usr/bin/env bash
# =============================================================================
# 在 VPS 上写入默认 Jackett indexer 配置（华语 + 国际主源）。
#
# @file scripts/remote/configure_jackett_cn_indexers.sh
# @description
#   直接写入 Indexers/*.json 并重启 Jackett（Config API 需 Dashboard 登录）。
#   可由 install_jackett_oneclick.sh 交互调用；也可在 VPS 上手动执行。
#
# 用法（VPS 上 root 执行）：
#   bash configure_jackett_cn_indexers.sh
#   INDEXER_PROFILE=cn bash configure_jackett_cn_indexers.sh   # 仅华语
#   INDEXER_PROFILE=intl bash configure_jackett_cn_indexers.sh # 仅国际
# =============================================================================

set -euo pipefail

JACKETT_NAME="${JACKETT_NAME:-jackett}"
CONFIG_DIR="${JACKETT_CONFIG_DIR:-/opt/jackett/config/Jackett/Indexers}"
# all=华语+国际；cn=仅华语；intl=仅国际主源
INDEXER_PROFILE="${INDEXER_PROFILE:-all}"

log() {
  # 打印带前缀的日志
  echo "[configure-jackett-cn] $*"
}

write_indexer_json() {
  # 写入单个 indexer 的最小可用配置（sitelink + 占位字段）
  # @param $1 indexer id（文件名，不含 .json）
  # @param $2 站点首页 URL
  local name="$1"
  local sitelink="$2"
  python3 - "$CONFIG_DIR/${name}.json" "$sitelink" <<'PY'
import json, sys
path, link = sys.argv[1], sys.argv[2]
cfg = [
    {"id": "sitelink", "type": "inputstring", "name": "Site Link", "value": link},
    {"id": "cookieheader", "type": "hiddendata", "name": "CookieHeader", "value": None},
    {"id": "lasterror", "type": "hiddendata", "name": "LastError", "value": None},
    {"id": "tags", "type": "inputtags", "name": "Tags", "value": ""},
]
open(path, "w", encoding="utf-8").write(json.dumps(cfg, indent=2))
print("wrote", path)
PY
}

write_cn_indexers() {
  # 华语公开源
  write_indexer_json "dmhy" "https://share.dmhy.org/"
  write_indexer_json "mikan" "https://mikanani.me/"
  write_indexer_json "acgrip" "https://acg.rip/"
  write_indexer_json "bangumi-moe" "https://bangumi.moe/"
}

write_intl_indexers() {
  # 国际主源（1337x / tgx 依赖 FlareSolverr）
  write_indexer_json "thepiratebay" "https://thepiratebay.org/"
  write_indexer_json "nyaasi" "https://nyaa.si/"
  write_indexer_json "eztv" "https://eztvx.to/"
  write_indexer_json "1337x" "https://1337x.to/"
  write_indexer_json "torrentgalaxyclone" "https://torrentgalaxy.one/"
}

main() {
  # 按 PROFILE 写入 indexer 并重启 Jackett
  mkdir -p "${CONFIG_DIR}"
  log "INDEXER_PROFILE=${INDEXER_PROFILE}"

  case "${INDEXER_PROFILE}" in
    all)
      write_cn_indexers
      write_intl_indexers
      ;;
    cn)
      write_cn_indexers
      ;;
    intl)
      write_intl_indexers
      ;;
    *)
      echo "未知 INDEXER_PROFILE=${INDEXER_PROFILE}（支持 all|cn|intl）" >&2
      exit 1
      ;;
  esac

  log "重启 ${JACKETT_NAME} ..."
  docker restart "${JACKETT_NAME}"
  sleep 12
  log "完成。请在 Dashboard 对各 indexer 点 TEST 确认。"
}

main "$@"
