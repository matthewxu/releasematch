# SEO 迭代文档目录

> **创建日期：** 2026-07-04  
> **用途：** 集中存放 ReleaseMatch **SEO 专项**的评估、跟进看板与历次迭代记录  
> **与兄弟文档关系：** 战略见 [01-分支定位与流量获取.md](../01-分支定位与流量获取.md)；IG 字段登记见 [IG信息登记册.md](../IG信息登记册.md)；技术 SEO 任务见 [worklogs/页面SEO分析与优化方向.md](../../worklogs/2026-07-03/页面SEO分析与优化方向.md)；日常运维见 [12-日常运营执行手册.md](../12-日常运营执行手册.md)

---

## 一、本目录定位

| 维度 | `docs/seo/`（本目录） | `docs/01`、`IG信息登记册` | `worklogs/` |
|------|----------------------|---------------------------|-------------|
| **内容** | E-E-A-T / Info Gain **评估与跟进** | 战略方案、IG 字段规格 | 当日开发验收 |
| **更新频率** | 阶段切换、重大 SEO 变更、月度复盘 | 方案变更时 | 每日 |
| **读者** | 运营 / SEO 决策 | 架构与产品 | 开发冲刺 |

**原则：**

1. **评估文档**（`assessments/`）— 某时点的快照，**只增不改**（修订发新版文件）。
2. **跟进看板**（`TRACKER-*.md`）— **Living doc**，随迭代更新当前状态。
3. **迭代记录**（`iterations/`）— 每次 SEO 专项改动的摘要（做了什么、测了什么、结论）。

---

## 二、文档清单

### 2.1 评估（Assessments）

| 文档 | 日期 | 说明 |
|------|------|------|
| [2026-07-04-E-E-A-T与Info-Gain基线评估.md](./assessments/2026-07-04-E-E-A-T与Info-Gain基线评估.md) | 2026-07-04 | **首次基线**：四维 E-E-A-T + IG 能力栈 + 风险矩阵 + 改进优先级 |

### 2.2 跟进看板（Trackers）

| 文档 | 说明 |
|------|------|
| [TRACKER-E-E-A-T-InfoGain.md](./TRACKER-E-E-A-T-InfoGain.md) | **主看板**：E-E-A-T 清单、IG 字段落地率、SEO 元素矩阵、迭代日志 |

### 2.3 迭代记录（Iterations）

| 文档 | 日期 | 说明 |
|------|------|------|
| [2026-07-05-跨源扩展与全站重拉.md](./iterations/2026-07-05-跨源扩展与全站重拉.md) | 2026-07-05 | per-indexer 跨源 · 无 Rec noindex · refetch-all · VPS 迁移 |

---

## 三、SEO 元素覆盖范围

本目录跟进以下 SEO 维度（与 Google 2026 信号及项目 C 轨对齐）：

| 类别 | 元素 | 主文档 |
|------|------|--------|
| **内容质量** | Information Gain、Helpful Content、薄页门禁 | TRACKER · IG 登记册 |
| **E-E-A-T** | Experience / Expertise / Authority / Trust | TRACKER · assessments |
| **技术 SEO** | sitemap、robots、canonical、Schema、OG、favicon | worklog SEO 审计 · `seo_c2_checklist.py`（**2026-07-05 本地 13 pass**） |
| **站点信任** | Trust 五页（含 Contact）、DMCA、410、nofollow | TRACKER §Trust |
| **规模与政策** | Scaled Content、Pirate Demotion、sitemap 批次 | 01 §三 · 12 手册 |
| **度量** | GSC 收录率、排名、IG 估分 | TRACKER §度量（C2 后启用） |

---

## 四、新建文档规范

### 4.1 评估文档命名

```
assessments/YYYY-MM-DD-<主题>.md
```

示例：`assessments/2026-08-01-C3收录率复盘评估.md`

### 4.2 迭代记录命名

```
iterations/YYYY-MM-DD-<简短主题>.md
```

必填段落：背景 · 变更 · E-E-A-T 影响 · IG 影响 · 验收 · 下一步

### 4.3 看板更新

- 每次合并影响 SEO/IG 的 PR 或完成 C 轨里程碑后，更新 `TRACKER-E-E-A-T-InfoGain.md` 的 **§一基线** 与 **§四迭代日志**。
- 重大阶段切换（如 C2→C3）另起一篇 `assessments/` 评估，看板只保留最新指针。

---

## 五、关联命令与工具

| 工具 | 路径 | 用途 |
|------|------|------|
| SEO C2 门禁 | `scripts/seo_c2_checklist.py` | 技术 SEO 发版前检查 |
| IG Debug 面板 | `RM_SHOW_IG_DEBUG=1` + 生成器 | 单页 IG 字段对照登记册 |
| 全站 force 重拉 | `python -m workflow.run pipeline refetch-all` | 更新跨源分母与 magnet |
| fuzzy 跨源重算 | `scripts/recompute_cross_source_fuzzy.py --all-published` | 不重拉，提升 cross 分子 |
| VPS Key 同步 | `scripts/sync_jackett_vps_key.sh` | 远端 Jackett API Key → accounts.local.json |
| 页面 IG 估分 | `portal/generator/ig_debug.py` | 模板调试 |

---

## 六、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-04 | 初建目录；基线评估 + E-E-A-T/IG 主看板 |
| v1.1 | 2026-07-05 | 迭代记录 · refetch-all / fuzzy 工具索引 |
