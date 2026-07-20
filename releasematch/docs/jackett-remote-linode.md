# Jackett 部署在海外 VPS 说明

> **适用：** 开发机在国内，Jackett 本地 indexer（1337x / Nyaa 等）大量 400 或超时  
> **项目测试机：** 日本 VPS `104.105.140.95`（见 §四；历史 IP 见 [VPS迁移与部署.md](./VPS迁移与部署.md)）

---

## 是否更合适？

**对当前情况：更合适。**

| 维度 | 本机 Jackett | 海外 VPS（美/日节点） |
|------|----------------|---------------------|
| 1337x / Nyaa / EZTV 抓取 | 易 400、超时、Cloudflare | 通常更稳定 |
| YTS | 直连已通 | 同样可用 |
| 延迟 | 最低 | +100~250ms，批补可接受 |
| 安全 | 仅本机访问 | **必须** 设 API Key + 防火墙 |
| 成本 | $0 | 约 $5/月（1~2GB 够用） |

ReleaseMatch **元数据工作流**跑在你本机或 CI；**只把 Jackett 当远程 Torznab 服务**，架构清晰、与 T2 测速 VPS 可同机或分机。

---

## 推荐架构

```
[本机 / CI]  releasematch workflow
       │
       │  HTTP + API Key
       ▼
[海外 VPS]  Jackett :9117  +  FlareSolverr :8191  +  indexers (1337x, eztv, nyaasi…)
```

EZTV / YTS **直连 API** 仍可由本机 `eztv_client` / `yts_client` 调用；Jackett 专注聚合与难直连的源。

---

## 零、本机一键远程安装（推荐）

新买 VPS 时，在 **本机** `releasematch` 目录用交互一键脚本（IP + 密码即可）：

```bash
# 交互输入密码；安装后询问是否写入默认 indexer（all/cn/intl）
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95

# 密码含 & $ 等字符必须单引号
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95 --password 'YourPass&secret'
bash scripts/install_jackett_oneclick.sh --host 104.105.140.95 --password 'YourPass' --with-indexers
```

流程：`deploy_jackett_vps.sh`（Docker + Jackett + FlareSolverr）→ 可选 `configure_jackett_cn_indexers.sh` → `sync_jackett_vps_key.sh`。

仅装栈、不交互（读 `servers.local.json`）时仍可用：

```bash
bash scripts/deploy_jackett_vps.sh
SSHPASS='your-password' bash scripts/deploy_jackett_vps.sh --host 104.105.140.95
FORCE_RECREATE=1 bash scripts/deploy_jackett_vps.sh   # 强制重建容器
bash scripts/deploy_jackett_vps.sh --dry-run
```

**Nyaa 回退**在本机用 SSH SOCKS，无需 VPS 代理：

```bash
bash scripts/start_ssh_socks_tunnel.sh
export TORRENT_PROXY=socks5h://127.0.0.1:1080
```

仅 VPS 内手动安装时：`bash scripts/remote/install_jackett_stack.sh`（需 root）。  
仅补 indexer：`INDEXER_PROFILE=all bash scripts/remote/configure_jackett_cn_indexers.sh`（VPS 上）。

---

## 一、通用 Docker 部署

```bash
# SSH 登录 Debian / Ubuntu
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable --now docker

# Docker 网络（Jackett 与 FlareSolverr 互通）
docker network create jackett-net

# Jackett
sudo mkdir -p /opt/jackett/config
sudo docker run -d \
  --name jackett \
  --restart unless-stopped \
  --network jackett-net \
  -p 9117:9117 \
  -v /opt/jackett/config:/config \
  linuxserver/jackett:latest

# FlareSolverr（1337x / TorrentGalaxy 等 Cloudflare 站点必备）
sudo docker run -d \
  --name flaresolverr \
  --restart unless-stopped \
  --network jackett-net \
  -e LOG_LEVEL=info \
  -p 127.0.0.1:8191:8191 \
  ghcr.io/flaresolverr/flaresolverr:latest
```

### Jackett 内 FlareSolverr 配置

Dashboard → **System** → **FlareSolverr URL**（Docker 同网必须用**容器名**，不能用 `127.0.0.1`）：

```
http://flaresolverr:8191/
```

或通过 `ServerConfig.json` 写入：

```bash
python3 <<'PY'
import json
p = "/opt/jackett/config/Jackett/ServerConfig.json"
d = json.load(open(p))
d["FlareSolverrUrl"] = "http://flaresolverr:8191/"
d["FlareSolverrMaxTimeout"] = 55000
json.dump(d, open(p, "w"), indent=2)
PY
docker restart jackett
```

### 安全（必做）

1. FlareSolverr 建议只绑定 `127.0.0.1:8191`（不暴露公网）
2. Jackett 若公网开放 9117：**必须**设 Dashboard 管理员密码（安装脚本默认 `345621`，可用 `JACKETT_ADMIN_PASSWORD` 覆盖）
3. **SSH 密码、API Key 勿提交 Git** — 见 §三 凭据文件

---

## 二、本机 ReleaseMatch 配置

`workflow/torrent_sources/accounts.local.json`：

