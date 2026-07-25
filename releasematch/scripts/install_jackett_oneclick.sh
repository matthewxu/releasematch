#!/usr/bin/env bash
# =============================================================================
# 一键安装 Jackett + FlareSolverr；可选集成 Linode 购买 / 销毁 VPS。
#
# @file scripts/install_jackett_oneclick.sh
# @description
#   面向「已有 VPS」或「用 linode.local.json 自动开机关机」两种场景：
#   1) 传统：--host + --password → 装栈 / indexer / 同步 Key
#   2) 开通：--provision-linode → 调用 linode_vps.py create → 再装 Jackett
#   3) 销毁：--destroy-linode → 调用 linode_vps.py delete（不装机）
#
# 用法：
#   cd releasematch
#   bash scripts/install_jackett_oneclick.sh <IP> '<密码>'
#   bash scripts/install_jackett_oneclick.sh --host 1.2.3.4 --password 'secret'
#   bash scripts/install_jackett_oneclick.sh --provision-linode --with-indexers
#   bash scripts/install_jackett_oneclick.sh --destroy-linode
#
# 注意：密码含 & $ ! * 等字符时必须用单引号包裹，否则 shell 会拆命令。
#   错误: --password Release@2026&acb
#   正确: --password 'Release@2026&acb'
#
# 依赖：
#   ssh、sshpass、python3；Linode 模式另需 linode_api4（见 requirements-linode.txt）
#   远端建议 Debian/Ubuntu（apt 装 Docker）
# =============================================================================

set -euo pipefail

# ── 路径 ────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_SCRIPT="${SCRIPT_DIR}/deploy_jackett_vps.sh"
SYNC_SCRIPT="${SCRIPT_DIR}/sync_jackett_vps_key.sh"
INDEXERS_SCRIPT="${SCRIPT_DIR}/remote/configure_jackett_cn_indexers.sh"
LINODE_SCRIPT="${PROJECT_ROOT}/workflow/torrent_sources/linode_vps.py"
LINODE_LOCAL="${PROJECT_ROOT}/workflow/torrent_sources/linode.local.json"
LINODE_REQ="${PROJECT_ROOT}/workflow/torrent_sources/requirements-linode.txt"
SERVERS_LOCAL="${PROJECT_ROOT}/workflow/torrent_sources/servers.local.json"

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

# Linode 集成（label 默认来自 linode.local.json → defaults.label，不在此写死）
PROVISION_LINODE=0
DESTROY_LINODE=0
LINODE_LABEL="${LINODE_LABEL:-}"
LINODE_ID=""
LINODE_CONFIG=""
# 开通成功后是否回写 servers.local.json 的 host / 密码 / URL
UPDATE_SERVERS_LOCAL=1
# servers.local.json 中目标条目 key
SERVERS_ENTRY_KEY="${SERVERS_ENTRY_KEY:-jackett_vps_japan}"
# create 返回的实例 id（供收尾打印）
LINODE_CREATED_ID=""

# ── 辅助函数 ────────────────────────────────────────────────

