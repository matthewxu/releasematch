# VPS 迁移与 Jackett 部署记录

> **当前测试机：** `172.238.20.52`（2026-07-19）  
> **状态：** ✅ Jackett + FlareSolverr 已部署；本机 `accounts.local.json` 已同步 API Key  
> **文档类型：** 运维记录（长期有效，自 `worklogs/` 迁入并持续更新）

**历史迁移链：** `104.105.140.11`（2026-06-30）→ `104.105.137.77`（2026-07-01）→ `172.238.15.236`（2026-07-02）→ `172.237.11.232`（2026-07-04）→ `172.236.156.193`（2026-07-05）→ **`172.238.20.52`（2026-07-19，当前）**

---

## 当前环境（172.238.20.52）

| 项 | 值 |
|----|-----|
| VPS IP | **`172.238.20.52`** |
| Jackett URL | `http://172.238.20.52:9117` |
| Dashboard | `http://172.238.20.52:9117/UI/Dashboard` |
| SSH | `root` · 密码见 `servers.local.json`（不变） |
| Indexer（已配置） | nyaasi、1337x、thepiratebay、torrentgalaxyclone、eztv、dmhy、mikan、acgrip、bangumi-moe |
| FlareSolverr | 容器内 `http://flaresolverr:8191/`（1337x / tgx 用） |

---

## 部署命令

```bash
cd releasematch
export SSHPASS=$(python3 -c "import json; print(json.load(open('workflow/torrent_sources/servers.local.json'))['jackett_vps_japan']['ssh']['password'])")

# 一键安装 Jackett + FlareSolverr
FORCE_RECREATE=1 bash scripts/deploy_jackett_vps.sh --host 172.238.20.52

# 同步 API Key 到 accounts.local.json
bash scripts/sync_jackett_vps_key.sh --host 172.238.20.52

# Indexer（华语 + 主源）
sshpass -e scp scripts/remote/configure_jackett_cn_indexers.sh root@172.238.20.52:/tmp/
sshpass -e ssh root@172.238.20.52 'mkdir -p /opt/jackett/config/Jackett/Indexers && bash /tmp/configure_jackett_cn_indexers.sh'
# 另补 thepiratebay / nyaasi / eztv（见 2026-07-19 运维）
```

**2026-07-19 验收：**

```text
jackett_probe.reachable=true · status_code=200
has_valid_api_key=true
jackett_base_url=http://172.238.20.52:9117
```

---

## 本机配置更新

| 文件 | 变更 |
|------|------|
| `workflow/torrent_sources/servers.local.json` | host、public_url、api_key、SOCKS command |
| `workflow/torrent_sources/accounts.local.json` | base_url、api_key（数据源真相源） |
| `scripts/start_ssh_socks_tunnel.sh` | 默认 host 与 servers JSON 对齐 |

数据源勿再写入 `.env` 的 `JACKETT_*`（见 [15-多地多环境开发切换.md](./15-多地多环境开发切换.md)）。

---

## 验证

```bash
python -m workflow.torrent_sources.run status
python scripts/poc_phase0.py --jackett-base-url http://172.238.20.52:9117
python scripts/poc_jackett_indexers.py --jackett-base-url http://172.238.20.52:9117
python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6 --force
```

Nyaa 本机 SOCKS 回退：

```bash
bash scripts/start_ssh_socks_tunnel.sh
# accounts.local.json → proxy.url = socks5h://127.0.0.1:1080
```
