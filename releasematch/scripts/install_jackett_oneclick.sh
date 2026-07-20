#!/usr/bin/env bash
# =============================================================================
# 传入 VPS IP 与 SSH 密码，一键安装 Jackett + FlareSolverr，并同步 API Key。
#
# @file scripts/install_jackett_oneclick.sh
# @description
#   面向「刚买好 VPS」场景：只需 IP + 密码，无需先改 servers.local.json。
#   内部调用 deploy_jackett_vps.sh（装栈）、可选配置默认 indexer、sync API Key。
#
# 用法：
#   cd releasematch
#   bash scripts/install_jackett_oneclick.sh <IP> '<密码>'
#   bash scripts/install_jackett_oneclick.sh --host 1.2.3.4 --password 'secret'
#   bash scripts/install_jackett_oneclick.sh --host 1.2.3.4   # 交互输入密码
#   bash scripts/install_jackett_oneclick.sh --host 1.2.3.4 --with-indexers
#   bash scripts/install_jackett_oneclick.sh --host 1.2.3.4 --no-indexers
#
# 注意：密码含 & $ ! * 等字符时必须用单引号包裹，否则 shell 会拆命令。
#   错误: --password Release@2026&acb
#   正确: --password 'Release@2026&acb'
#
# 依赖：
#   ssh、scp、sshpass、python3；远端建议 Debian/Ubuntu（apt 装 Docker）
# =============================================================================

set -euo pipefail

# ── 路径 ────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="${SCRIPT_DIR}/deploy_jackett_vps.sh"
SYNC_SCRIPT="${SCRIPT_DIR}/sync_jackett_vps_key.sh"
INDEXERS_SCRIPT="${SCRIPT_DIR}/remote/configure_jackett_cn_indexers.sh"

# ── 默认参数 ────────────────────────────────────────────────

VPS_HOST=""
VPS_PASSWORD=""
VPS_USER="${VPS_USER:-root}"
VPS_PORT="${VPS_PORT:-22}"
# 新机默认强制重建容器，避免残留旧配置
FORCE_RECREATE="${FORCE_RECREATE:-1}"
# 安装成功后是否同步 API Key 到 accounts.local.json
DO_SYNC=1
DRY_RUN=0
# indexer：ask=交互询问（默认）；yes=强制写入；no=跳过
INDEXERS_MODE="ask"
# all | cn | intl —— 交互选择或 --indexer-profile 指定
INDEXER_PROFILE="${INDEXER_PROFILE:-all}"

# ── 辅助函数 ────────────────────────────────────────────────

usage() {
  # 打印帮助信息
  cat <<'EOF'
用法:
  bash scripts/install_jackett_oneclick.sh <IP> '<密码>' [选项]
  bash scripts/install_jackett_oneclick.sh --host <IP> --password '<密码>' [选项]
  bash scripts/install_jackett_oneclick.sh --host <IP>   # 交互输入密码 / 确认 indexer

在指定 VPS 上一键安装 Docker + Jackett + FlareSolverr，可选写入默认 indexer，并同步 API Key。

重要: 密码含 & $ ! 等特殊字符时必须用单引号，否则 shell 会拆开命令。
  错误示例: --password Release@2026&acb
  正确示例: --password 'Release@2026&acb'

位置参数:
  IP                   VPS 公网 IP 或域名
  密码                 root（或 --user）的 SSH 密码（建议单引号包裹）

选项:
  --host HOST          同位置参数 IP
  --password PASS      同位置参数密码（务必加单引号）
  --user USER          SSH 用户，默认 root
  --port PORT          SSH 端口，默认 22
  --with-indexers      跳过询问，直接写入默认 indexer
  --no-indexers        跳过询问，不配置 indexer
  --indexer-profile P  all（默认）| cn | intl
  --no-sync            安装后不同步 API Key
  --no-force           不强制重建已有容器（默认 FORCE_RECREATE=1）
  --dry-run            仅预览，不实际 SSH
  -h, --help           显示本帮助

环境变量:
  VPS_USER, VPS_PORT, FORCE_RECREATE, SSHPASS, INDEXER_PROFILE

示例:
  bash scripts/install_jackett_oneclick.sh --host 203.0.113.10
  bash scripts/install_jackett_oneclick.sh 203.0.113.10 'MyPass@2026&acb' --with-indexers
  bash scripts/install_jackett_oneclick.sh --host 203.0.113.10 --no-indexers --no-sync
EOF
}

die() {
  # 打印错误并退出
  echo "错误: $*" >&2
  exit 1
}