usage() {
  # 打印帮助信息
  cat <<'EOF'
用法:
  bash scripts/install_jackett_oneclick.sh <IP> '<密码>' [选项]
  bash scripts/install_jackett_oneclick.sh --host <IP> --password '<密码>' [选项]
  bash scripts/install_jackett_oneclick.sh --provision-linode [选项]
  bash scripts/install_jackett_oneclick.sh --destroy-linode [--linode-label LABEL|--linode-id ID]

在指定 VPS 上一键安装 Docker + Jackett + FlareSolverr，可选写入默认 indexer，并同步 API Key。
也可通过 linode.local.json 自动购买 / 销毁 Linode VPS（见 docs/linode-vps-lifecycle.md）。
实例 label / 规格 / SSH 密码以 workflow/torrent_sources/linode.local.json 为准（由 linode_vps.py 读取）。

重要: 密码含 & $ ! 等特殊字符时必须用单引号，否则 shell 会拆开命令。
  错误示例: --password Release@2026&acb
  正确示例: --password 'Release@2026&acb'

位置参数:
  IP                   VPS 公网 IP 或域名（--provision-linode 时可不传）
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
  --dry-run            仅预览，不实际 SSH / 不调 Linode API

Linode（读 workflow/torrent_sources/linode.local.json；create/delete 委托 linode_vps.py）:
  --provision-linode   先按配置购买 VPS，再用返回的 IP/密码安装 Jackett
  --destroy-linode     仅销毁 VPS（不安装）；label 默认取自 linode.local.json
  --linode-label NAME  覆盖 config.defaults.label（一般不必传）
  --linode-id ID       实例数字 ID（销毁时优先于 label）
  --linode-config PATH 指定 linode.local.json（默认自动查找）
  --no-update-servers  开通后不回写 servers.local.json
  --servers-key KEY    servers.local.json 条目名，默认 jackett_vps_japan

  -h, --help           显示本帮助

环境变量:
  VPS_USER, VPS_PORT, FORCE_RECREATE, SSHPASS, INDEXER_PROFILE, LINODE_LABEL

示例:
  # 已有 VPS
  bash scripts/install_jackett_oneclick.sh --host 203.0.113.10
  bash scripts/install_jackett_oneclick.sh 203.0.113.10 'MyPass@2026&acb' --with-indexers

  # 购买日本 Nanode + 装 Jackett（label/密码取自 linode.local.json）
  bash scripts/install_jackett_oneclick.sh --provision-linode --with-indexers

  # 销毁（label 默认读 linode.local.json → defaults.label）
  bash scripts/install_jackett_oneclick.sh --destroy-linode
EOF
}

die() {
  # 打印错误并退出
  echo "错误: $*" >&2
  exit 1
}

resolve_python() {
  # 优先项目 .venv，否则系统 python3
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    echo "${PROJECT_ROOT}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    die "未找到 python3"
  fi
}

