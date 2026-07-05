# E-E-A-T · Info Gain · SEO 跟进看板

> **Living Document** — 随 SEO 迭代持续更新  
> **创建：** 2026-07-04 · **最近更新：** 2026-07-06（质量向定义拆分 · Hero 文案语义修正）  
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
| **published 页** | **117**（indexable） | — | ✅ |
| **sitemap URL 数** | ≤36（+Contact） | 维持 ≤30 内容页 + Trust | ✅ |
| **GSC** | 未提交 | C2 门禁通过后提交 | ⏸ |
| **CF Pages 生产** | 暂缓 | C2 本地门禁通过后 deploy | ⏸ |
| **C2 本地 SEO 门禁** | **13 pass / 0 fail**（§6.1～6.3） | deploy + GSC | ✅ 本地 |
| **页面 IG 估分（Debug 呈现）** | **8~9（109/120）** · 7~8（6）· 0~1（5） | Rec+测速页 **8~9** | ✅ |
| **页面 IG 估分（质量向）** | 见 **§3.2.1** · 主轨 **7+：98/110** · S-04 验证 **8/110** · L4 Rec **12** | **主轨维持 · S-04 辅轨↑** | 🔶 |
| **测速 bake 覆盖率** | **110/110 Rec** 有 summary | **100%**（有 Rec 页） | ✅ |
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

> **数据快照（2026-07-06）：** renderable **120** · indexable **110** · 有 Recommended **110/115 published** · Rec+测速 **110/110** · cross≥2 **8/110** · L4 Rec **12** · VPS `172.236.156.193` · 迭代见 [宽松 fuzzy 与 groups 补档](./iterations/2026-07-06-宽松fuzzy与groups补档.md)

| # | 信号 | 要求 | 状态 | IG-ID | 备注 |
|---|------|------|------|-------|------|
| E-01 | VPS/libtorrent 测速 | cron 每 6h | ✅ | S-06 | Rec+summary **107/107** · cron 已上线 |
| E-02 | 测速 bake 进 HTML | 静态可爬 | ✅ | S-06 | `generate all` 120 页 · **110** 有 Rec+evidence |
| E-03 | grab_index Hero | Recommended 卡片（表格 → 理由 → **Grab**） | ✅ | S-07 | 折叠测速内已去重；0 peers 槽分偏弱 |
| E-04 | speed_endorsement 文案 | 实测背书句 | ✅ | S-07 | Rec+summary 页已 bake；无 Rec 页已 noindex |
| E-05 | recommend_reason 含实测事实 | UTC + peers 对比 | ✅ | S-02 | A-10 合并 **107/107 Rec** · `_merge_measured_into_recommend_reason` |
| E-06 | tested_at 页面展示 | 更新时间 | ✅ | A-03 | 有 Rec+测速页已展示；**10** 页无 Rec 已 noindex |
| E-07 | 索引 vs 实测 peers 对比 | 独家事实句 | ✅ | A-10 | 面板 + **已并入 recommend_reason** |
| E-08 | thin 降级仍输出 HTML | noindex UX | ✅ | — | `list_renderable_page_ids` · thin 页 `noindex,follow` 进 dist |

### 2.3 Expertise（专业）

| # | 信号 | 要求 | 状态 | IG-ID | 备注 |
|---|------|------|------|-------|------|
| X-01 | groups.yaml 分档 | L0~L4 | ✅ | S-05 | **123** 组（+12 · 2026-07-06） |
| X-02 | Group badge Hero | Recommended 表格 Group 列 | ✅ | S-05 | |
| X-03 | Group badge Sources 表 | 逐条 | ✅ | S-05 | `sources_table_row.html` |
| X-04 | 跨源 N/M Hero badge | 页面级 | 🔶 | S-03 | 文案 **「N/M 源有结果」**（覆盖，非验证）；见 [语义修订](./iterations/2026-07-06-跨源语义与质量向定义.md) |
| X-05 | 跨源 confidence Sources | 单条 badge | ✅ | S-04 | 三档 fuzzy strict/no_group/slot_resolution |
| X-06 | release 解析 | source/codec/res | 🔶 | A-05 | `[GROUP]` / `...Hon3y` 尾缀 · 空组名 Rec 仍 12 L4 |
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
| S-03 | 跨源 N/M | ✅ | ✅ | 🔶 **覆盖** N avg **1.07** / M **3.67** | Hero「源有结果」· 非验证 |
| S-04 | hash confidence | ✅ | ✅ | 🔶 **验证** 页 **8/110** | Sources Verify 列 |
| S-05 | Group tier | ✅ | ✅ Hero+Sources | 🔶 L4 Rec **12**（24→12） | 空组名 / 华语标题 parser |
| S-06 | 实测速度 | ✅ | ✅ | ✅ **110/110 Rec** | cron 维持 |
| S-07 | 实测背书 | ✅ | 🔶 | 🔶 不可达槽弱 | 琅琊榜/三体 timeout 观察 |
| S-08 | 多地域测速 | 📋 | 📋 | — | P2+ |

