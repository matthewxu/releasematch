# SEO 策略与 TODO — 2026-08-08

> **复盘日期：** 2026-08-08  
> **最近修订：** 2026-08-08 v1.1 — Title 保持 `Sources`；snippet 优化改 Description  
> **基于：** [01-GSC索引复盘.md](./01-GSC索引复盘.md) · [02-GSC效果复盘.md](./02-GSC效果复盘.md)  
> **关联方案：** [可覆盖关键词落地方案.md](../../可覆盖关键词落地方案.md) · [01-分支定位与流量获取.md](../../../01-分支定位与流量获取.md) §8.1  
> **阶段目标：** C2 → C3 过渡；从「验证收录」转向「扩大展示 + 稳定 CTR」

---

## 〇、策略总纲

### 当前位置（2026-08-08）

```
索引 ✅ → 展示 🟡 → CTR ✅ → 流量规模 🔴
```

| 层级 | 状态 | 下一步 |
|------|------|--------|
| 能被找到（索引） | 58 页，健康 | 维持门禁；~~www / catalog noindex~~ ✅ |
| 能被看到（展示） | 201/3天，刚起步 | 推 Top 10 + 复制新片页 |
| 能被点击（CTR） | 12.4%，优秀 | 优化零点击高展示页 **Description** |
| 能规模化（流量） | 25 点击，单页依赖 | 3～5 个「Minions 型」页面 |

### 核心策略（2026-08 ～ 2026-09）

1. **守**：不放开 Hub/薄页 index；维持 D2/D3 门禁；**Title 主轴保持 `Sources`**  
2. **攻**：复制 Minions 成功模式到新片（2026 catalog）  
3. **修**：~~www 301~~ ✅ · ~~catalog 分页 noindex~~ ✅ · 美国市场 **Description** snippet  
4. **量**：C3 条件满足后 sitemap 从 30 扩到 50～60  

### Title / Description 分工（已定，勿回退）

| 槽位 | 策略 | 意图词 | 品牌信号 |
|------|------|--------|----------|
| **Title** | `{片名} ({年}) Sources — {source/res} \| ReleaseMatch` | ❌ 不放 download/torrent | ✅ `Sources` + ReleaseMatch |
| **Description** | `… torrent sources: Recommended … ({group}) and N matched downloads` | ✅ torrent / download / sources | Recommended · edition · group |
| **H1** | `{片名} — Release-Matched Sources` | — | Release-Matched |

**决策依据（2026-08-08）：**

- 2026-07-20 迭代已明确：**Title 用 `Sources` 对齐品牌，torrent/download 仅进 Description**  
- GSC 验证：Minions 页 Title 为 `Sources — 1080p`，仍获 72% 点击、14% CTR；query 匹配由 Description 承担  
- Title 改 `Torrent Download` 会强化「泛 download 聚合站」分类，与 Release Guide 定位、Pirate Demotion 防护、IG 差异化冲突  
- L1 泛词 `torrent download` 在 01 文档标为 **不攻**；L3 长尾 `{片名} torrent` 已在 Description 覆盖  

---

## 一、已验证的有效公式

### 1.1 赢家页模式（Minions & Monsters）

| 要素 | 做法 |
|------|------|
| **内容类型** | 2026 新片（竞争低、搜索新鲜） |
| **Title** | `{片名} ({年份}) Sources — {画质} \| ReleaseMatch`（**不改 Download**） |
| **Description** | 含 **torrent sources**、Recommended **组名**、**edition 数量**、**年份** |
| **排名** | ~12 即可获 14% CTR |
| **查询词** | `{片名} torrent` / `{片名} download torrent`（由 Description 匹配） |

### 1.2 待复制目标页（2026 新片 · 已有 indexable）

