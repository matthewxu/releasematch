# Ops 上线 UI 流程测试 · Friends + Whiplash

> **日期：** 2026-07-19  
> **方式：** Ops API（与 UI 同一路由）；浏览器抽查公网页  
> **批次：** `20260719T091241Z-c2579576`

## 选片

| 类型 | 作品 | page_id | 结果 |
|------|------|---------|------|
| TV | Friends S01E01 | `tv:1668:s01e01` | magnet=100 · Rec · indexable · `/friends/s1e1/` |
| 电影 | Whiplash | `movie:244786` | magnet=3 · Rec · indexable · `/whiplash/` |

## 步骤结果

| 段 | 动作 | 结果 |
|----|------|------|
| ① | TMDB 导出 ensure + 搜索 + 季集 + 并入工作区 | ✅ |
| ② | 导入跟踪表 | ✅ batch 创建 |
| ③ | pipeline live | ✅ 179s · 2/2 ok |
| ③ | generate | ✅（须用 `.venv` 重启 Ops；旧进程缺 `BLOCK_CRAWLERS` / 错 Python 缺 jinja2） |
| ④ | seo_c2 | ✅ 16 pass / 0 fail |
| ④ | deploy prepare-only | ✅ |
| ④ | wrangler deploy | ✅ Version `47a91557-a1a6-4b15-a229-7983ef2a6194` |

## 公网验收

- https://www.releasematch.com/friends/s1e1/ → 200 · Recommended · magnet · noindex  
- https://www.releasematch.com/whiplash/ → 200 · Recommended · magnet · noindex  
- https://www.releasematch.com/friends/ → 200 · Hub（`ensure_show_hub_page` 补齐后）

## 踩坑

1. **Ops 须用** `releasematch/.venv/bin/python -m workflow.run ops serve`（系统 `python3` 可能无 jinja2）。  
2. **改代码后须重启** Ops，否则 generate 报 `cannot import BLOCK_CRAWLERS`。  
3. 测速原先未自动 bake；Ops「测速 write」成功后现已 **自动 `run_generate`**，线上才有 Grab / 测速面板。

## 跟进修复（同日 · 布局与 Hub）

| # | 问题 | 处理 |
|---|------|------|
| 1 | `/friends/` Hub 404 | `MySQLStore.ensure_show_hub_page`；`ensure_slot_page` / Ops generate 同步 Hub |
| 2 | 测速后页面无 Grab | Ops `run_speedtest` 成功后自动 regenerate |
| 3 | 剧集表列宽错乱 / 省略号 | Recommended 与 All Sources 共用 `rm-table--episode` + `rm-col-*` 固定列宽；禁止 ellipsis，长文案换行 |
| 4 | All Sources 需横向拖、Group 过宽 | `table-layout: fixed` + Group badge 可换行；表宽 100% |
| 5 | 页面宽度与 Whiplash 不一致 | 主栏 `minmax(0,1fr)` + `--rm-max-width:1120` / sidebar `320` |
| 6 | CSS 缓存旧规则 | `static_asset_version()` → `design-system.css?v=…` |

**验收（硬刷新后）：** Friends / Whiplash 均为 container **1120** · 主栏 **736** · 侧栏 **320**；两表列百分比对齐、无需横向滚动。

**测速报告留档：** `worklogs/ops/speedtest-friends-whiplash.json`