### 3.2 页面 IG 估分目标（Debug 呈现）

> 算法见 `ig_debug._estimate_page_ig`；与质量向 **分列**（§3.2.1）。

| 页面类型 | Debug 呈现（当前） | C3 目标 |
|----------|-------------------|---------|
| Rec + 测速 | **8~9**（109 页） | 维持 |
| 无 Rec / thin | **0~1** | noindex |

### 3.2.1 质量向估分规则（2026-07-06 修订）

> **问题：** 原先把 Hero **N/M**（S-03 覆盖）与 **cross≥2**（S-04 验证）混为同一「质量向」升降机，导致 cross「长期不提升」的错觉。  
> **修订：** 拆成 **主轨 / 覆盖轨 / 验证轨**；质量向 **7+** 不再以页面 cross≥2 为主条件。

| 轨道 | IG-ID | 指标 | 当前基线 | 角色 |
|------|-------|------|----------|------|
| **主轨（质量向 7+）** | S-02,S-05,S-06 | Rec + 测速 + Group **L0~L3** | **98/110** | **决定质量向档位** |
| **覆盖轨** | S-03 | Hero **N/M 源有结果** | N avg **1.07**，M avg **3.67** | Experience / 可得性 |
| **验证轨** | S-04 | 页面存在任一条 **cross≥2**，或 Rec 条 cross≥2 | **8/110** 页 | Expertise 加分；公网稀缺 |

**质量向档位（手工代理，非 Debug 算法）：**

| 档位 | 条件 |
|------|------|
| **7+** | 主轨满足（Rec + 测速 + L0~L3） |
| **5~7** | Rec + 测速，但 **L4** Rec 或缺 Group 解析 |
| **2~4** | 无 Rec 或缺测速（多数已 noindex） |

**Hero 文案（已落地）：** `{N}/{M} sources with results` / `{N}/{M} 源有结果` — 对应 S-03 only。  
**Sources 表：** Verify 列仅在 `cross_source_count > 1` 时显示 badge — 对应 S-04。

| 页面类型 | 质量向（当前） | C3 目标 | 关键提升项 |
|----------|---------------|---------|-----------|
| Rec + 测速 + L0~L3 | **7+**（**98/110**） | 维持 | release_parser 空组名 |
| Rec + 测速 + L4 | **5~7**（**12** 页） | 降 L4 | yaml + parser |
| S-04 验证（任一 cross≥2） | **8** 页 | 占比 ↑（非主轨硬门槛） | indexer 重叠 · fuzzy |
| Trust 页 | — | Trust A- | Contact ✅ · lang=en ✅ |

### 3.3 IG 缺口 → 开发映射

| 优先级 | IG-ID | 缺口 | 负责模块 | 状态 |
|--------|-------|------|----------|------|
| P0 | A-01,A-03,S-07 | speed 面板 + endorsement 已渲染 | T2+T3 | ✅ 有 Rec 页 |
| P0 | A-07 | timeout 条目隐藏 | T2+T3 | ✅ |
| P0 | A-10 | 索引/实测句已并入 **recommend_reason** | T3 | ✅ 有 Rec 页 |
| P1 | S-05 | 补 groups.yaml（BB 首批 4 组） | T1 | ✅ |
| P1 | S-05 | 补 groups.yaml（MeGusta/AFG 等全库高频） | T1 | ✅ +9 组 |
| P1 | S-05 | Sources 表 tier badge | T3 | ✅ |
| P1 | S-06 | 批量 slot cron 增量 TTL | T2 | ✅ cron |
| P1 | S-04 | title/fuzzy 跨源对齐 | T1 | ✅ |
| P1 | A-07 | timeout 无 peers 隐藏测速面板 | T3 | ✅ |
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
| 薄页 robots | ✅ | `is_indexable()` · **无 Rec → noindex** | — |
| Hub noindex | ✅ | D2 决策 | — |
| lang=en | ✅ | 内容页 + Trust 五页 | — |
| Schema JSON-LD | ✅ | TVEpisode / Movie / WebSite | — |
| Open Graph | ✅ | `base.html` og:* + Twitter Card | — |
| favicon | ✅ | `/static/favicon.ico` + `.svg` | — |
| BreadcrumbList | ✅ | episode/movie | T-SEO-08 |

### 4.2 内容 SEO / 政策

