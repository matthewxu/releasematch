# E-E-A-T · Info Gain · SEO 跟进看板

> **Living Document** — 随 SEO 迭代持续更新  
> **创建：** 2026-07-04 · **最近更新：** 2026-07-05  
> **功能性邮箱：** `ReleaseMatch@hotmail.com`（Contact · DMCA · Privacy）  
> **基线评估：** [2026-07-04 基线评估](./assessments/2026-07-04-E-E-A-T与Info-Gain基线评估.md)  
> **IG 字段权威：** [IG信息登记册.md](../IG信息登记册.md)

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
| **页面 IG 估分（真实页）** | **5~7** | **≥7** | 🔴 |
| **测速 bake 覆盖率** | ~81% 槽有数据 | **100%** indexable 页 | 🟡 |
| **E-E-A-T 综合** | Trust B+ · Exp B+ · Exp A- · Auth C | Trust A- · Exp A | 🟡 |

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

| # | 信号 | 要求 | 状态 | IG-ID | 备注 |
|---|------|------|------|-------|------|
| E-01 | VPS/libtorrent 测速 | cron 每 6h | ✅ | S-06 | 114 槽 ~81% ok |
| E-02 | 测速 bake 进 HTML | 静态可爬 | 🔶 | S-06/S-07 | 未 100% 覆盖 |
| E-03 | grab_index Hero | Recommended 卡片 | 🔶 | S-07 | 模板有，数据不全 |
| E-04 | speed_endorsement 文案 | 实测背书句 | 🔶 | S-07 | A-10 模板待建 |
| E-05 | recommend_reason 含实测事实 | UTC + peers 对比 | ❌ | S-02 | 当前公式拼接 |
| E-06 | tested_at 页面展示 | 更新时间 | 🔶 | A-03 | speed bar 部分有 |
| E-07 | 索引 vs 实测 peers 对比 | 独家事实句 | ❌ | A-10 | |

### 2.3 Expertise（专业）

| # | 信号 | 要求 | 状态 | IG-ID | 备注 |
|---|------|------|------|-------|------|
| X-01 | groups.yaml 分档 | L0~L4 | ✅ | S-05 | 98 组 |
| X-02 | Group badge Hero | Recommended | ✅ | S-05 | |
| X-03 | Group badge Sources 表 | 逐条 | ❌ | S-05 | T3 待做 |
| X-04 | 跨源 N/M Hero badge | 页面级 | ✅ | S-03 | 数据多为 1/3 |
| X-05 | 跨源 confidence Sources | 单条 badge | ❌ | S-04 | |
| X-06 | release 解析 | source/codec/res | ✅ | A-05 | |
| X-07 | BB 高频组入库 | XEBEC/FQM 等 | ❌ | S-05 | yaml 缺口 |
| X-08 | scene_compliant | 入 reason | ❌ | — | 规划 P2 |
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
| S-02 | recommend_reason | ✅ | ✅ | ⚠️ 模板化 | P0：A-10 实测句 |
| S-03 | 跨源 N/M | ✅ | ✅ | ⚠️ 多数 1/3 | 修 Nyaa/EZTV |
| S-04 | hash confidence | ✅ | 🔶 | ❌ 全 0.333 | P3：fuzzy 对齐 |
| S-05 | Group tier | ✅ | 🔶 Hero | ⚠️ L4 为主 | P1：补 yaml |
| S-06 | 实测速度 | ✅ | 🔶 | 🔶 81% | P1：100% bake |
| S-07 | 实测背书 | 🔶 | 🔶 | 🔶 | P0：speed_endorsement |
| S-08 | 多地域测速 | 📋 | 📋 | — | P2+ |

### 3.2 页面 IG 估分目标

| 页面类型 | 当前估分 | C3 目标 | 关键提升项 |
|----------|----------|---------|-----------|
| 单集 L3（有 recommended + 测速） | 7~8 | 8~9 | S-06/S-07 bake + A-10 |
| 单集 L3（有 recommended 无测速） | 5~7 | 7~8 | 测速 cron 覆盖 |
| 单集 L3（无 recommended） | 2~4 | noindex | 保持门禁 |
| 电影页 | 5~7 | 7~8 | 同单集 |
| Trust 页 | — | Trust A- | Contact ✅ · lang=en ✅ |

### 3.3 IG 缺口 → 开发映射

| 优先级 | IG-ID | 缺口 | 负责模块 | 状态 |
|--------|-------|------|----------|------|
| P0 | A-01,A-03,S-07 | speed bar + 生成器渲染 | T2+T3 | 🔶 |
| P0 | A-07 | timeout 条目隐藏 | T2+T3 | ❌ |
| P0 | A-10 | 索引 vs 实测对比文案 | T3 | ❌ |
| P1 | S-05 | 补 groups.yaml | T1 | ❌ |
| P1 | S-05 | Sources 表 tier badge | T3 | ❌ |
| P1 | S-06 | 批量 slot cron 增量 TTL | T2 | ✅ cron |
| P1 | S-04 | title/fuzzy 跨源对齐 | T1 | ❌ |
| P2 | S-05 | scene_compliant 入 reason | T1 | ❌ |
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
| Information Gain | 🟡 5~7 | 本看板 §三 |
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
| 单页 IG debug 均分 | 5~7 | ≥7 | `RM_SHOW_IG_DEBUG=1` |

---

## 五、迭代日志

> 每次 SEO/IG 相关合并或里程碑完成后追加一行。详细过程可另建 `iterations/YYYY-MM-DD-*.md`。

| 日期 | 版本/Commit | 变更摘要 | E-E-A-T 影响 | IG 影响 | 验收 |
|------|-------------|----------|-------------|---------|------|
| 2026-07-04 | — | 初建 `docs/seo/` + 基线评估 + 本看板 | 建立跟进体系 | 基线 5~7 分建档 | 文档 review |
| 2026-07-04 | C2 SEO | sitemap ≤35 · 410 · Hub noindex · lang=en | Trust/技术 SEO ↑ | — | seo_c2_checklist |
| 2026-07-04 | cron | VPS 测速 `--all-published` 每 6h | Experience ↑ | S-06 数据 ↑ | 92/114 ok |
| 2026-07-05 | Trust | Contact 页 + 五页 `lang=en` + `ReleaseMatch@hotmail.com` | Trust ↑ | — | `/trust/contact/` |
| 2026-07-05 | T-10 | 删除 `portal/` 手写 demo（BB S04E6 等） | Trust ↑ | 避免虚假 cross/tier | generate page 验收 |
| | | | | | |

**下一迭代待办（摘自基线评估 P0/P1）：**

- [x] P0：生成器 100% DB 驱动，清理手写 demo 页（T-10）
- [ ] P0：`speed_endorsement` + A-10 索引/实测对比模板（E-04/E-07）
- [ ] P1：补 `groups.yaml` BB 高频组（X-07）
- [ ] P1：全 indexable 页测速 + grab_index bake（E-02/E-03）
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
