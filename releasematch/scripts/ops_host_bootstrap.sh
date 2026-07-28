#!/usr/bin/env bash
# =============================================================================
# 运维机引导：按 docs/17 与 2026-07-28 实迁经验，幂等安装依赖 / systemd / cron。
#
# @file scripts/ops_host_bootstrap.sh
# @description
#   在**目标运维机**上、已 clone 到 PROJECT_ROOT 后执行。
#   默认 --dry-run 只打印；加 --apply 才改系统。
#
#   覆盖：
#     - apt：MariaDB client/server、sshpass、构建链（可选 libtorrent 头文件）
#     - Node 22 + wrangler（Debian 自带 Node 18 不够 wrangler 4）
#     - /var/log/releasematch
#     - releasematch-ops.service（仅 127.0.0.1:8090）
#     - crontab 托管块（测速 / 增量上传 / TMDB；增量默认**不**带 --prepare-only）
#
#   不覆盖（须人工 / 其它步骤）：
#     - MySQL dump/restore（方案 A）
#     - 写入 CLOUDFLARE_API_TOKEN（勿入库；本机编辑 .env）
#     - Jackett VPS 开通与 accounts 回写
#
# 用法：
#   cd PROJECT_ROOT   # …/releasematch/releasematch（含 wrangler.toml）
#   bash scripts/ops_host_bootstrap.sh                 # dry-run
#   bash scripts/ops_host_bootstrap.sh --apply
#   bash scripts/ops_host_bootstrap.sh --apply --with-wrangler --with-libtorrent
#
# 验收：
#   .venv/bin/python scripts/ops_host_migrate_verify.py
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPLY=0
WITH_WRANGLER=0
WITH_LIBTORRENT=0
OPS_HOST_LABEL="${OPS_HOST:-8.159.152.227}"

# crontab 托管标记（重复执行只替换本块）
CRON_BEGIN="# BEGIN ReleaseMatch ops-host managed"
CRON_END="# END ReleaseMatch ops-host managed"

usage() {
  # 完整注释：打印帮助
  cat <<'EOF'
用法: bash scripts/ops_host_bootstrap.sh [选项]

选项:
  --apply              真正执行（默认仅 dry-run）
  --with-wrangler      安装 Node 22 + wrangler（正式 CF 上传需要）
  --with-libtorrent    apt 头文件 + pip libtorrent（测速需要）
  -h, --help           帮助

环境变量:
  OPS_HOST             写入 crontab 注释用的主机名/IP（默认 8.159.152.227）
EOF
}

log() {
  # 完整注释：统一日志前缀
  printf '[ops-bootstrap] %s\n' "$*"
}

run() {
  # 完整注释：dry-run 打印，apply 执行
  if [[ "${APPLY}" -eq 1 ]]; then
    log "+ $*"
    "$@"
  else
    log "(dry-run) $*"
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --apply) APPLY=1; shift ;;
      --with-wrangler) WITH_WRANGLER=1; shift ;;
      --with-libtorrent) WITH_LIBTORRENT=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "未知参数: $1" >&2; usage; exit 1 ;;
    esac
  done
}

assert_project_root() {
  # 完整注释：防止在 git 根少一层目录执行导致 systemd 路径错误
  if [[ ! -f "${PROJECT_ROOT}/wrangler.toml" ]]; then
    echo "错误: 未在含 wrangler.toml 的 PROJECT_ROOT 执行（当前 ${PROJECT_ROOT}）" >&2
    echo "正确示例: /opt/releasematch/releasematch/releasematch" >&2
    exit 1
  fi
  if [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    echo "错误: 缺少 ${PROJECT_ROOT}/.venv ；请先 python3 -m venv .venv && pip install -r requirements.txt" >&2
    exit 1
  fi
  log "PROJECT_ROOT=${PROJECT_ROOT}"
}

install_apt() {
  # 完整注释：运维机基础包（方案 A 含 mariadb-server）
  local pkgs=(
    git curl ca-certificates
    python3 python3-venv python3-pip python3-dev
    build-essential pkg-config
    default-libmysqlclient-dev
    sshpass
    mariadb-server mariadb-client
  )
  if [[ "${WITH_LIBTORRENT}" -eq 1 ]]; then
    pkgs+=(libtorrent-rasterbar-dev)
  fi
  run sudo apt-get update
  run sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
}

install_libtorrent_pip() {
  # 完整注释：与 requirements.txt 钉版本对齐
  if [[ "${WITH_LIBTORRENT}" -ne 1 ]]; then
    return 0
  fi
  run "${PROJECT_ROOT}/.venv/bin/pip" install 'libtorrent==2.0.13'
  if [[ "${APPLY}" -eq 1 ]]; then
    "${PROJECT_ROOT}/.venv/bin/python" -c 'import libtorrent as lt; print(lt.version)'
  fi
}

install_node22_wrangler() {
  # 完整注释：Debian/Ubuntu 默认 Node 18 无法跑 wrangler 4；用 NodeSource 22.x
  if [[ "${WITH_WRANGLER}" -ne 1 ]]; then
    log "跳过 wrangler（未传 --with-wrangler）"
    return 0
  fi
  if command -v node >/dev/null 2>&1; then
    local major
    major="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
    if [[ "${major}" -ge 20 ]]; then
      log "node $(node -v) 已满足 wrangler 4"
    else
      log "node $(node -v) 过旧，安装 NodeSource 22.x"
      run bash -c 'curl -fsSL https://deb.nodesource.com/setup_22.x | bash -'
      run sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
    fi
  else
    run bash -c 'curl -fsSL https://deb.nodesource.com/setup_22.x | bash -'
    run sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
  fi
  run sudo npm i -g wrangler@4
  if [[ "${APPLY}" -eq 1 ]]; then
    wrangler --version || true
  fi
}

ensure_log_dir() {
  run sudo mkdir -p /var/log/releasematch
  run sudo chmod 755 /var/log/releasematch
}

write_systemd_unit() {
  # 完整注释：WorkingDirectory / ExecStart 必须指向三层 PROJECT_ROOT
  local unit=/etc/systemd/system/releasematch-ops.service
  local py="${PROJECT_ROOT}/.venv/bin/python"
  local tmp
  tmp="$(mktemp)"
  cat >"${tmp}" <<EOF
[Unit]
Description=ReleaseMatch Ops Console
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_ROOT}
ExecStart=${py} -u -m workflow.run ops serve --host 127.0.0.1 --port 8090
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
  if [[ "${APPLY}" -eq 1 ]]; then
    log "写入 ${unit}"
    sudo cp "${tmp}" "${unit}"
    sudo systemctl daemon-reload
    sudo systemctl enable --now releasematch-ops.service
    sudo systemctl status releasematch-ops.service --no-pager || true
  else
    log "(dry-run) 将写入 unit WorkingDirectory=${PROJECT_ROOT}"
    cat "${tmp}"
  fi
  rm -f "${tmp}"
}

