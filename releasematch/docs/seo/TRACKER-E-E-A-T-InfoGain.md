# E-E-A-T · Info Gain · SEO 跟进看板

> **Living Document** — 随 SEO 迭代持续更新  
> **创建：** 2026-07-04 · **最近更新：** 2026-07-05  
> **功能性邮箱：** `ReleaseMatch@hotmail.com`（Contact · DMCA · Privacy）  
> **基线评估：** [2026-07-04 基线评估](./assessments/2026-07-04-E-E-A-T与Info-Gain基线评估.md)  
> **IG 字段权威：** [IG信息登记册.md](../IG信息登记册.md)  
> **IG Debug 批量汇总：** [ig-debug-batch-summary.md](../../worklogs/2026-07-05/ig-debug-batch-summary.md)（2026-07-05 · 未重拉）

---

## 一、当前基线快照

> 阶段切换或重大变更后更新本表；历史快照留在 `assessments/`。

| 项 | 当前值 | 目标（C3 前） | 状态 |
|----|--------|--------------|------|
| **内容轨** | C2 SEO 冷启动 | C3 沙盒观察 | 🟡 |
| **published 页** | 118 | — | ✅ |
| **sitemap URL 数** | ≤36（+Contact） | 维持 ≤30 内容页 + Trust | ✅ |
| **GSC** | 未提交 | C2 门禁通过后提交 | ⏸ |
| **CF Pages 生产** | 暂缓 | C2 门禁通过后 | ⏸ |
| **页面 IG 估分（Debug 呈现）** | **8~9（97/120）** · 7~8（8）· ≤5~7（15） | Rec+测速页 **8~9** | ✅ |
| **页面 IG 估分（质量向）** | **5~7**（cross≥2 仅 1/104 · L4 Rec 39/104） | **≥7** | 🔴 |
| **测速 bake 覆盖率** | **96/104 Rec** · 97/120 summary | **100%**（有 Rec 页） | 🔶 |
| **E-E-A-T 综合** | Trust B+ · Experience B+ · Expertise A- · Auth C | Trust A- · Experience A | 🟡 |

---

## 二、E-E-A-T 跟进清单

### 2.1 Trust（信任）— 权重最高

**功能性邮箱（全站 Trust 联络）：** [ReleaseMatch@hotmail.com](mailto:ReleaseMatch@hotmail.com)

| # | 信号 | 要求 | 状态 | 负责 | 备注 |
|---|------|------|------|------|------|
| T-01 | About 页 | Day 1 | ✅ | C0 | `/trust/about/` · `lang=en` |
| T-02 | DMCA 政策 | Day 1 | ✅ | C0 | `/trust/dmca/` · 邮箱同上 |
| T-03 | Privacy Policy | Day 1 | ✅ | C0 | `/trust/privacy/` · meta description 已补 |
| T-04 | 对版方法论 | Day 1 | ✅ | C0 | `/trust/how-matching-works/` |
| T-05 | **Contact 页** | Day 1 | ✅ | C0 | `/trust/contact/` · `ReleaseMatch@hotmail.com` |
| T-06 | magnet nofollow | 全站 | ✅ | T3 | |
| T-07 | 无假播放器 | 全站 | ✅ | — | |
| T-08 | 410 Gone | DMCA 下架 | ✅ | C2 | `portal/410.html` |
| T-09 | Trust 页 `lang=en` | 与内容页一致 | ✅ | C2 | 五页 Trust 已英文化 |
| T-10 | 演示页与 DB 一致 | 禁用手写 demo | ✅ | T3 | 已删 `portal/` 手写内容页；仅 `dist/` + `serve` |
| T-11 | 独立域名隔离 | 规避 SRA | ✅ | — | releasematch.io |

### 2.2 Experience（经验）

> **数据快照（2026-07-05）：** renderable **120**（indexable **118**）· 有 Recommended **104/120** · Rec+测速 **96/104** · cron `--all-published` 每 6h · thin **2** 页 noindex dist · 批量 IG Debug 见 [worklog](../../worklogs/2026-07-05/ig-debug-batch-summary.md)

