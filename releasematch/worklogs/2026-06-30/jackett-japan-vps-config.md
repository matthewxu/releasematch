# Jackett 日本测试服务器配置归档

> **日期：** 2026-06-30  
> **用途：** 记录海外 Jackett + FlareSolverr 测试环境，供本机 workflow 与文档引用

---

## 服务器概要

| 项 | 值 |
|----|-----|
| 标签 | 日本测试服务器 |
| IP | `104.105.140.11` |
| SSH | `root`（密码见 `servers.local.json`） |
| 系统 | Debian 12 |
| Jackett | `http://104.105.140.11:9117` |
| FlareSolverr | Docker 网络 `jackett-net`，Jackett 内 URL `http://flaresolverr:8191/` |

---

## 项目内配置文件

| 文件 | Git | 内容 |
|------|-----|------|
| `workflow/torrent_sources/servers.local.json` | 忽略 | SSH 密码、API Key、Docker 服务详情 |
| `workflow/torrent_sources/servers.example.json` | 提交 | 模板 |
| `workflow/torrent_sources/accounts.local.json` | 忽略 | `base_url` → 104.105.140.11:9117 |

---

## 文档

- [docs/jackett-remote-linode.md](../../docs/jackett-remote-linode.md) — 完整部署与运维
- [docs/jackett-stability.md](../../docs/jackett-stability.md) — 稳定性保障
- [docs/05-Jackett详解与安装使用教程.md](../../docs/05-Jackett详解与安装使用教程.md) §九 FlareSolverr

---

## 验收

```bash
python -m workflow.torrent_sources.run status
# 期望：has_valid_api_key=true, jackett_probe.reachable=true
```