write_crontab_managed() {
  # 完整注释：用 BEGIN/END 标记替换，避免重复追加；增量默认实际上传
  local block
  block="$(cat <<EOF
${CRON_BEGIN}
# ReleaseMatch 运维机 @ ${OPS_HOST_LABEL} — 全网唯一业务 cron
0 */6 * * * cd ${PROJECT_ROOT} && .venv/bin/python scripts/speedtest_batch_worker.py --all-published --write --workers 5 --target-bytes 262144 --report /var/log/releasematch/speedtest-batch.json >> /var/log/releasematch/speedtest-cron.log 2>&1
30 */6 * * * cd ${PROJECT_ROOT} && .venv/bin/python scripts/incremental_publish_worker.py --report /var/log/releasematch/incremental-publish.json >> /var/log/releasematch/incremental-publish-cron.log 2>&1
30 6 * * * cd ${PROJECT_ROOT} && .venv/bin/python -m workflow.run ops tmdb-sync >> /var/log/releasematch/tmdb-sync-cron.log 2>&1
${CRON_END}
EOF
)"
  if [[ "${APPLY}" -ne 1 ]]; then
    log "(dry-run) crontab 托管块："
    printf '%s\n' "${block}"
    return 0
  fi
  local existing filtered
  existing="$(crontab -l 2>/dev/null || true)"
  # 删旧托管块 + 历史散落的同名行（防双份）
  filtered="$(
    printf '%s\n' "${existing}" \
      | awk -v b="${CRON_BEGIN}" -v e="${CRON_END}" '
          $0==b {skip=1; next}
          $0==e {skip=0; next}
          skip {next}
          /speedtest_batch_worker|incremental_publish_worker|ops tmdb-sync/ {next}
          {print}
        '
  )"
  {
    printf '%s\n' "${filtered}"
    printf '%s\n' "${block}"
  } | crontab -
  log "crontab 已更新："
  crontab -l | sed -n "/${CRON_BEGIN}/,/${CRON_END}/p"
}

print_next_steps() {
  cat <<EOF

── 下一步（脚本未自动做）──
1) 方案 A 迁库（若尚未）：mysqldump → 本机 MariaDB → 改 .env 指向 127.0.0.1
   MariaDB root 走 TCP 时需设密码（应用不用 unix_socket）：
     sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '...'; FLUSH PRIVILEGES;"
2) 本地填写 CLOUDFLARE_API_TOKEN / ACCOUNT_ID（勿 git push；GitHub 会拦）
3) Jackett：servers + accounts 同指向现网 VPS；一键部署后确认 A4 回写 base_url
4) 验收：
     cd ${PROJECT_ROOT}
     .venv/bin/python scripts/ops_host_migrate_verify.py --expect-host ${OPS_HOST_LABEL}
5) 正式首传：先全量 generate / dist 非稀疏，再 wrangler（避免空 dist 对账删页）
6) 防双跑：旧 Mac + Jackett VPS 删除 speedtest/incremental/tmdb-sync cron

详见 docs/17-运维机迁移到服务器.md
EOF
}

main() {
  parse_args "$@"
  assert_project_root
  if [[ "${APPLY}" -eq 0 ]]; then
    log "模式=dry-run（加 --apply 才会改系统）"
  else
    log "模式=APPLY"
  fi
  install_apt
  install_libtorrent_pip
  install_node22_wrangler
  ensure_log_dir
  write_systemd_unit
  write_crontab_managed
  print_next_steps
}

main "$@"