| # | 信号 | 要求 | 状态 | IG-ID | 备注 |
|---|------|------|------|-------|------|
| E-01 | VPS/libtorrent 测速 | cron 每 6h | ✅ | S-06 | Rec+summary **96/104** · cron 已上线 |
| E-02 | 测速 bake 进 HTML | 静态可爬 | ✅ | S-06 | `generate all` 120 页（118 index + 2 thin）· 97/120 有 evidence |
| E-03 | grab_index Hero | Recommended 卡片（表格 → 理由 → **Grab**） | ✅ | S-07 | 折叠测速内已去重；0 peers 槽分偏弱 |
| E-04 | speed_endorsement 文案 | 实测背书句 | ✅ | S-07 | Rec+summary 页已 bake；8 页 Rec 无 summary 不适用 |
| E-05 | recommend_reason 含实测事实 | UTC + peers 对比 | ✅ | S-02 | A-10 合并 **95/104 Rec** · `_merge_measured_into_recommend_reason` |
| E-06 | tested_at 页面展示 | 更新时间 | 🔶 | A-03 | 有 summary 页已展示；**16 页**无 Recommended 无测速 |
| E-07 | 索引 vs 实测 peers 对比 | 独家事实句 | ✅ | A-10 | 面板 + **已并入 recommend_reason** |
| E-08 | thin 降级仍输出 HTML | noindex UX | ✅ | — | `list_renderable_page_ids` · thin 页 `noindex,follow` 进 dist |

### 2.3 Expertise（专业）

| # | 信号 | 要求 | 状态 | IG-ID | 备注 |
|---|------|------|------|-------|------|
| X-01 | groups.yaml 分档 | L0~L4 | ✅ | S-05 | **102** 组 |
| X-02 | Group badge Hero | Recommended 表格 Group 列 | ✅ | S-05 | |
| X-03 | Group badge Sources 表 | 逐条 | ✅ | S-05 | `sources_table_row.html` |
| X-04 | 跨源 N/M Hero badge | 页面级 | ✅ | S-03 | 数据多为 1/3 |
| X-05 | 跨源 confidence Sources | 单条 badge | ❌ | S-04 | |
| X-06 | release 解析 | source/codec/res | ✅ | A-05 | |
| X-07 | BB 高频组入库 | XEBEC/FQM/IMMERSE/ASAP | ✅ | S-05 | yaml **98→102** 组 · 2026-07-05 rescore |
| X-08 | scene_compliant | 入 reason | ✅ | S-02 | L0~L2 已知组 · Scene/P2P 短句 |
| X-09 | 音轨/剪辑对版段落 | 人工编辑 | 📋 | — | 最高 IG，未启动 |

### 2.4 Authoritativeness（权威）

| # | 信号 | 要求 | 状态 | 备注 |
|---|------|------|------|------|
| A-01 | GSC 属性 + sitemap 提交 | C2 后 | ⏸ | |
| A-02 | 自然外链 | 持续 | ❌ | 未启动 |
| A-03 | Stremio 插件 | T4 | 📋 | 09 文档 |
| A-04 | 社区/Reddit  presence | 长期 | ❌ | |
| A-05 | 品牌搜索量 | 长期 | ❌ | 新域 |

**图例：** ✅ 完成 · 🔶 部分 · ❌ 未做 · 📋 规划 · ⏸ 暂缓

---

## 三、Info Gain 字段跟进

> 详细计算逻辑见 [IG信息登记册.md](../IG信息登记册.md)。本表只跟踪 **页面呈现 + 数据质量**。

### 3.1 S 级字段（8~10 分核心）

| IG-ID | 名称 | 后端 | 页面 bake | 数据质量 | 下一动作 |
|-------|------|------|-----------|----------|----------|
| S-01 | Recommended Release | ✅ | ✅ | ✅ | — |
| S-02 | recommend_reason | ✅ | ✅ | ✅ 有 Rec 页 | — |
| S-03 | 跨源 N/M | ✅ | ✅ | ⚠️ 多数 1/3 | 修 Nyaa/EZTV |
| S-04 | hash confidence | ✅ | 🔶 | ❌ 全 0.333 | P3：fuzzy 对齐 |
| S-05 | Group tier | ✅ | ✅ Hero | 🔶 L4 Rec **43/109**（↓ yaml 补库后） | 继续扩 yaml |
| S-06 | 实测速度 | ✅ | ✅ | ✅ **96/104 Rec** | 8 页 Rec 无 summary · 16 页无 Rec |
| S-07 | 实测背书 | ✅ | 🔶 | 🔶 不可达槽弱 | 琅琊榜/三体 timeout 观察 |
| S-08 | 多地域测速 | 📋 | 📋 | — | P2+ |

### 3.2 页面 IG 估分目标

> **2026-07-05 批量 IG Debug**（120 renderable · [明细](../../worklogs/2026-07-05/ig-debug-batch-summary.md)）：**Debug 呈现**与**质量向**分列。

