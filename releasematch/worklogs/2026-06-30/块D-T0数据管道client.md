# 块 D — T0 数据管道 client 实现

> **日期：** 2026-06-30  
> **状态：** T0 MVP 核心已通（剧集 + 电影单槽）

---

## 新增模块

| 文件 | 职责 |
|------|------|
| `eztv_client.py` | EZTV 直连（IMDb 7 位前导零） |
| `yts_client.py` | YTS 镜像回退 + magnet 构造 |
| `jackett_client.py` | Torznab XML 解析 + 剧集多模式回退 |
| `release_parser.py` | 标题正则解析 group/resolution/codec |
| `fetch_service.py` | 多源编排、去重、SQLite 缓存 |

---

## 验收命令

```bash
# 剧集 Breaking Bad S04E06（≥2 magnet）
python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6 --force

# 电影 The Matrix
python -m workflow.torrent_sources.run test --tmdb 603 --media-type movie --force
```

**结果：**

| 槽位 | count | 来源 |
|------|-------|------|
| tv:1396:s04e06 | 2 | EZTV 直连 |
| movie:603 | 3 | YTS 直连 |

Jackett 本机 indexer 仍 0 条；不影响 T0（EZTV/YTS 直连已满足薄页门禁）。

---

## 已知问题

1. EZTV `imdb_id` 须 `zfill(7)`（`tt0903747` → `0903747`）
2. 空结果被缓存 — 测试时用 `--force`
3. Jackett 剧集源待海外 VPS 或 FlareSolverr

---

## 下一步（T0 收尾 / T1）

- [x] `workflow.run run 4c --test` 透传 `--force`
- [x] `score_slot` 接真实 `fetch_service` items
- [ ] `groups.yaml`、跨源 `cross_source_count`
- [ ] 海外 Linode Jackett + 更新 `base_url`
