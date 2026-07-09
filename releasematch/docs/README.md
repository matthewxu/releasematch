# 影视下载资源分支 — 文档索引

> **版本：** v1.1  
> **创建日期：** 2026-06-29  
> **定位：** 下载站采用 **独立顶级域名**（与字幕主域完全分离）；SEO 见 [01 独立域名 SEO v5.0（Google 2026 深度版）](./01-分支定位与流量获取.md)；数据爬取见 [02](./02-数据源技术方案-详细展开.md)

> **SEO 文档状态：** v5.2 + [04 双轨优先级 v1.1](./04-方案全景分析与优先级重评.md)；开发代码见 [releasematch/](../releasematch/)  
> **状态：** 📋 规划稿 + R0 脚手架；**执行顺序：T0 工具 → C0~C4 内容**

---

## 一、分支摘要

本分支 **不托管视频文件**，仅聚合、索引、展示 torrent **元数据**。流量策略：**独立域名** + Matched Release 导航 + 冷启动分批（M12 约 5K–10K 页，日 UV 500–1,200）；字幕主域仅 **单集上下文 1 链** 协同，不灌权重。

| 维度 | 字幕分支（现有） | 下载分支（新增） |
|------|----------------|----------------|
| **流量核心** | SEO：`subtitles` 意图 | SEO：`download` / `magnet` 意图 |
| 核心资产 | 100GB SRT + 元数据 | 清单/索引（magnet + 元数据） |
| 主路由 | `/subtitle/`（字幕主域） | `/` 根路径（**独立域**，如 `releasematch.io/breaking-bad/s4e6/`） |
| 工作流 | Step 0–5, 8 | Step 4c（`releasematch/workflow/torrent_sources`） |

**独立开发目录：** [releasematch/](../releasematch/) — 与 `subtitle-portal`、`tmdbpy/workflow/opensubtitles` 隔离。

---

## 二、文档目录

| 文档 | 说明 |
|------|------|
| [01-分支定位与流量获取.md](./01-分支定位与流量获取.md) | **独立域名 SEO 最佳方案**（冷启动、跨站规则、KPI） |
| [02-数据源技术方案-详细展开.md](./02-数据源技术方案-详细展开.md) | **核心**：四层数据源、日韩扩展、接口规格、Python 客户端、PoC |
| [**11-CN华语影视资源方案.md**](./11-CN华语影视资源方案.md) | **华语专用**：市场摘要、DMHy Layer 2F、`cn` 路由、稀缺分类、PoC |
| [03-工作流集成与模块规划.md](./03-工作流集成与模块规划.md) | 原 Step 4c 规划（**代码已迁移至 releasematch/**） |
| [04-方案全景分析与优先级重评.md](./04-方案全景分析与优先级重评.md) | **T0~T5 工具轨 + C0~C4 内容轨（v1.1，当前生效）** |
| [**12-日常运营执行手册.md**](./12-日常运营执行手册.md) | **日常运维**：巡检、cron、扩槽→生成→SEO 门禁 |
| [**13-用户互动方案.md**](./13-用户互动方案.md) | **用户互动**：X-09 结构化 tag · S-Community · 分期（规划稿） |
| [**14-各国合法平台与上线节奏清单.md**](./14-各国合法平台与上线节奏清单.md) | **行业基线**：各国合法 OTT / catch-up、PVOD 与 BT 生态上线节奏、RM 区域路由对照 |
| [../releasematch/README.md](../releasematch/README.md) | **独立代码库**：workflow / portal / extension |

---

## 三、关联文档（项目内）

| 路径 | 关系 |
|------|------|
| [seo/工作流-从数据清洗到上线全链路.md](../seo/工作流-从数据清洗到上线全链路.md) | 主工作流 10 步，本分支扩展 Step 4c |
| [seo/字幕站最优SEO方案-综合版.md](../seo/字幕站最优SEO方案-综合版.md) | 字幕主 SEO 引擎，下载页内链交叉引流 |
| [seo/01-竞品SEO深度分析报告.md](../seo/01-竞品SEO深度分析报告.md) | §4 影视下载站 SEO 模式对比 |
| [seo/07-用户痛点调研与可行解决方案.md](../seo/07-用户痛点调研与可行解决方案.md) | Q1 对版痛点 → 下载分支差异化 |
| [tmdbpy/workflow/opensubtitles/README.md](../tmdbpy/workflow/opensubtitles/README.md) | 爬虫模块范式（batch + on-demand + SQLite 缓存） |
| [docs/P2P引流三大核心动作.md](../docs/P2P引流三大核心动作.md) | Telegram + SEO 矩阵引流参考 |

---

## 四、Phase 0 快速验证（1 天）

```powershell
# 1. 启动 Jackett
docker run -d --name jackett -p 9117:9117 -v C:\jackett\config:/config linuxserver/jackett

# 2. Torznab 剧集搜索（Breaking Bad S04E06，TVDB 81189）
curl "http://127.0.0.1:9117/api/v2.0/indexers/1337x/results/torznab/api?apikey=KEY&t=tvsearch&tvdbid=81189&season=4&ep=6&cache=false"

# 3. EZTV JSON
curl "https://eztvx.to/api/get-torrents?imdb_id=904747&limit=10&page=1"

# 4. YTS 电影
curl "https://yts.mx/api/v2/movie_details.json?imdb_id=tt0133093"

# 5. Nyaa RSS（动漫 c=1_0）
curl "https://nyaa.si/?page=rss&q=Breaking+Bad&c=1_0"

# 6. 日韩 — Nyaa Live Action（c=4_0）
curl "https://nyaa.si/?page=rss&q=Crash+Landing+on+You&c=4_0"
curl "https://nyaa.si/?page=rss&q=Alice+in+Borderland&c=4_0"
```

详见 [02-数据源技术方案-详细展开.md](./02-数据源技术方案-详细展开.md) §十二。

---

## 五、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-29 | 初版：索引 + 三份专题文档 |
| v1.4 | 2026-06-29 | 01 改为独立顶级域名 SEO 专版 v4.0 |
| v1.5 | 2026-06-29 | 新增 04 优先级重评；代码迁移至 releasematch/ |
| v1.6 | 2026-06-29 | 04 升级为 v1.1：T/C 双轨（先工具后内容） |
