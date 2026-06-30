# Jackett 稳定性保障文档归档

> **日期：** 2026-06-30  
> **主文档：** [docs/jackett-stability.md](../../docs/jackett-stability.md)

---

## 文档内容摘要

| 章节 | 内容 |
|------|------|
| 三层架构 | VPS Docker → Jackett Indexer → ReleaseMatch 拉取管道 |
| 配置规范 | 禁用 `all` 聚合；推荐 tv/movie indexer 列表 |
| VPS healthcheck | `/opt/healthcheck.sh` + crontab 每 30 分钟 |
| 探测命令 | `status` / `poc_phase0` / BB S04E06 基准槽位 |
| FlareSolverr | 1337x 依赖、排错表 |

---

## 关联更新

- `docs/INDEX.md` — 新增 jackett-stability 索引
- `docs/jackett-remote-linode.md` — 交叉引用
- `docs/05-Jackett详解与安装使用教程.md` — 附录 A 链接
- `workflow/torrent_sources/accounts.example.json` — 推荐 indexer 列表（无 `all`）

---

## 配置待办（可选）

本地 `accounts.local.json` 若仍含 `"all"`，建议按主文档 §3.1 移除。