| 页面类型 | Debug 呈现（当前） | 质量向（当前） | C3 目标 | 关键提升项 |
|----------|-------------------|---------------|---------|-----------|
| 单集 L3（Rec + 测速） | **8~9**（49 页） | 5~7 | 8~9 | cross 2/3 · 补 yaml L1~L3 |
| 单集 L3（Rec 无测速） | **7~8**（1 页） | 5~7 | 7~8 | 测速 cron 覆盖 |
| 单集 L3（无 Rec） | **5~7 / 0~1**（7 页） | 2~4 | noindex | scorer 修复 |
| 电影（Rec + 测速） | **8~9**（48 页） | 5~7 | 7~9 | 同单集 + edition 分组 |
| 电影（Rec 无测速） | **7~8**（7 页） | 5~7 | 8~9 | 电影槽 cron 测速 |
| 电影（无 Rec） | **0~1**（8 页） | 0~1 | noindex / 补 magnet | pipeline |
| Trust 页 | — | — | Trust A- | Contact ✅ · lang=en ✅ |

### 3.3 IG 缺口 → 开发映射

| 优先级 | IG-ID | 缺口 | 负责模块 | 状态 |
|--------|-------|------|----------|------|
| P0 | A-01,A-03,S-07 | speed 面板 + endorsement 已渲染 | T2+T3 | ✅ 有 Rec 页 |
| P0 | A-07 | timeout 条目隐藏 | T2+T3 | ❌ |
| P0 | A-10 | 索引/实测句已并入 **recommend_reason** | T3 | ✅ 有 Rec 页 |
| P1 | S-05 | 补 groups.yaml（BB 首批 4 组） | T1 | ✅ |
| P1 | S-05 | 补 groups.yaml（MeGusta/AFG 等全库高频） | T1 | ❌ |
| P1 | S-05 | Sources 表 tier badge | T3 | ❌ |
| P1 | S-06 | 批量 slot cron 增量 TTL | T2 | ✅ cron |
| P1 | S-04 | title/fuzzy 跨源对齐 | T1 | ❌ |
| P2 | S-05 | scene_compliant 入 reason（静态句） | T1 | ✅ |
| P2 | S-05 | cron 动态 compliance_rate | T1 | ❌ |
| P2 | S-08 | 多节点 Worker | T2+ | 📋 |

---

## 四、SEO 元素矩阵

> 技术 SEO 细节任务见 [worklog SEO 审计](../../worklogs/2026-07-03/页面SEO分析与优化方向.md)；发版跑 `seo_c2_checklist.py`。

### 4.1 技术 SEO

| 元素 | 状态 | 文档/工具 | 下一动作 |
|------|------|-----------|----------|
| sitemap.xml | ✅ ≤35 URL | `portal/generator/sitemap.py` | C2 后提交 GSC |
| robots.txt | ✅ | dist | — |
| canonical | ✅ | 生成器 | — |
| 薄页 robots | ✅ | `is_indexable()` | — |
| Hub noindex | ✅ | D2 决策 | — |
| lang=en | ✅ | 内容页 + Trust 五页 | — |
| Schema JSON-LD | 🔶 | WebPage only | P1：TVEpisode |
| Open Graph | ❌ | — | P1 |
| favicon | ❌ | — | P1 |
| BreadcrumbList | ❌ | — | P2 |

### 4.2 内容 SEO / 政策

| 元素 | 状态 | 说明 |
|------|------|------|
| Information Gain | 🟡 Debug **8~9**（97 页）· 质量 **5~7** | 本看板 §一 · §3.2 |
| Scaled Content 合规 | ✅ | 薄页门禁 + sitemap 限批 |
| Helpful Content | 🟡 | 依赖 IG 提升 |
| Pirate Demotion 防护 | 🟡 | 独立域 + DMCA；垂直风险仍在 |
| TMDB 复述风险 | ⚠️ | 侧栏 overview 待缩短/折叠 |
| 内链 prev/next | ✅ | 单集 L3 |
| subtitle 跨站链 | ✅ nofollow | D4 决策 |

### 4.3 度量（C2 后启用）

| 指标 | 基线 | 目标 C3 | 数据源 |
|------|------|---------|--------|
| GSC 收录率 | — | >25% | GSC |
| indexable 页 indexed 数 | 0 | ~20 | GSC |
| 品牌词 impression | 0 | >0 | GSC |
| 长尾词 Top 50 排名 | — | 跟踪 | GSC / 第三方 |
| 单页 IG debug 分布 | 8~9 **97** · 7~8 **8** · ≤5~7 **15** | Rec+测速 **≥8~9** | [批量汇总](../../worklogs/2026-07-05/ig-debug-batch-summary.md) |
| 质量向 IG（cross/L4） | cross≥2 **1/104** · L4 Rec **39/104** | cross≥2 占比 ↑ | MySQL · 登记册 §九 |

---

## 五、迭代日志

> 每次 SEO/IG 相关合并或里程碑完成后追加一行。详细过程可另建 `iterations/YYYY-MM-DD-*.md`。