| 元素 | 状态 | 说明 |
|------|------|------|
| Information Gain | 🟡 Debug **8~9**（109）· 质量主轨 **7+：98/110** · S-04 **8** 页 | §3.2.1 |
| Scaled Content 合规 | ✅ | 薄页门禁 + **无 Rec noindex** + sitemap 限批 |
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
| 单页 IG debug 分布 | 8~9 **109** · 7~8 **6** · 0~1 **5** | Rec+测速 **≥8~9** | [批量汇总](../../worklogs/2026-07-05/ig-debug-batch-summary.md) · 2026-07-06 重算后 |
| 质量向 IG（主轨 / S-04） | 主轨 7+ **98/110** · S-04 **8/110** · L4 Rec **12** | S-04 占比 ↑（辅轨） | §3.2.1 |

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
| 2026-07-05 | T-SEO-04/05 | OG + favicon + WebSite Schema · Trust favicon · C2 checklist **13 pass** | 技术 SEO ↑ | — | seo_c2_checklist |
| 2026-07-05 | S-04/X-05 | fuzzy 跨源对齐 + Sources Cross badge · `recompute_cross_source_fuzzy.py` | Expertise ↑ | S-04 页面 bake | 不重拉 DB 重算 |
| 2026-07-05 | A-07 | timeout/error 无 peers → 不 bake speed_evidence | Experience ↑ | 琅琊榜/三体弱槽 | 生成器 |
| 2026-07-05 | X-07b | groups.yaml +9（MeGusta/AFG/DL…）· **111** 组 | Expertise ↑ | S-05 tier 命中 ↑ | rescore |
| 2026-07-05 | `5ed2784` | 跨源 per-indexer（TPB/1337x）· 无 Rec noindex · `pipeline refetch-all` · VPS `172.236.156.193` | Trust/Scaled ↑ | S-03 分母 **3.28** avg · S-06 **107/107** | [迭代](./iterations/2026-07-05-跨源扩展与全站重拉.md) |
| 2026-07-05 | T-SEO-08 | BreadcrumbList JSON-LD · episode/movie | 技术 SEO ↑ | — | schema head |
| 2026-07-06 | fuzzy+groups | 三档宽松 fuzzy · yaml **+12** · L4 Rec **24→12** · S-04 页 **8/110** | Expertise ↑ | 主轨 7+ **98/110**（新定义） | [worklog](../../worklogs/2026-07-06/fuzzy-relaxed-and-groups-before-after.json) |
| 2026-07-06 | 语义修订 | Hero **源有结果**（S-03）· §3.2.1 三轨 · Trust 方法论 | Trust ↑ | 消除 cross 名不副实 | [迭代](./iterations/2026-07-06-跨源语义与质量向定义.md) |
| | | | | | |

**下一迭代待办（摘自基线评估 P0/P1）：**

- [x] P0：生成器 100% DB 驱动，清理手写 demo 页（T-10）
- [x] P0：`recommend_reason` 合并 A-10 实测句（E-05 · 有 Rec 页 96/96）
- [x] P1：补 `groups.yaml` BB 首批 4 组（X-07 · XEBEC/FQM/IMMERSE/ASAP）
- [x] P1：补 `groups.yaml` 全库高频 L4 组（MeGusta/AFG/DL 等 · +9 组）
- [x] P1：S-04 fuzzy 跨源 + X-05 Sources Cross badge（不重拉）
- [x] P0：A-07 timeout 槽隐藏测速面板
- [x] P2：BreadcrumbList JSON-LD（T-SEO-08）
- [x] P1：有 Recommended 页测速 summary 100%（E-02 · **107/107**）
- [x] P1：**无 Rec 页 noindex 门禁**（`backfill_no_rec_noindex` · 10 页）
- [x] P1：跨源 per-indexer + 全站 `pipeline refetch-all`
- [x] P2：`recompute_cross_source_fuzzy.py --all-published --rescore-after`（严格档无效 → **宽松三档** 已落地）
- [x] P1：groups.yaml 补档 **+12** · L4 Rec **24→12**
- [ ] P1：release_parser 空组名 / 华语无 `-Group` 标题（剩余 **12** L4 Rec）→ **抬主轨 7+**
- [ ] P2：S-04 验证页占比 ↑（**8/110**）— 辅轨，非质量向主门槛
- [x] P2：Hero / Trust **跨源文案语义**与 TRACKER 质量向拆分（2026-07-06）

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
| v1.8 | 2026-07-05 | T-SEO-04/05：OG + favicon + WebSite Schema · Trust 五页 favicon |
| v1.9 | 2026-07-05 | S-04 fuzzy · X-05 Cross badge · A-07 timeout 隐藏 · yaml +9 · BreadcrumbList |
| v2.0 | 2026-07-05 | 跨源 per-indexer · 无 Rec noindex · refetch-all · VPS 172.236.156.193 · 迭代文档 |
| v2.1 | 2026-07-06 | 宽松 fuzzy 三档 · groups +12 · cross≥2 8/110 |
| v2.2 | 2026-07-06 | §3.2.1 质量向三轨 · Hero S-03 文案 · Trust 方法论 · 迭代文档 |