parse_args() {
  # 解析位置参数与选项；支持 <IP> <密码> 或 --host / --password / Linode 开关
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
      --provision-linode)
        PROVISION_LINODE=1
        shift
        ;;
      --destroy-linode)
        DESTROY_LINODE=1
        shift
        ;;
      --linode-label)
        [[ $# -ge 2 ]] || die "--linode-label 需要参数"
        LINODE_LABEL="$2"
        shift 2
        ;;
      --linode-id)
        [[ $# -ge 2 ]] || die "--linode-id 需要参数"
        LINODE_ID="$2"
        shift 2
        ;;
      --linode-config)
        [[ $# -ge 2 ]] || die "--linode-config 需要参数"
        LINODE_CONFIG="$2"
        shift 2
        ;;
      --no-update-servers)
        UPDATE_SERVERS_LOCAL=0
        shift
        ;;
      --servers-key)
        [[ $# -ge 2 ]] || die "--servers-key 需要参数"
        SERVERS_ENTRY_KEY="$2"
        shift 2
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

  if [[ "${PROVISION_LINODE}" -eq 1 && "${DESTROY_LINODE}" -eq 1 ]]; then
    die "--provision-linode 与 --destroy-linode 不能同时使用"
  fi

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
    die "未提供密码，且当前非交互终端。请用 --password '...' 或 export SSHPASS=...；或使用 --provision-linode（读 linode.local.json）"
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
  # 检查本机依赖：ssh / sshpass / 子脚本（indexer 经 SSH stdin 推送，无需 scp）
  command -v ssh >/dev/null 2>&1 || die "未找到 ssh，请先安装 OpenSSH 客户端"
  command -v sshpass >/dev/null 2>&1 || die "未找到 sshpass。macOS: brew install hudochenkov/sshpass/sshpass"
  [[ -f "${DEPLOY_SCRIPT}" ]] || die "找不到 ${DEPLOY_SCRIPT}"
  [[ -f "${INDEXERS_SCRIPT}" ]] || die "找不到 ${INDEXERS_SCRIPT}"
  if [[ "${DO_SYNC}" -eq 1 ]]; then
    [[ -f "${SYNC_SCRIPT}" ]] || die "找不到 ${SYNC_SCRIPT}"
  fi
}

check_linode_deps() {
  # 检查 Linode 脚本与 SDK
  [[ -f "${LINODE_SCRIPT}" ]] || die "找不到 ${LINODE_SCRIPT}"
  local py
  py="$(resolve_python)"
  if ! "${py}" -c "import linode_api4" 2>/dev/null; then
    die "未安装 linode_api4。请执行: ${py} -m pip install -r ${LINODE_REQ}"
  fi
  if [[ -n "${LINODE_CONFIG}" ]]; then
    [[ -f "${LINODE_CONFIG}" ]] || die "找不到 --linode-config ${LINODE_CONFIG}"
  elif [[ ! -f "${LINODE_LOCAL}" && -z "${LINODE_TOKEN:-}" ]]; then
    die "缺少 ${LINODE_LOCAL}（或设置 LINODE_TOKEN）。模板: linode.example.json"
  fi
}

linode_cli() {
  # 调用 linode_vps.py；参数原样追加
  local py cfg_args=()
  py="$(resolve_python)"
  if [[ -n "${LINODE_CONFIG}" ]]; then
    cfg_args+=(--config "${LINODE_CONFIG}")
  fi
  "${py}" "${LINODE_SCRIPT}" "${cfg_args[@]}" "$@"
}

ensure_linode_label() {
  # label 唯一真相源：linode.local.json → defaults.label（经 linode_vps.py defaults 输出）
  # CLI --linode-label / 环境变量 LINODE_LABEL 可覆盖
  if [[ -n "${LINODE_LABEL}" ]]; then
    return 0
  fi
  local out py
  py="$(resolve_python)"
  out="$(linode_cli defaults --json)" || die "无法读取 linode defaults（检查 linode.local.json）"
  LINODE_LABEL="$(printf '%s\n' "${out}" | "${py}" -c "import sys,json; d=json.load(sys.stdin); print((d.get('label') or '').strip())")"
  [[ -n "${LINODE_LABEL}" ]] || die "linode.local.json 未配置 defaults.label，请填写或传 --linode-label"
  echo "使用配置 label=${LINODE_LABEL}（来自 linode.local.json / linode_vps.py defaults）"
}

ssh_conn_args() {
  # 填充 ssh 连接参数（端口用小写 -p）
  SSH_CONN_ARGS=(-p "${VPS_PORT}" -o StrictHostKeyChecking=no -o ConnectTimeout=20)
}

wait_for_ssh() {
  # 新购 VPS 等待 cloud-init / sshd 就绪
  local i max_tries=36
  echo "=== 等待 SSH 就绪（最多 $((max_tries * 5))s）==="
  export SSHPASS="${VPS_PASSWORD}"
  ssh_conn_args
  for i in $(seq 1 "${max_tries}"); do
    if sshpass -e ssh -T "${SSH_CONN_ARGS[@]}" "${VPS_USER}@${VPS_HOST}" "true" 2>/dev/null; then
      echo "SSH 已通（第 ${i} 次探测）"
      return 0
    fi
    sleep 5
  done
  die "SSH 等待超时：${VPS_USER}@${VPS_HOST}:${VPS_PORT}"
}

update_servers_local_after_provision() {
  # 把新 IP / 密码 / public_url 写回 servers.local.json（若存在）
  if [[ "${UPDATE_SERVERS_LOCAL}" -ne 1 ]]; then
    echo "=== 已跳过 servers.local.json 回写（--no-update-servers）==="
    return 0
  fi
  if [[ ! -f "${SERVERS_LOCAL}" ]]; then
    echo "提示: 无 ${SERVERS_LOCAL}，跳过回写"
    return 0
  fi
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] 将更新 ${SERVERS_LOCAL} key=${SERVERS_ENTRY_KEY} host=${VPS_HOST}"
    return 0
  fi

  local py
  py="$(resolve_python)"
  HOST="${VPS_HOST}" VPS_PASS="${VPS_PASSWORD}" VPS_SSH_USER="${VPS_USER}" VPS_SSH_PORT="${VPS_PORT}" \
  KEY="${SERVERS_ENTRY_KEY}" SERVERS_JSON="${SERVERS_LOCAL}" \
  "${py}" - <<'PY'
"""将开通后的 host/密码写回 servers.local.json 对应条目。"""
import json
import os
from pathlib import Path

path = Path(os.environ["SERVERS_JSON"])
key = os.environ["KEY"]
host = os.environ["HOST"]
password = os.environ["VPS_PASS"]
user = os.environ.get("VPS_SSH_USER") or "root"
port = int(os.environ.get("VPS_SSH_PORT") or "22")

data = json.loads(path.read_text(encoding="utf-8"))
if key not in data or not isinstance(data[key], dict):
    data[key] = {"_comment": "由 install_jackett_oneclick.sh --provision-linode 创建"}
entry = data[key]
entry["host"] = host
entry.setdefault("label", "日本测试服务器")
entry.setdefault("os", "Debian 12")
ssh = entry.setdefault("ssh", {})
if not isinstance(ssh, dict):
    ssh = {}
    entry["ssh"] = ssh
ssh["user"] = user
ssh["password"] = password
ssh["port"] = port

services = entry.setdefault("services", {})
if isinstance(services, dict):
    jackett = services.setdefault("jackett", {})
    if isinstance(jackett, dict):
        jackett["public_url"] = f"http://{host}:9117"
        jackett["dashboard_url"] = f"http://{host}:9117/UI/Dashboard"
    socks = services.get("ssh_socks_tunnel")
    if isinstance(socks, dict):
        socks["command"] = f"ssh -N -D 127.0.0.1:1080 {user}@{host}"

path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"已更新 {path} → {key}.host={host}")
PY
}

run_provision_linode() {
  # 调用 linode_vps.py create（不传 --label 时由 config.defaults.label 决定）
  ensure_linode_label
  echo "=== Linode 购买 VPS（label=${LINODE_LABEL}，via linode_vps.py）==="
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] linode_vps.py create --json --label ${LINODE_LABEL}"
    VPS_HOST="${VPS_HOST:-203.0.113.10}"
    VPS_PASSWORD="${VPS_PASSWORD:-dry-run-password}"
    LINODE_CREATED_ID="0"
    return 0
  fi

  # 同 label 已存在则拒绝，避免 delete --label 歧义
  local existing
  if existing="$(linode_cli ip --label "${LINODE_LABEL}" --json 2>/dev/null)" \
    && printf '%s' "${existing}" | grep -q '"ok":true'; then
    die "label=${LINODE_LABEL} 已存在（$(printf '%s' "${existing}" | "$(resolve_python)" -c "import sys,json; d=json.load(sys.stdin); print(d.get('ipv4') or d.get('id'))" 2>/dev/null || true)）。请先: bash scripts/install_jackett_oneclick.sh --destroy-linode"
  fi

  local out ipv4 pass iid
  # 显式传 --label，与 ensure 后的配置值一致（仍由 linode.local.json 决定）
  if ! out="$(linode_cli create --json --label "${LINODE_LABEL}" 2>/dev/null)"; then
    linode_cli create --json --label "${LINODE_LABEL}" || true
    die "Linode create 失败"
  fi

  local py
  py="$(resolve_python)"
  ipv4="$(printf '%s\n' "${out}" | "${py}" -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok'), d; print(d['ipv4'])")"
  pass="$(printf '%s\n' "${out}" | "${py}" -c "import sys,json; d=json.load(sys.stdin); print(d.get('root_pass') or '')")"
  iid="$(printf '%s\n' "${out}" | "${py}" -c "import sys,json; d=json.load(sys.stdin); print(d.get('id') or '')")"

  [[ -n "${ipv4}" ]] || die "create 未返回 ipv4: ${out}"
  [[ -n "${pass}" ]] || die "create 未返回 root_pass（请在 linode.local.json defaults.ssh.password 配置）"

  VPS_HOST="${ipv4}"
  VPS_PASSWORD="${pass}"
  LINODE_CREATED_ID="${iid}"
  echo "已创建 id=${iid} ipv4=${ipv4} label=${LINODE_LABEL}"
  update_servers_local_after_provision
  wait_for_ssh
}