| 日期 | 版本/Commit | 变更摘要 | E-E-A-T 影响 | IG 影响 | 验收 |
|------|-------------|----------|-------------|---------|------|
| 2026-07-04 | — | 初建 `docs/seo/` + 基线评估 + 本看板 | 建立跟进体系 | 基线 5~7 分建档 | 文档 review |
| 2026-07-04 | C2 SEO | sitemap ≤35 · 410 · Hub noindex · lang=en | Trust/技术 SEO ↑ | — | seo_c2_checklist |
| 2026-07-04 | cron | VPS 测速 `--all-published` 每 6h | Experience ↑ | S-06 数据 ↑ | 92/114 ok |
| 2026-07-05 | Trust | Contact 页 + 五页 `lang=en` + `ReleaseMatch@hotmail.com` | Trust ↑ | — | `/trust/contact/` |
| 2026-07-05 | E-05 | `recommend_reason` 合并 A-10 实测句（生成器） | Experience ↑ | S-02 ↑ | BB S04E06 验收 |
| 2026-07-05 | 测速+dist | 4 槽 gap-fill 测速 · `generate all` 120 页 | E-02/E-05 ✅ | S-06 96/96 Rec | speedtest-cn-gap-fill.json |
| 2026-07-05 | T-10 | 删除 `portal/` 手写 demo（BB S04E6 等） | Trust ↑ | 避免虚假 cross/tier | generate page 验收 |
| 2026-07-05 | IG Debug | 全站 120 页批量 Debug（未重拉）· §一基线刷新 | — | Debug **8~9：97** · 质量仍 **5~7** | [ig-debug-batch-summary.md](../../worklogs/2026-07-05/ig-debug-batch-summary.md) |
| 2026-07-05 | X-07/X-08 | groups.yaml +4（XEBEC/FQM/IMMERSE/ASAP）· scene_compliant 入 reason · rescore 107 页 | Expertise ↑ | S-05 XEBEC **L1** · S-02 合规句 | BB S04E06 · L4 Rec 43/109 |
| | | | | | |

**下一迭代待办（摘自基线评估 P0/P1）：**

- [x] P0：生成器 100% DB 驱动，清理手写 demo 页（T-10）
- [x] P0：`recommend_reason` 合并 A-10 实测句（E-05 · 有 Rec 页 96/96）
- [x] P1：补 `groups.yaml` BB 首批 4 组（X-07 · XEBEC/FQM/IMMERSE/ASAP）
- [ ] P1：补 `groups.yaml` 全库高频 L4 组（MeGusta/AFG/DL 等）
- [x] P1：有 Recommended 页测速 summary 100%（E-02 · 96/96）
- [ ] P1：**16 页**无 Recommended 的 pipeline/scorer 修复（非测速 cron 范围）
- [ ] P1：**8 页** Rec 无测速 summary（7 电影 + 1 单集）· 电影 cron 覆盖
- [x] P2：Trust 页 `lang=en` + Contact 页（T-05/T-09）· 邮箱 `ReleaseMatch@hotmail.com`

---

## 六、复盘节奏

| 频率 | 动作 | 产出 |
|------|------|------|
| **每次 SEO 相关 PR** | 更新 §五迭代日志 + 相关清单项 | 看板 diff |
| **扩槽 / generate all 后** | 抽查 3 页 IG debug · 跑 seo_c2_checklist | worklog 勾选 |
| **阶段切换（C2→C3）** | 新写一篇 `assessments/` 评估 | 阶段快照 |
| **月度** | 更新 §一基线 · §3.2 估分 · §4.3 度量 | 月度 SEO 摘要（可选 `iterations/`） |

---

## 七、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-04 | 初建看板；同步基线评估结论 |
| v1.1 | 2026-07-05 | T-05 Contact · T-09 lang=en · 功能性邮箱 `ReleaseMatch@hotmail.com` |
| v1.2 | 2026-07-05 | T-10 清理 portal/ 手写 demo 页 |
| v1.3 | 2026-07-05 | §2.2 Experience 对齐代码与 DB（93/118 测速 · E-04/E-07 已实现） |
| v1.4 | 2026-07-05 | E-05：`recommend_reason` 渲染期合并 A-10 实测句 |
| v1.5 | 2026-07-05 | 测速 gap-fill 4 槽 + `generate all` · E-02/E-05 有 Rec 页闭合 |
| v1.6 | 2026-07-05 | 全站 IG Debug 批量汇总 · §一拆 Debug/质量双轨 · §3.2/§4.3/§五同步 |
| v1.7 | 2026-07-05 | X-07 yaml +4 组 · X-08 scene_compliant 入 reason · rescore 107 页 |