| 优先级 | 页面 slug | 理由 |
|--------|-----------|------|
| P0 | `goat` | catalog 有展示（4），排名 8.8，0 点击 |
| P0 | `el-mal` | 2026 新片 |
| P0 | `enola-holmes-3` | 查询已有 enola 相关词 |
| P1 | `avatar-fire-and-ash` | 已有 3 点击，排名 39 待提升 |
| P1 | `zootopia-2` | 2026 新片 |
| P1 | `chum` | 排名 4.0，0 点击 |

### 1.3 Title 微调范围（仅 L4，不加 Download）

Title 主轴 **不变**；仅可在 `{source/res}` 槽位加强 L4 差异：

```
当前：Minions & Monsters (2026) Sources — 1080p | ReleaseMatch
微调：Minions & Monsters (2026) Sources — 1080p BluRay | ReleaseMatch
      ↑ 补 source/edition（WEB-DL / BluRay / REMUX），不引入 Download / Torrent
```

**允许：** `{resolution}` → `{resolution} {source}`（如 `1080p` → `1080p BluRay`）  
**禁止：** Title 出现 `Torrent`、`Download`、`Free`、`Magnet` 等泛 download 词  

### 1.4 Description 优化模板（Snippet A/B 主战场）

针对「有展示零点击」页面，**只改 Description**（及必要时 Title 的 `{source}` 槽位）：

```
当前 desc 示例：
Minions & Monsters (2026) torrent sources: Recommended 1080p BluRay (FLAME) and 4 edition comparisons (WEB-DL / BluRay / REMUX).

优化方向（覆盖 rank 4.4 零点击查询「… 2026 torrent」）：
Minions & Monsters (2026) torrent sources: Recommended 1080p BluRay (FLAME) — 4 edition downloads compared (WEB-DL / BluRay / REMUX).
```

| 优化 lever | 用途 | 示例 |
|------------|------|------|
| 年份重复 | 匹配 `{片名} 2026 torrent` | desc 前部含 `(2026)` |
| 组名 | 匹配 release 名查询 | `(FLAME)` |
| edition 数 | 差异化 vs 纯 magnet 站 | `4 edition comparisons` |
| matched downloads | 匹配 download 意图 | `N matched downloads` |
| source 三元 | 电影 L4 | `WEB-DL / BluRay / REMUX` |

**A/B 范围：** 单页 Description；**不做**全站 Title 批量试验。

---

## 二、TODO 清单

### P0 — 本周（2026-08-08 ～ 08-15）

| ID | 任务 | 负责 | 验收标准 | 状态 |
|----|------|------|----------|------|
| **T-01** | Cloudflare 配置 **301**：`www.releasematch.com` → `releasematch.com` | 运维 | `curl -I www` 返回 301；GSC 备用页不再新增 | ✅ 2026-08-08 Page Rule |
| **T-02** | **catalog 分页 noindex**：`/catalog/page/2/` 及以后 | 开发 | view-source 含 `noindex,follow`；canonical 指首页 | ✅ 2026-08-08 |
| **T-03** | GSC **URL Inspection** 查 2 页「已抓取未编入」原因 | 运营 | 记录原因到下次复盘 | ✅ 2026-08-08 根因 **www 重复**；T-01 301 已修复 |
| **T-04** | 优化 `/minions-monsters/` **snippet 推 Top 10** | 开发/运营 | Title `1080p BluRay`；desc edition 短语 + FLAME | ✅ 2026-08-08 代码+dist |
| **T-05** | 复制 **Description 公式**到 GOAT、El mal、Enola Holmes 3 | 开发 | 同上（全站电影模板） | ✅ 2026-08-08 已 generate |

### P1 — 本月（2026-08）