run_destroy_linode() {
  # 调用 linode_vps.py delete；无 --linode-id 时 label 来自配置
  if [[ -z "${LINODE_ID}" ]]; then
    ensure_linode_label
  fi
  echo "=== Linode 销毁 VPS（via linode_vps.py）==="
  local del_args=(delete --yes --json)
  if [[ -n "${LINODE_ID}" ]]; then
    del_args+=(--id "${LINODE_ID}")
    echo "目标: id=${LINODE_ID}"
  else
    del_args+=(--label "${LINODE_LABEL}")
    echo "目标: label=${LINODE_LABEL}"
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] linode_vps.py ${del_args[*]}"
    return 0
  fi

  if [[ -t 0 ]]; then
    local ans
    read -r -p "确认销毁上述 Linode？不可恢复 [y/N] " ans
    case "${ans}" in
      [Yy]|[Yy][Ee][Ss]) ;;
      *) die "已取消销毁" ;;
    esac
  fi

  linode_cli "${del_args[@]}"
  echo "销毁完成。"
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
  if [[ -n "${LINODE_CREATED_ID}" ]]; then
    echo "linode_id=${LINODE_CREATED_ID}  label=${LINODE_LABEL}"
  fi
  echo

  export SSHPASS="${VPS_PASSWORD}"
  export FORCE_RECREATE

  FORCE_RECREATE="${FORCE_RECREATE}" bash "${DEPLOY_SCRIPT}" "${deploy_args[@]}"
}

