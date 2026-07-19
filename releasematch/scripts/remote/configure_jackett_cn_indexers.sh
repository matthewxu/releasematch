#!/usr/bin/env bash
# =============================================================================
# 在 VPS 上写入 dmhy / 1337x / torrentgalaxyclone 的 Jackett indexer 配置。
#
# @file scripts/remote/configure_jackett_cn_indexers.sh
# @description
#   直接写入 Indexers/*.json 并重启 Jackett（Config API 需 Dashboard 登录）。
#   华语 PoC 依赖：thepiratebay + 1337x + torrentgalaxyclone + dmhy。
#
# 用法（VPS 上 root 执行）：
#   bash configure_jackett_cn_indexers.sh
# =============================================================================

set -euo pipefail

JACKETT_NAME="${JACKETT_NAME:-jackett}"
CONFIG_DIR="${JACKETT_CONFIG_DIR:-/opt/jackett/config/Jackett/Indexers}"

log() {
  echo "[configure-jackett-cn] $*"
}

write_indexer_json() {
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

main() {
  mkdir -p "${CONFIG_DIR}"
  write_indexer_json "dmhy" "https://share.dmhy.org/"
  write_indexer_json "1337x" "https://1337x.to/"
  write_indexer_json "torrentgalaxyclone" "https://torrentgalaxy.one/"
  write_indexer_json "mikan" "https://mikanani.me/"
  write_indexer_json "acgrip" "https://acg.rip/"
  write_indexer_json "bangumi-moe" "https://bangumi.moe/"
  log "重启 ${JACKETT_NAME} ..."
  docker restart "${JACKETT_NAME}"
  sleep 12
  log "完成。请在 Dashboard 对各 indexer 点 TEST 确认。"
}

main "$@"
