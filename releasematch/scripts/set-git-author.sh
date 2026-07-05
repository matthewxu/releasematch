#!/usr/bin/env bash
# =============================================================================
# set-git-author.sh
# 重写 Git 历史提交的作者/提交者信息，并配置后续新提交使用的身份。
#
# 用法:
#   ./scripts/set-git-author.sh --name "你的名字" --email "you@example.com"
#   ./scripts/set-git-author.sh --name "你的名字" --email "you@example.com" --old-name "Matthew Xu"
#   ./scripts/set-git-author.sh --name "你的名字" --email "you@example.com" --global
#   ./scripts/set-git-author.sh --name "你的名字" --email "you@example.com" --dry-run
#
# 注意:
#   - 会改写当前仓库所有分支与标签上的提交历史（生成新 commit hash）
#   - 若已 push 到远程，改写后需执行: git push --force-with-lease
#   - 执行前请确保工作区干净（无未提交改动）
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# 脚本路径与仓库根目录
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# -----------------------------------------------------------------------------
# 默认参数
# -----------------------------------------------------------------------------
NEW_NAME=""          # 新的作者显示名
NEW_EMAIL=""         # 新的作者邮箱
OLD_NAME=""          # 仅改写匹配此旧名字的历史提交；为空则改写全部
OLD_EMAIL=""         # 仅改写匹配此旧邮箱的历史提交；为空则忽略邮箱过滤
USE_GLOBAL=false     # true 时对全局 git config 生效，否则仅本仓库 local
DRY_RUN=false        # true 时只预览，不实际改写
SKIP_CONFIRM=false   # true 时跳过交互确认

# -----------------------------------------------------------------------------
# 打印用法说明
# -----------------------------------------------------------------------------
print_usage() {
  cat <<'EOF'
用法: set-git-author.sh --name <名字> --email <邮箱> [选项]

必填:
  --name <名字>         新的 Git 作者名（Author / Committer 显示名）
  --email <邮箱>        新的 Git 邮箱

可选:
  --old-name <名字>     仅改写 Author/Committer 名字等于此值的提交（默认改写全部）
  --old-email <邮箱>    与 --old-name 组合，进一步按旧邮箱过滤（默认不限制邮箱）
  --global              写入全局 git config（默认仅写入本仓库 local config）
  --dry-run             预览将受影响的提交，不实际改写
  --yes, -y             跳过确认提示，直接执行
  -h, --help            显示此帮助

示例:
  ./scripts/set-git-author.sh --name "Matthew Xu" --email "matthew@example.com"
  ./scripts/set-git-author.sh --name "Matthew Xu" --email "matthew@example.com" --old-name "许历"
EOF
}

# -----------------------------------------------------------------------------
# 解析命令行参数
# -----------------------------------------------------------------------------
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name)
        NEW_NAME="${2:-}"
        shift 2
        ;;
      --email)
        NEW_EMAIL="${2:-}"
        shift 2
        ;;
      --old-name)
        OLD_NAME="${2:-}"
        shift 2
        ;;
      --old-email)
        OLD_EMAIL="${2:-}"
        shift 2
        ;;
      --global)
        USE_GLOBAL=true
        shift
        ;;
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --yes | -y)
        SKIP_CONFIRM=true
        shift
        ;;
      -h | --help)
        print_usage
        exit 0
        ;;
      *)
        echo "错误: 未知参数 '$1'" >&2
        print_usage >&2
        exit 1
        ;;
    esac
  done
}

# -----------------------------------------------------------------------------
# 校验必填参数与邮箱格式
# -----------------------------------------------------------------------------
validate_args() {
  if [[ -z "$NEW_NAME" || -z "$NEW_EMAIL" ]]; then
    echo "错误: 必须同时提供 --name 和 --email" >&2
    print_usage >&2
    exit 1
  fi

  # 简单邮箱格式校验（含 @ 且 @ 后有点）
  if [[ ! "$NEW_EMAIL" =~ ^[^@]+@[^@]+\.[^@]+$ ]]; then
    echo "错误: 邮箱格式无效: $NEW_EMAIL" >&2
    exit 1
  fi
}

# -----------------------------------------------------------------------------
# 确认当前目录是 Git 仓库且工作区干净
# -----------------------------------------------------------------------------
ensure_clean_repo() {
  cd "$REPO_ROOT"

  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "错误: $REPO_ROOT 不是 Git 仓库" >&2
    exit 1
  fi

  if [[ "$DRY_RUN" != "true" && -n "$(git status --porcelain)" ]]; then
    echo "错误: 工作区存在未提交改动，请先 commit 或 stash 后再运行" >&2
    git status --short
    exit 1
  fi
}

# -----------------------------------------------------------------------------
# 统计并展示当前作者分布（dry-run / 确认前预览）
# -----------------------------------------------------------------------------
preview_commits() {
  echo ""
  echo "========================================"
  echo " 当前仓库作者分布"
  echo "========================================"
  git shortlog -sne --all || true

  echo ""
  echo "========================================"
  echo " 计划变更"
  echo "========================================"
  echo "  新作者名 : $NEW_NAME"
  echo "  新邮箱   : $NEW_EMAIL"
  echo "  配置范围 : $([[ "$USE_GLOBAL" == "true" ]] && echo "global（全局）" || echo "local（本仓库）")"

  if [[ -n "$OLD_NAME" || -n "$OLD_EMAIL" ]]; then
    echo "  过滤条件 :"
    [[ -n "$OLD_NAME" ]] && echo "    旧名字 = $OLD_NAME"
    [[ -n "$OLD_EMAIL" ]] && echo "    旧邮箱 = $OLD_EMAIL"
  else
    echo "  过滤条件 : 改写全部历史提交"
  fi

  local total
  total="$(git rev-list --all --count 2>/dev/null || echo 0)"
  echo "  提交总数 : $total"
  echo ""
}

