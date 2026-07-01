# VPS 迁移：104.105.140.11 → 104.105.137.77

> **日期：** 2026-07-01  
> **状态：** Jackett + FlareSolverr 已在新机部署；本机配置已切换

---

## 变更摘要

| 项 | 旧值 | 新值 |
|----|------|------|
| VPS IP | `104.105.140.11` | **`104.105.137.77`** |
| Jackett URL | `http://104.105.140.11:9117` | `http://104.105.137.77:9117` |
| API Key | 见旧机 `servers.local.json` | **新机生成**，见 `servers.local.json` |
| SSH 用户/密码 | root / 见 servers.local.json | **不变** |

---

## 部署命令

```bash
cd releasematch
export SSHPASS=$(python3 -c "import json; print(json.load(open('workflow/torrent_sources/servers.local.json'))['jackett_vps_japan']['ssh']['password'])")
bash scripts/deploy_jackett_vps.sh --host 104.105.137.77
```

**结果：** Docker + FlareSolverr + Jackett 安装成功；FlareSolverr sessions.list HTTP 200。

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

## 关联

- [docs/jackett-remote-linode.md](../../docs/jackett-remote-linode.md)
- [今日验收清单](./今日验收清单.md)