run_configure_indexers() {
  # 经 SSH stdin 在远端执行 configure_jackett_cn_indexers.sh（避免 scp -p/-P 端口参数差异）
  if [[ "${INDEXERS_MODE}" != "yes" ]]; then
    echo "=== 已跳过默认 indexer 配置 ==="
    return 0
  fi

  echo
  echo "=== 配置默认 Indexer（profile=${INDEXER_PROFILE}）==="

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] ssh INDEXER_PROFILE=${INDEXER_PROFILE} bash -s < ${INDEXERS_SCRIPT}"
    return 0
  fi

  export SSHPASS="${VPS_PASSWORD}"
  ssh_conn_args
  # 与 deploy 相同：远端 bash -s 读 stdin，不依赖 scp
  sshpass -e ssh -T "${SSH_CONN_ARGS[@]}" "${VPS_USER}@${VPS_HOST}" \
    "INDEXER_PROFILE='${INDEXER_PROFILE}' bash -s" < "${INDEXERS_SCRIPT}"

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
Dashboard 密码: ${JACKETT_ADMIN_PASSWORD:-345621}
Torznab:    http://${VPS_HOST}:9117
FlareSolverr 仅监听 VPS 本机 127.0.0.1:8191（不暴露公网）
EOF
  if [[ -n "${LINODE_CREATED_ID}" ]]; then
    cat <<EOF
Linode:     id=${LINODE_CREATED_ID}  label=${LINODE_LABEL}
销毁命令:   bash scripts/install_jackett_oneclick.sh --destroy-linode --linode-id ${LINODE_CREATED_ID}
            或: bash scripts/install_jackett_oneclick.sh --destroy-linode --linode-label ${LINODE_LABEL}
EOF
  fi
  cat <<EOF

建议: 在 Dashboard 登录后对已添加 indexer 逐个点 TEST（1337x/tgx 需 FlareSolverr）。
本机 Nyaa/DMHy SOCKS: bash scripts/start_ssh_socks_tunnel.sh
EOF
}

main() {
  # 入口：解析 →（销毁 | 开通）→ 密码 → indexer → 安装 → 同步 Key
  parse_args "$@"

  if [[ "${DESTROY_LINODE}" -eq 1 ]]; then
    check_linode_deps
    # label 可从 linode.local.json 读取；仅当既无 id 又无配置 label 时失败
    run_destroy_linode
    exit 0
  fi

  if [[ "${PROVISION_LINODE}" -eq 1 ]]; then
    check_linode_deps
    check_deps
    prompt_indexers_if_needed
    run_provision_linode
    run_install
    run_configure_indexers
    run_sync_key
    print_next_steps
    exit 0
  fi

  [[ -n "${VPS_HOST}" ]] || die "请传入 IP（位置参数或 --host），或使用 --provision-linode / --destroy-linode"
  prompt_password_if_needed
  prompt_indexers_if_needed

  check_deps
  run_install
  run_configure_indexers
  run_sync_key
  print_next_steps
}

main "$@"