| ID | 任务 | 负责 | 验收标准 | 状态 |
|----|------|------|----------|------|
| **T-06** | 优化 **avatar-aang**（20 展示 0 点击）**Description** | 开发 | 覆盖 `legend of aang webrip`；Title 仍 `Sources` | ⏸ |
| **T-07** | GSC 同时验证 **非 www 属性** 或只保留主域 | 运营 | 两属性数据可对比 | ⏸ |
| **T-08** | 更新 [TRACKER](../TRACKER-E-E-A-T-InfoGain.md) §度量：GSC 已提交、收录率 44% | 运营 | TRACKER 基线表已更新 | ⏸ |
| **T-09** | 分析美国市场 SERP：对比 Top 3 竞品 **snippet**（非 Title 抄 Download） | 运营 | 结论：竞品 desc 里哪些 L4 词可借鉴 | ⏸ |
| **T-10** | 运行 `seo_c2_checklist.py` 确认 dist 与线上一致 | 开发 | 16 pass / 0 fail | ⏸ |

### P2 — 下月（2026-09）

| ID | 任务 | 负责 | 验收标准 | 状态 |
|----|------|------|----------|------|
| **T-11** | sitemap `max_content_urls` **30 → 50**（若收录率仍 >40%） | 开发 | sitemap 50+ 内容 URL | ⏸ |
| **T-12** | **2026-09-08 月度复盘** | 运营 | 新建 `reviews/2026-09-08/` | ⏸ |
| **T-13** | 评估 Hub 页改 index（D2 解除） | 决策 | 需收录率 >50% + IG 7+ | ⏸ |
| **T-14** | Rich Results Test 抽查 5 页 TVEpisode Schema | 开发 | 无 error | ⏸ |

---

## 三、技术 TODO 实现要点

### T-02：catalog 分页 noindex（已落地 2026-08-08）

**实现：**

| 文件 | 变更 |
|------|------|
| `portal/generator/render.py` | `catalog_noindex = page > 1`；canonical 指向 `{origin}/` |
| `portal/generator/templates/home.html` | `meta_robots`：`noindex,follow` |
| `scripts/seo_c2_checklist.py` | `6.2.catalog_pagination` 门禁 |

**规则：**

- 第 1 页（`/`）：`index,follow`，canonical 为首页
- 第 2 页起（`/catalog/page/N/`）：`noindex,follow`，canonical → `/`

**发版：** `python -m workflow.run generate all` 或 `write_home_page()` 重烘首页分页后 `wrangler deploy`。

### T-01：Cloudflare 301

**建议规则：**

```
if (http.host eq "www.releasematch.com") {
  redirect to "https://releasematch.com" + http.request.uri.path status 301
}
```

**注意：** 与 `RM_SITE_ORIGIN`、canonical、sitemap 保持一致（均为非 www）。

**已落地（2026-08-08）：** Page Rule `www.releasematch.com/*` → `301 https://releasematch.com/$1`；curl 验收通过。详见 [infra-www-to-apex-301.md](../../infra-www-to-apex-301.md)。

### T-03：「已抓取未编入」根因（www 重复）

| 项 | 结论 |
|----|------|
| **GSC 表现** | 未编入 30 中：备用页 2 + 已抓取未编入 2，均与 **www / 非 www 双 URL** 相关 |
| **根因** | Google 在 www 属性下抓取 www URL；canonical 指向 apex → 标记为备用页或未编入 canonical 目标 |
| **修复** | T-01 全站 **301**（www → apex）；无需单页内容改动 |
| **复验** | 1～2 周后 GSC 索引报告「备用页 / 已抓取未编入」应下降或归零 |

### T-04 / T-05：snippet 优化（Description + Title L4，已落地 2026-08-08）

**目标模块：**

- `portal/generator/i18n.py` → `build_movie_title_quality` · `build_movie_meta_description` · `_movie_edition_phrase`
- `portal/generator/templates/movie.html` → `seo_title_quality`

**规则：**

| 字段 | 改法 | 示例（Minions） |
|------|------|-----------------|
| Title | `Sources — {res} {source}`，不加 Download | `Sources — 1080p BluRay` |
| meta description | `{year} torrent sources: Recommended … (GROUP) — N edition downloads compared` | 含 FLAME · edition 数 |
| og:title / og:description | 与 title / desc 同步 | — |

