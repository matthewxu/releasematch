# 页面生成器（T3）

> **路径：** `releasematch/portal/generator/`  
> **优先级：** **T3**（工具轨 Week 7）— **阻塞 C1 验证集**  
> **方案：** [04-方案全景分析与优先级重评.md](../../download-resources/04-方案全景分析与优先级重评.md) §4.2 T3

---

## 职责

将「槽位 + D1 数据 + IG 引擎输出」转换为一页静态 HTML，供 CF Pages 部署。

```
输入：
  tmdb_id, season?, episode?
  ← workflow/torrent_sources/（magnet 列表）
  ← workflow/recommended/scorer.py（Recommended + reason）
  ← workflow/torrent_sources/speedtest/（测速摘要，T2 后）
  ← Group DB / 编码 P1 / 跨源 badge（T1）

输出：
  portal/dist/breaking-bad/s4e6/index.html
  （magnet ≥ 2 才生成 index 页，否则 skip 或 noindex 占位）
```

---

## 与内容轨的关系

| 阶段 | 动作 |
|------|------|
| T3 完成 | 生成器可对任意槽位出页 |
| **C1** | 生成器 batch 产出 **20 页验证集** + 人工 QA |
| **C2** | 将 C1 产出物提交 sitemap / GSC |
| **C4** | 生成器 batch +100 / +200 规模扩展 |

**页面生成器是工具；验证集与规模页都是它的 batch 运行结果。**

---

## 待实现（R0 脚手架阶段占位）

- [x] `render.py` — Jinja2 渲染
- [x] `generate_one.py` — 单页/批量 CLI（`workflow.run generate`）
- [x] `dev_server.py` — 本地开发服（`workflow.run serve`，实时读 MySQL）
- [ ] `generate_batch.py` — 读 `priority/queue_builder.py` 队列
- [ ] 薄页门禁与 canonical 注入（生成器内置部分已完成）

---

## 模板与 partial（2026-07-05）

| 模板 | 说明 |
|------|------|
| `templates/episode.html` · `movie.html` | 槽位页壳 |
| `partials/recommended_block.html` | Hero：**表格 → 理由 → Grab → 背书 → 折叠测速** |
| `partials/recommended_release_table.html` | Hero REC 表格（与 Sources 同列） |
| `partials/sources_table_row.html` | 剧集 / 电影共用表行 |
| `partials/movie_edition_groups.html` | 电影 All Versions 按 edition 分组 |
| `partials/speed_evidence_panel.html` | 展开测速证据（**无重复 Grab**） |

上下文组装：`schema/d1_models.py` · 电影分组：`workflow/movie_editions.py` · 详见 [IG §4.1](../../docs/IG信息登记册.md#41-recommended-区块信息架构2026-07-05)。

---

## 页面 head / SEO（2026-07-05 · T-SEO-04/05）

| 能力 | 位置 | 说明 |
|------|------|------|
| **Open Graph + Twitter** | `templates/base.html` | `og:site_name/type/url/title/description`；episode `video.episode` · movie `video.movie` |
| **Favicon** | `portal/static/favicon.ico` · `.svg` | `base.html` + Trust 五页静态 HTML |
| **JSON-LD** | `episode.html` / `movie.html` / `home.html` | TVEpisode · Movie · WebSite（`build_*_schema_ld`） |
| **C2 验收** | `scripts/seo_c2_checklist.py` | 本地 §6.1～6.3；generate 后须 sync Trust/static 进 dist |

Trust 壳（About / Contact / DMCA / Privacy / How-matching-works）为 `portal/trust/` 静态页，**不**经 Jinja；部署前复制到 `portal/dist/trust/`。