# -----------------------------------------------------------------------------
# 交互确认（除非 --yes 或 --dry-run）
# -----------------------------------------------------------------------------
confirm_execution() {
  if [[ "$DRY_RUN" == "true" || "$SKIP_CONFIRM" == "true" ]]; then
    return 0
  fi

  echo "警告: 此操作将改写 Git 历史，所有 commit hash 都会变化。"
  echo "      若已 push 到远程，完成后需执行: git push --force-with-lease"
  echo ""
  read -r -p "确认继续? [y/N] " answer
  case "$answer" in
    y | Y | yes | YES) ;;
    *)
      echo "已取消。"
      exit 0
      ;;
  esac
}

# -----------------------------------------------------------------------------
# 写入 git config，供后续新提交使用
# -----------------------------------------------------------------------------
apply_git_config() {
  local config_scope="--local"
  if [[ "$USE_GLOBAL" == "true" ]]; then
    config_scope="--global"
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[dry-run] git config $config_scope user.name \"$NEW_NAME\""
    echo "[dry-run] git config $config_scope user.email \"$NEW_EMAIL\""
    return 0
  fi

  git config "$config_scope" user.name "$NEW_NAME"
  git config "$config_scope" user.email "$NEW_EMAIL"

  echo ""
  echo "已设置后续提交身份 ($config_scope):"
  echo "  user.name  = $(git config $config_scope user.name)"
  echo "  user.email = $(git config $config_scope user.email)"
}

# -----------------------------------------------------------------------------
# 使用 git filter-branch 批量改写历史 Author / Committer
# -----------------------------------------------------------------------------
rewrite_history() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "[dry-run] 将使用 git filter-branch 改写 --branches --tags 上的历史提交"
    return 0
  fi

  echo ""
  echo "========================================"
  echo " 正在改写历史提交..."
  echo "========================================"

  # 导出供 env-filter 子 shell 使用的变量
  export FILTER_NEW_NAME="$NEW_NAME"
  export FILTER_NEW_EMAIL="$NEW_EMAIL"
  export FILTER_OLD_NAME="$OLD_NAME"
  export FILTER_OLD_EMAIL="$OLD_EMAIL"

  # env-filter 在 filter-branch 中对每个 commit 执行一次
  git filter-branch -f --env-filter '
    rewrite_author=false
    rewrite_committer=false

    if [ -n "$FILTER_OLD_NAME$FILTER_OLD_EMAIL" ]; then
      if [ -z "$FILTER_OLD_NAME" ] || [ "$GIT_AUTHOR_NAME" = "$FILTER_OLD_NAME" ]; then
        if [ -z "$FILTER_OLD_EMAIL" ] || [ "$GIT_AUTHOR_EMAIL" = "$FILTER_OLD_EMAIL" ]; then
          rewrite_author=true
        fi
      fi
      if [ -z "$FILTER_OLD_NAME" ] || [ "$GIT_COMMITTER_NAME" = "$FILTER_OLD_NAME" ]; then
        if [ -z "$FILTER_OLD_EMAIL" ] || [ "$GIT_COMMITTER_EMAIL" = "$FILTER_OLD_EMAIL" ]; then
          rewrite_committer=true
        fi
      fi
    else
      rewrite_author=true
      rewrite_committer=true
    fi

    if [ "$rewrite_author" = "true" ]; then
      export GIT_AUTHOR_NAME="$FILTER_NEW_NAME"
      export GIT_AUTHOR_EMAIL="$FILTER_NEW_EMAIL"
    fi

    if [ "$rewrite_committer" = "true" ]; then
      export GIT_COMMITTER_NAME="$FILTER_NEW_NAME"
      export GIT_COMMITTER_EMAIL="$FILTER_NEW_EMAIL"
    fi
  ' -- --branches --tags

  # 清理 filter-branch 备份引用，避免占用空间与混淆
  if [[ -d "$REPO_ROOT/.git/refs/original" ]]; then
    rm -rf "$REPO_ROOT/.git/refs/original"
  fi
  git reflog expire --expire=now --all
  git gc --prune=now --quiet

  echo ""
  echo "历史改写完成。最新提交作者:"
  git log -1 --format="  %h  %an <%ae>  %s"
}

# -----------------------------------------------------------------------------
# 打印后续操作建议
# -----------------------------------------------------------------------------
print_next_steps() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "[dry-run] 未做任何实际修改。去掉 --dry-run 后执行即可。"
    return 0
  fi

  echo ""
  echo "========================================"
  echo " 完成"
  echo "========================================"
  echo "后续新提交将使用: $NEW_NAME <$NEW_EMAIL>"
  echo ""
  if git remote get-url origin >/dev/null 2>&1; then
    echo "若需同步到远程，请执行:"
    echo "  git push --force-with-lease origin main"
    echo ""
    echo "（如有其他分支/标签也需推送，请一并 force push）"
  fi
}

# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------
main() {
  parse_args "$@"
  validate_args
  ensure_clean_repo
  preview_commits
  confirm_execution
  apply_git_config
  rewrite_history
  print_next_steps
}

main "$@"
