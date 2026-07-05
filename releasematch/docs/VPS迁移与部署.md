# VPS 迁移与 Jackett 部署记录

> **当前测试机：** `172.236.156.193`（2026-07-05）  
> **状态：** ✅ Jackett + FlareSolverr 已部署；本机 `accounts.local.json` 已同步 API Key  
> **文档类型：** 运维记录（长期有效，自 `worklogs/` 迁入并持续更新）

**历史迁移链：** `104.105.140.11`（2026-06-30）→ `104.105.137.77`（2026-07-01）→ `172.238.15.236`（2026-07-02）→ `172.237.11.232`（2026-07-04）→ **`172.236.156.193`（2026-07-05，当前）**

---

## 当前环境（172.236.156.193）

| 项 | 值 |
|----|-----|
| VPS IP | **`172.236.156.193`** |
| Jackett URL | `http://172.236.156.193:9117` |
| Dashboard | `http://172.236.156.193:9117/UI/Dashboard` |
| SSH | `root` · 密码见 `servers.local.json`（不变） |
| Indexer（已配置） | nyaasi、1337x、thepiratebay、torrentgalaxyclone |
| FlareSolverr | 容器内 `http://flaresolverr:8191/`（1337x / tgx 用） |

---

## 部署命令

```bash
cd releasematch
export SSHPASS=$(python3 -c "import json; print(json.load(open('workflow/torrent_sources/servers.local.json'))['jackett_vps_japan']['ssh']['password'])")

# 一键安装 Jackett + FlareSolverr
FORCE_RECREATE=1 bash scripts/deploy_jackett_vps.sh --host 172.236.156.193

# 同步 API Key 到 accounts.local.json
bash scripts/sync_jackett_vps_key.sh --host 172.236.156.193
```

**2026-07-05 验收：**

```text
jackett_probe.reachable=true
has_valid_api_key=true
jackett_base_url=http://172.236.156.193:9117
poc_jackett_indexers: nyaasi/1337x/tpb/tgx 均 HTTP 200（TPB tvdbid 400，q+s+e 可用）
```

---

## 本机配置更新

| 文件 | 变更 |
|------|------|
| `workflow/torrent_sources/servers.local.json` | host、public_url、api_key、SOCKS command |
| `workflow/torrent_sources/accounts.local.json` | base_url、api_key、tv indexers |
| `scripts/start_ssh_socks_tunnel.sh` | 默认 `VPS_HOST=172.236.156.193` |

---

## 验收

```bash
python -m workflow.torrent_sources.run status
python scripts/poc_jackett_indexers.py

bash scripts/start_ssh_socks_tunnel.sh
# Nyaa via SOCKS: HTTP 200
```

---

## 全站数据重拉（跨源分母更新后）

```bash
# 117 个 published 槽位 force 重拉（约 1.5~3h）
python -m workflow.run pipeline refetch-all

# 可选：fuzzy 跨源重算（不重拉 indexer）
python scripts/recompute_cross_source_fuzzy.py --all-published --rescore-after

python -m workflow.run generate all
```

详见 [seo/iterations/2026-07-05-跨源扩展与全站重拉.md](./seo/iterations/2026-07-05-跨源扩展与全站重拉.md)。

---

## 测速 cron Worker

在 VPS 或本机（需 libtorrent + MySQL 可达）定时跑批量测速：

```bash
python -m workflow.torrent_sources.speedtest.run batch --all-published --write
```

---

## 变更记录

| 日期 | IP | 说明 |
|------|-----|------|
| 2026-06-30 | 104.105.140.11 | 初建日本 VPS Jackett |
| 2026-07-04 | 172.237.11.232 | 迁移 + deploy 验收 |
| 2026-07-05 | **172.236.156.193** | 新机部署 · indexer 四源 · 全站 refetch |
