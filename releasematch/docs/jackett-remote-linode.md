# Jackett 部署在海外 VPS（Linode）说明

> **适用：** 开发机在国内，Jackett 本地 indexer（1337x / Nyaa 等）大量 400 或超时

---

## 是否更合适？

**对当前情况：更合适。**

| 维度 | 本机 Jackett | Linode（美/日节点） |
|------|----------------|---------------------|
| 1337x / Nyaa / EZTV 抓取 | 易 400、超时、Cloudflare | 通常更稳定 |
| YTS | 直连已通 | 同样可用 |
| 延迟 | 最低 | +100~250ms，批补可接受 |
| 安全 | 仅本机访问 | **必须** 设 API Key + 防火墙 |
| 成本 | $0 | 约 $5/月（Nanode 1GB 够用） |

ReleaseMatch **元数据工作流**跑在你本机或 CI；**只把 Jackett 当远程 Torznab 服务**，架构清晰、与 T2 测速 VPS 可同机或分机。

---

## 推荐架构

```
[本机 / CI]  releasematch workflow
       │
       │  HTTPS + API Key
       ▼
[Linode VPS]  Jackett :9117  +  indexers (1337x, eztv, yts, nyaasi…)
```

EZTV / YTS **直连 API** 仍可由本机 `eztv_client` / `yts_client` 调用（你 [2/4][3/4] 已通）；Jackett 专注聚合与难直连的源。

---

## Linode 快速部署

```bash
# SSH 登录 Ubuntu 22.04+
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker

sudo mkdir -p /opt/jackett/config
sudo docker run -d \
  --name jackett \
  --restart unless-stopped \
  -p 127.0.0.1:9117:9117 \
  -v /opt/jackett/config:/config \
  linuxserver/jackett:latest
```

### 安全（必做）

1. **不要** `0.0.0.0:9117` 裸奔公网；二选一：
   - **SSH 隧道（开发）：** `ssh -L 9117:127.0.0.1:9117 user@linode-ip`，本机仍用 `http://127.0.0.1:9117`
   - **公网 + 防护：** Nginx/Caddy + TLS，或 `ufw allow from YOUR_HOME_IP to any port 9117`
2. Jackett Dashboard 设置 **Admin password**
3. 复制 **API Key** 到本机 `accounts.local.json`

### 本机配置

`workflow/torrent_sources/accounts.local.json`:

```json
"jackett": {
  "base_url": "http://YOUR_LINODE_IP:9117",
  "api_key": "..."
}
```

或环境变量：

```bash
export JACKETT_BASE_URL=http://YOUR_LINODE_IP:9117
export JACKETT_API_KEY=...
```

验证：

```bash
python scripts/poc_phase0.py --jackett-base-url http://YOUR_LINODE_IP:9117
python scripts/poc_jackett_indexers.py --jackett-base-url http://YOUR_LINODE_IP:9117
```

---

## 区域选择

| 节点 | 适合 |
|------|------|
| **美国** | 1337x、EZTV、YTS |
| **日本** | Nyaa.si、日韩源 |
| **新加坡** | 国内开发者较低延迟折中 |

可先开美国 Nanode，Nyaa 仍差再换日本或加第二实例。

---

## 与 T2 测速 VPS 的关系

| 服务 | 用途 | 是否合并 |
|------|------|----------|
| Jackett | 索引抓取 | 可与测速同 VPS |
| T2 libtorrent 测速 | 握手/片段测速 | 文档建议 Hetzner/Linode |

同机部署省成本；注意 CPU/带宽：测速与 Jackett 高峰错开即可。

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-30 | 初版：国内本机 indexer 失败后的海外 Jackett 方案 |
