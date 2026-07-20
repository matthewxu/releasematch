# VPS 迁移与 Jackett 部署记录

> **当前测试机：** `104.105.140.95`（2026-07-20）  
> **状态：** ✅ Jackett + FlareSolverr 已部署；本机 `accounts.local.json` 已同步 API Key  
> **文档类型：** 运维记录（长期有效，自 `worklogs/` 迁入并持续更新）

**历史迁移链：** `104.105.140.11`（2026-06-30）→ `104.105.137.77`（2026-07-01）→ `172.238.15.236`（2026-07-02）→ `172.237.11.232`（2026-07-04）→ `172.236.156.193`（2026-07-05）→ `172.238.20.52`（2026-07-19）→ **`104.105.140.95`（2026-07-20，当前）**

---

## 当前环境（104.105.140.95）

| 项 | 值 |
|----|-----|
| VPS IP | **`104.105.140.95`** |
| Jackett URL | `http://104.105.140.95:9117` |
| Dashboard | `http://104.105.140.95:9117/UI/Dashboard` |
| SSH | `root` · 密码见 `servers.local.json`（勿提交敏感变更到公开仓库时请复查） |
| Indexer（可一键写入） | nyaasi、1337x、thepiratebay、torrentgalaxyclone、eztv、dmhy、mikan、acgrip、bangumi-moe |
| FlareSolverr | 容器内 `http://flaresolverr:8191/`（1337x / tgx 用） |

---

## 部署命令（推荐：交互一键）

新买 VPS 或重建时，在本机 `releasematch` 目录执行：

```bash
cd releasematch

# 交互：输入密码 → 询问是否配置默认 indexer → 安装 → 同步 API Key
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95

# 或命令行传入密码（含 & 等字符必须单引号）
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95 --password 'YourPass'
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95 --password 'YourPass' --with-indexers
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95 --password 'YourPass' --with-indexers --indexer-profile all
```

| 选项 | 说明 |
|------|------|
| （默认） | 交互询问是否写入默认 indexer |
| `--with-indexers` | 跳过询问，直接写入 |
| `--no-indexers` | 跳过 indexer |
| `--indexer-profile all\|cn\|intl` | 全套 / 仅华语 / 仅国际 |
| `--no-force` | 不强制重建已有容器 |
| `--no-sync` | 不同步 API Key 到本机 |

脚本内部会调用：

1. `scripts/deploy_jackett_vps.sh` → 远端 `install_jackett_stack.sh`（Docker + Jackett + FlareSolverr）
2. （可选）`scripts/remote/configure_jackett_cn_indexers.sh`（写入 Indexers/*.json）
3. `scripts/sync_jackett_vps_key.sh` → `accounts.local.json`

### 旧版分步命令（仍可用）

```bash
export SSHPASS=$(python3 -c "import json; print(json.load(open('workflow/torrent_sources/servers.local.json'))['jackett_vps_japan']['ssh']['password'])")

FORCE_RECREATE=1 bash scripts/deploy_jackett_vps.sh --host 104.105.140.95
bash scripts/sync_jackett_vps_key.sh --host 104.105.140.95

sshpass -e scp scripts/remote/configure_jackett_cn_indexers.sh root@104.105.140.95:/tmp/
sshpass -e ssh root@104.105.140.95 'INDEXER_PROFILE=all bash /tmp/configure_jackett_cn_indexers.sh'
```

**2026-07-20 验收：**

```text
jackett_probe.reachable=true · status_code=200
has_valid_api_key=true
jackett_base_url=http://104.105.140.95:9117
公网根路径 HTTP 301 → /UI/Dashboard
```

---

## 本机配置更新

| 文件 | 变更 |
|------|------|
| `workflow/torrent_sources/servers.local.json` | host、public_url、api_key、SOCKS command、deploy_notes |
| `workflow/torrent_sources/accounts.local.json` | base_url、api_key（数据源真相源） |
| `scripts/start_ssh_socks_tunnel.sh` | 默认 host 与 servers JSON 对齐 |

数据源勿再写入 `.env` 的 `JACKETT_*`（见 [15-多地多环境开发切换.md](./15-多地多环境开发切换.md)）。

---

## 验证

```bash
python -m workflow.torrent_sources.run status
python scripts/poc_phase0.py --jackett-base-url http://104.105.140.95:9117
python scripts/poc_jackett_indexers.py --jackett-base-url http://104.105.140.95:9117
python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6 --force
```

Nyaa 本机 SOCKS 回退：

```bash
bash scripts/start_ssh_socks_tunnel.sh
export TORRENT_PROXY=socks5h://127.0.0.1:1080
```
