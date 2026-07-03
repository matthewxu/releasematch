# torrent_sources — 多源 magnet 清单模块

> **路径：** `releasematch/workflow/torrent_sources/`  
> **原规划路径：** `tmdbpy/workflow/torrent_sources/`（已废弃，见隔离说明）  
> **优先级：** **T0**（工具轨 Week 1~2）→ T1 全量

---

## 模块用途

从 Jackett / EZTV / YTS / Nyaa / **DMHy（动漫花园）** 拉取 torrent **元数据**（infohash、标题、seeders、magnet），不下载、不托管视频。

| 模式 | 命令 | 说明 |
|------|------|------|
| test | `test --tmdb 1396 --season 4 --episode 6` | 单槽测试 |
| batch | `batch --tier P0 --limit 100` | 批补（R0 待实现） |
| on-demand | `on-demand --tmdb 603 --media-type movie` | 访问 miss 回源（R1 待实现） |

---

## 目录结构（目标）

```
torrent_sources/
├── run.py                    # CLI 入口 ✅
├── config.py                 # 配置 ✅
├── models.py                 # 数据模型 ✅
├── cache_index.py            # SQLite 缓存 ✅
├── jackett_client.py         # Layer 1 🔧 R0
├── eztv_client.py            # Layer 2A 🔧 R0
├── yts_client.py             # Layer 2B 🔧 R0
├── nyaa_client.py            # Layer 2C 🔧 R1
├── nyaa_live_action_client.py # Layer 2D 日韩真人 🔧 R1
├── dmhy_client.py            # Layer 2F 中文 DMHy 🔧 R1
├── release_parser.py         # 归一化 🔧 R1
├── fetch_service.py          # 编排层 🔧 R0
├── batch_fetch.py            # 批补 🔧 R1
├── on_demand_fetch.py        # 按需 🔧 R1
├── speedtest/                # 测速子模块 🔧 R2
└── data/
```

---

## 与字幕站 opensubtitles 的差异

| 项 | opensubtitles | torrent_sources |
|----|---------------|-----------------|
| 输出 | SRT 文件 | magnet 元数据 |
| Primary 对齐 | 字幕 release | **本站 Recommended Release**（`recommended/scorer.py`） |
| 上线目标 | subtitle-portal R2 | **releasematch/portal D1** |
| 总控 | tmdbpy/workflow/run.py 4b | releasematch/workflow/run.py 4c |

---

## 隔离说明

本模块 **不 import** `workflow.opensubtitles`、`subtitle-portal` 或字幕 Primary 相关代码。  
可选只读 TMDB 元数据见 `workflow/metadata/external_ids.py`。