```json
"jackett": {
  "base_url": "http://104.105.140.95:9117",
  "api_key": "从 Dashboard 或 servers.local.json 复制",
  "indexers": {
    "tv": ["thepiratebay", "torrentgalaxyclone", "nyaasi", "1337x", "all"],
    "movie": ["yts", "1337x", "torrentgalaxyclone", "all"]
  }
}
```

或环境变量：

```bash
export JACKETT_BASE_URL=http://104.105.140.95:9117
export JACKETT_API_KEY=...
```

验证：

```bash
python -m workflow.torrent_sources.run status
python scripts/poc_phase0.py --jackett-base-url http://104.105.140.95:9117
python scripts/poc_jackett_indexers.py --jackett-base-url http://104.105.140.95:9117
```

---

## 三、凭据与服务器清单（本地保存）

| 文件 | 是否提交 Git | 说明 |
|------|-------------|------|
| `workflow/torrent_sources/servers.example.json` | ✅ 可提交 | 模板，占位符 |
| `workflow/torrent_sources/servers.local.json` | ❌ 勿提交 | SSH 密码、API Key、Docker 详情 |
| `workflow/torrent_sources/accounts.local.json` | ❌ 勿提交 | 本机 workflow 使用的 Jackett URL + Key |

首次使用：

```bash
cp workflow/torrent_sources/servers.example.json workflow/torrent_sources/servers.local.json
# 编辑 servers.local.json 填入真实 IP / 密码 / API Key
```

---

## 四、日本测试服务器（当前环境）

| 项 | 值 |
|----|-----|
| **标签** | 日本测试服务器 |
| **IP** | `104.105.140.95` |
| **SSH 用户** | `root` |
| **SSH 密码** | 见 `servers.local.json`（勿写入公开文档） |
| **系统** | Debian 12 |
| **Jackett** | `http://104.105.140.95:9117` |
| **Dashboard** | `http://104.105.140.95:9117/UI/Dashboard` |
| **Dashboard 密码** | 默认 `345621`（`JACKETT_ADMIN_PASSWORD`） |
| **FlareSolverr** | 容器内 `http://flaresolverr:8191/`（宿主机 `127.0.0.1:8191`） |
| **Docker 网络** | `jackett-net` |
| **配置卷** | `/opt/jackett/config` |

### 已配置 Indexer

一键脚本 `--with-indexers` / `INDEXER_PROFILE=all` 可写入：

- thepiratebay、nyaasi、eztv
- 1337x、torrentgalaxyclone（需 FlareSolverr）
- dmhy、mikan、acgrip、bangumi-moe（华语）

### 常用运维命令

```bash
# SSH 登录
ssh root@104.105.140.95

# 查看容器
docker ps
docker logs jackett --tail 50
docker logs flaresolverr --tail 30

# 重启服务
docker restart flaresolverr jackett

# 验证 FlareSolverr API
curl -s -X POST http://127.0.0.1:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.list"}'

# 从 Jackett 容器内测 FlareSolverr 连通性
docker exec jackett curl -s -o /dev/null -w '%{http_code}\n' http://flaresolverr:8191/
```

### FlareSolverr 排错

| 现象 | 处理 |
|------|------|
| `Challenge detected but FlareSolverr is not configured` | 在 Jackett System 填入 `http://flaresolverr:8191/` 并 `docker restart jackett` |
| Test 超时 | 检查 VPS 内存 ≥ 2GB；`docker stats flaresolverr` |
| 容器不通 | `docker network inspect jackett-net` 确认 jackett、flaresolverr 均在网内 |

---

## 五、区域选择

| 节点 | 适合 |
|------|------|
| **美国** | 1337x、EZTV、YTS |
| **日本** | Nyaa.si、日韩源（**当前测试机**） |
| **新加坡** | 国内开发者较低延迟折中 |

---

## 六、与 T2 测速 VPS 的关系

| 服务 | 用途 | 是否合并 |
|------|------|----------|
| Jackett | 索引抓取 | 可与测速同 VPS |
| T2 libtorrent 测速 | 握手/片段测速 | 文档建议 Hetzner/Linode |

同机部署省成本；注意 CPU/带宽：测速与 Jackett 高峰错开即可。

**稳定性运维（healthcheck、indexer 配置、验收基准）见 [jackett-stability.md](./jackett-stability.md)。**

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-30 | 初版：国内本机 indexer 失败后的海外 Jackett 方案 |
| 2026-06-30 | 补充日本测试机 104.105.140.11、FlareSolverr Docker 网络、`servers.local.json` 凭据规范 |
| 2026-07-02 | 测试机迁移至 `172.238.15.236`（见 [VPS迁移与部署.md](./VPS迁移与部署.md)） |
| 2026-07-05 | 测试机迁移至 `104.105.140.95`；indexer：nyaasi/1337x/tpb/tgx；**部署验收通过** |
| 2026-06-30 | 增加 [jackett-stability.md](./jackett-stability.md) 交叉引用 |
| 2026-06-30 | 增加本机一键脚本 `scripts/deploy_jackett_vps.sh` |
| 2026-07-20 | 增加 `scripts/install_jackett_oneclick.sh`（IP+密码+交互 indexer）；测试机 `104.105.140.95` |
| 2026-07-20 | 安装脚本默认写入 Dashboard 密码 `345621`（`JACKETT_ADMIN_PASSWORD`）；indexer 经 SSH stdin 推送 |
