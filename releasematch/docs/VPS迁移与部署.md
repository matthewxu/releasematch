# VPS 迁移：104.105.137.77 → 172.238.15.236

> **日期：** 2026-07-02  
> **状态：** Jackett + FlareSolverr 已在新机部署；本机配置已切换  
> **文档类型：** 运维记录（长期有效，自 `worklogs/2026-07-01/` 迁入并持续更新）

**历史迁移链：** `104.105.140.11`（2026-06-30）→ `104.105.137.77`（2026-07-01）→ **`172.238.15.236`（2026-07-02，当前）**

---

## 变更摘要

| 项 | 旧值 | 新值 |
|----|------|------|
| VPS IP | `104.105.137.77` | **`172.238.15.236`** |
| Jackett URL | `http://104.105.137.77:9117` | `http://172.238.15.236:9117` |
| API Key | 见旧机 `servers.local.json` | **新机生成**，见 `servers.local.json` |
| SSH 用户/密码 | root / 见 servers.local.json | **不变** |

---

## 部署命令

```bash
cd releasematch
export SSHPASS=$(python3 -c "import json; print(json.load(open('workflow/torrent_sources/servers.local.json'))['jackett_vps_japan']['ssh']['password'])")
FORCE_RECREATE=1 bash scripts/deploy_jackett_vps.sh --host 172.238.15.236
```

**结果：** Docker + FlareSolverr + Jackett 安装成功；FlareSolverr sessions.list HTTP 200。

**2026-07-02 实测：**

```text
jackett_probe.reachable=true
has_valid_api_key=true
jackett_base_url=http://172.238.15.236:9117
```

---

## 本机配置更新

| 文件 | 变更 |
|------|------|
| `workflow/torrent_sources/servers.local.json` | host、public_url、api_key、SOCKS command |
| `workflow/torrent_sources/accounts.local.json` | base_url、api_key |
| `scripts/start_ssh_socks_tunnel.sh` | 默认 VPS_HOST |

---

## 验收

```bash
python -m workflow.torrent_sources.run status
# jackett_probe.reachable=true, has_valid_api_key=true

bash scripts/start_ssh_socks_tunnel.sh
# Nyaa via SOCKS: HTTP 200
```

**注意：** 新机 Jackett Dashboard 需手动添加 indexer（thepiratebay、nyaasi、eztv 等）。

---

## 测速 cron Worker（172.238.15.236）

在 VPS 或本机（需 libtorrent + MySQL 可达）定时跑批量测速：

```bash
cd releasematch
source .venv/bin/activate

# 7 槽 benchmark（5 并发，策略 A2）
python scripts/speedtest_batch_worker.py \
  --slots-json worklogs/2026-06-30/benchmark-slots.json \
  --write --workers 5 --target-bytes 262144 \
  --report worklogs/2026-07-02/speedtest-batch-benchmark.json
```

**crontab 示例（每 6 小时，TTL 内自动跳过）：**

```cron
0 */6 * * * cd /opt/releasematch/releasematch && .venv/bin/python scripts/speedtest_batch_worker.py --slots-json worklogs/2026-06-30/benchmark-slots.json --write --workers 5 --report /var/log/releasematch/speedtest-batch.json >> /var/log/releasematch/speedtest-cron.log 2>&1
```

**systemd timer 单元（`/etc/systemd/system/releasematch-speedtest.service`）：**

```ini
[Unit]
Description=ReleaseMatch batch speedtest
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/releasematch/releasematch
ExecStart=/opt/releasematch/releasematch/.venv/bin/python scripts/speedtest_batch_worker.py --slots-json worklogs/2026-06-30/benchmark-slots.json --write --workers 5 --report /var/log/releasematch/speedtest-batch.json
User=root
```

```ini
# /etc/systemd/system/releasematch-speedtest.timer
[Unit]
Description=ReleaseMatch speedtest every 6h

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用：`systemctl enable --now releasematch-speedtest.timer`

---

## 关联

- [jackett-remote-linode.md](./jackett-remote-linode.md) — 海外 VPS 通用部署
- [jackett-stability.md](./jackett-stability.md) — 稳定性与 healthcheck
- [nyaa-proxy-asia.md](./nyaa-proxy-asia.md) — SSH SOCKS 隧道回退
- [2026-07-01 今日验收清单](../worklogs/2026-07-01/今日验收清单.md) — 上一机迁移验收记录