parse_args() {
  # 解析位置参数与选项；支持 <IP> <密码> 或 --host / --password
  local positional=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        [[ $# -ge 2 ]] || die "--host 需要参数"
        VPS_HOST="$2"
        shift 2
        ;;
      --password)
        [[ $# -ge 2 ]] || die "--password 需要参数"
        VPS_PASSWORD="$2"
        shift 2
        ;;
      --user)
        [[ $# -ge 2 ]] || die "--user 需要参数"
        VPS_USER="$2"
        shift 2
        ;;
      --port)
        [[ $# -ge 2 ]] || die "--port 需要参数"
        VPS_PORT="$2"
        shift 2
        ;;
      --with-indexers)
        INDEXERS_MODE="yes"
        shift
        ;;
      --no-indexers)
        INDEXERS_MODE="no"
        shift
        ;;
      --indexer-profile)
        [[ $# -ge 2 ]] || die "--indexer-profile 需要参数（all|cn|intl）"
        INDEXER_PROFILE="$2"
        shift 2
        ;;
      --no-sync)
        DO_SYNC=0
        shift
        ;;
      --no-force)
        FORCE_RECREATE=0
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --)
        shift
        positional+=("$@")
        break
        ;;
      -*)
        die "未知选项: $1（见 --help）"
        ;;
      *)
        positional+=("$1")
        shift
        ;;
    esac
  done

  # 位置参数：第 1 个为 IP，第 2 个为密码（未被 --host/--password 覆盖时）
  if [[ ${#positional[@]} -ge 1 && -z "${VPS_HOST}" ]]; then
    VPS_HOST="${positional[0]}"
  fi
  if [[ ${#positional[@]} -ge 2 && -z "${VPS_PASSWORD}" ]]; then
    VPS_PASSWORD="${positional[1]}"
  fi
  if [[ ${#positional[@]} -gt 2 ]]; then
    die "多余位置参数: ${positional[*]:2}"
  fi

  case "${INDEXER_PROFILE}" in
    all|cn|intl) ;;
    *) die "无效 --indexer-profile=${INDEXER_PROFILE}（支持 all|cn|intl）" ;;
  esac

  # 未在命令行提供密码时：优先用已有 SSHPASS，否则交互输入（避免 & 被 shell 拆开）
  if [[ -z "${VPS_PASSWORD}" && -n "${SSHPASS:-}" ]]; then
    VPS_PASSWORD="${SSHPASS}"
  fi
}

prompt_password_if_needed() {
  # 无密码时从终端静默读取，避免命令行中的 & $ 等元字符问题
  if [[ -n "${VPS_PASSWORD}" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    die "未提供密码，且当前非交互终端。请用 --password '...' 或 export SSHPASS=..."
  fi
  # -s 不回显；-r 保留反斜杠
  read -r -s -p "SSH 密码 (${VPS_USER}@${VPS_HOST}): " VPS_PASSWORD
  echo
  [[ -n "${VPS_PASSWORD}" ]] || die "密码不能为空"
}

prompt_indexers_if_needed() {
  # 交互询问是否写入默认 indexer，以及选用哪套 profile
  if [[ "${INDEXERS_MODE}" == "yes" || "${INDEXERS_MODE}" == "no" ]]; then
    return 0
  fi

  if [[ ! -t 0 ]]; then
    # 非交互终端且未指定时默认跳过，避免挂起
    echo "非交互终端：未指定 --with-indexers/--no-indexers，跳过 indexer 配置"
    INDEXERS_MODE="no"
    return 0
  fi

  echo
  echo "=== 默认 Indexer 配置 ==="
  echo "将写入 Jackett Indexers/*.json 并重启容器。"
  echo "  all  = 华语(dmhy/mikan/acgrip/bangumi-moe) + 国际(TPB/nyaasi/eztv/1337x/tgx)"
  echo "  cn   = 仅华语"
  echo "  intl = 仅国际"
  echo
  local ans profile_ans
  read -r -p "是否配置默认 indexer？[Y/n] " ans
  case "${ans}" in
    ""|[Yy]|[Yy][Ee][Ss])
      INDEXERS_MODE="yes"
      read -r -p "Indexer 套件 [all/cn/intl]（默认 ${INDEXER_PROFILE}）: " profile_ans
      if [[ -n "${profile_ans}" ]]; then
        case "${profile_ans}" in
          all|cn|intl) INDEXER_PROFILE="${profile_ans}" ;;
          *)
            echo "无效输入，使用 ${INDEXER_PROFILE}"
            ;;
        esac
      fi
      ;;
    *)
      INDEXERS_MODE="no"
      echo "已跳过 indexer 配置"
      ;;
  esac
}

check_deps() {
  # 检查本机依赖：ssh / scp / sshpass / 子脚本
  command -v ssh >/dev/null 2>&1 || die "未找到 ssh，请先安装 OpenSSH 客户端"
  command -v scp >/dev/null 2>&1 || die "未找到 scp"
  command -v sshpass >/dev/null 2>&1 || die "未找到 sshpass。macOS: brew install hudochenkov/sshpass/sshpass"
  [[ -f "${DEPLOY_SCRIPT}" ]] || die "找不到 ${DEPLOY_SCRIPT}"
  [[ -f "${INDEXERS_SCRIPT}" ]] || die "找不到 ${INDEXERS_SCRIPT}"
  if [[ "${DO_SYNC}" -eq 1 ]]; then
    [[ -f "${SYNC_SCRIPT}" ]] || die "找不到 ${SYNC_SCRIPT}"
  fi
}

ssh_base_args() {
  # 填充 SSH/SCP 共用连接参数到全局数组 SSH_CONN_ARGS
  SSH_CONN_ARGS=(-p "${VPS_PORT}" -o StrictHostKeyChecking=no -o ConnectTimeout=20)
}

run_install() {
  # 调用 deploy_jackett_vps.sh 在远端安装 Jackett 栈
  local deploy_args=(--host "${VPS_HOST}" --user "${VPS_USER}" --port "${VPS_PORT}")
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    deploy_args+=(--dry-run)
  fi

  echo "=== 一键安装 Jackett + FlareSolverr ==="
  echo "目标: ${VPS_USER}@${VPS_HOST}:${VPS_PORT}"
  echo "FORCE_RECREATE=${FORCE_RECREATE}  sync_api_key=${DO_SYNC}  indexers=${INDEXERS_MODE}/${INDEXER_PROFILE}"
  echo

  export SSHPASS="${VPS_PASSWORD}"
  export FORCE_RECREATE

  FORCE_RECREATE="${FORCE_RECREATE}" bash "${DEPLOY_SCRIPT}" "${deploy_args[@]}"
}

run_configure_indexers() {
  # 将 configure_jackett_cn_indexers.sh 推到远端执行
  if [[ "${INDEXERS_MODE}" != "yes" ]]; then
    echo "=== 已跳过默认 indexer 配置 ==="
    return 0
  fi

  echo
  echo "=== 配置默认 Indexer（profile=${INDEXER_PROFILE}）==="

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] scp ${INDEXERS_SCRIPT} → ${VPS_USER}@${VPS_HOST}:/tmp/"
    echo "[dry-run] ssh INDEXER_PROFILE=${INDEXER_PROFILE} bash /tmp/configure_jackett_cn_indexers.sh"
    return 0
  fi

  export SSHPASS="${VPS_PASSWORD}"
  local remote_tmp="/tmp/configure_jackett_cn_indexers.sh"
  ssh_base_args

  sshpass -e scp "${SSH_CONN_ARGS[@]}" "${INDEXERS_SCRIPT}" "${VPS_USER}@${VPS_HOST}:${remote_tmp}"
  sshpass -e ssh -T "${SSH_CONN_ARGS[@]}" "${VPS_USER}@${VPS_HOST}" \
    "INDEXER_PROFILE='${INDEXER_PROFILE}' bash '${remote_tmp}'"

  echo "Indexer 配置完成。Dashboard: http://${VPS_HOST}:9117/UI/Dashboard"
}

run_sync_key() {
  # 安装成功后把远端 API Key 写入 accounts.local.json
  if [[ "${DO_SYNC}" -ne 1 ]]; then
    echo "=== 已跳过 API Key 同步（--no-sync）==="
    return 0
  fi
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] 将执行: bash scripts/sync_jackett_vps_key.sh --host ${VPS_HOST}"
    return 0
  fi

  echo
  echo "=== 同步 Jackett API Key → accounts.local.json ==="
  export SSHPASS="${VPS_PASSWORD}"
  bash "${SYNC_SCRIPT}" --host "${VPS_HOST}" --user "${VPS_USER}" --port "${VPS_PORT}"
}

print_next_steps() {
  # 打印安装完成后的访问与后续步骤
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    return 0
  fi
  cat <<EOF

=== 安装完成 ===
Dashboard:  http://${VPS_HOST}:9117/UI/Dashboard
Torznab:    http://${VPS_HOST}:9117
FlareSolverr 仅监听 VPS 本机 127.0.0.1:8191（不暴露公网）

建议: 在 Dashboard 对已添加 indexer 逐个点 TEST（1337x/tgx 需 FlareSolverr）。
本机 Nyaa/DMHy SOCKS: bash scripts/start_ssh_socks_tunnel.sh
EOF
}

main() {
  # 入口：解析 → 密码 → 询问 indexer → 安装 → 写 indexer → 同步 Key
  parse_args "$@"

  [[ -n "${VPS_HOST}" ]] || die "请传入 IP（位置参数或 --host）"
  prompt_password_if_needed
  prompt_indexers_if_needed

  check_deps
  run_install
  run_configure_indexers
  run_sync_key
  print_next_steps
}

main "$@"