**T-05 已 regenerate：** `minions-monsters` · `goat` · `el-mal` · `enola-holmes-3`

**发版：** `wrangler deploy` 后 2 周对照 GSC 排名/CTR（T-04 验收指标仍待观察）

**Minions 零点击查询对照：**

| 查询 | 排名 | desc 应覆盖 |
|------|------|-------------|
| minions and monsters 2026 torrent | 4.4 | `(2026)` + `torrent sources` |
| minions monsters torrent | 9.5 | 片名变体 + `torrent sources` |

---

## 四、度量目标（2026-09-08 复盘对照）

| 指标 | 2026-08-08 基线 | 2026-09-08 目标 | 备注 |
|------|-----------------|-----------------|------|
| 已索引页 | 58 | ≥70 | 随 sitemap 扩量 |
| indexable 收录率 | ~44% | ≥50% | C3 持续观察 |
| 月展示 | ~670（3天×10粗估） | ≥2,000 | 效果报告 28 天 |
| 月点击 | ~83（粗估） | ≥200 | — |
| CTR | 12.4% | ≥8% | 扩量后可能回落 |
| 平均排名 | 14.6 | ≤12 | 推 Top 10 |
| 单页点击占比 | 72%（Minions） | ≤50% | 流量多样化 |
| 美国 CTR | 2.4% | ≥5% | Description snippet 优化 |

---

## 五、不做清单（避免过度优化）

| 不做 | 原因 |
|------|------|
| 放开 Hub index | D2 沙盒期策略；等 C3 指标 |
| sitemap 一次提交全部 117 页 | D3 分批策略；防低质收录 |
| 为冲收录去掉 noindex 门禁 | 薄页/no-Rec 页会拉低整站质量 |
| 经典老片（Dark Knight 等）重投入 | 排名 30+，ROI 低；优先 2026 新片 |
| **Title 改 `Torrent Download` / 全站加 Download** | 与 `Sources` 品牌、Release Guide 定位冲突；强化 Pirate 聚合站分类；L1 泛词不攻 |
| Title 加 `Free` / `Magnet` / 全大写 DOWNLOAD | 同上；降低 E-E-A-T 观感 |
| 仅改 Title 不改 Description 做 snippet A/B | GSC 已证 Description 承担 torrent  query 匹配 |

---

## 六、决策门控（何时进入下一阶段）

### C3 正式观察期进入条件

- [x] GSC 已提交且有效数据 ≥7 天  
- [x] indexable 收录率 >25%（当前 ~44%）  
- [x] 「已抓取未编入」<5%（复盘时 2 页；**T-03 根因 www 重复，T-01 301 已修复**；下月复盘复验）  
- [ ] 月点击 ≥100（当前未达标）  
- [ ] 至少 **2 个** 内容页各贡献 >10% 点击（当前仅 1 个）

### sitemap 扩量门控

- [ ] 收录率 >40% 维持 2 周  
- [ ] 平均排名 ≤15  
- [x] catalog 分页 noindex 已部署（2026-08-08 T-02）

### Title 策略变更门控（未来若评估 Hub index 等）

- [ ] 任何 Title 主轴变更须先更新 [可覆盖关键词落地方案.md](../../可覆盖关键词落地方案.md) 并过 TRACKER 评审  
- [ ] **禁止** 以 GSC 短期 CTR 为由单独引入 `Download` 进 Title  

---

## 七、复盘节奏

| 频率 | 动作 |
|------|------|
| **每周** | GSC 效果快速扫一眼；Minions 排名变化 |
| **每月 8 日** | 完整复盘 → 新建 `reviews/YYYY-MM-DD/` |
| **重大变更后** | 7 天内加做一次 mini 复盘 |

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-08-08 | 首次策略与 TODO |
| v1.4 | 2026-08-08 | T-04/T-05 电影 Title L4 + desc 公式；regenerate 4 页 |
