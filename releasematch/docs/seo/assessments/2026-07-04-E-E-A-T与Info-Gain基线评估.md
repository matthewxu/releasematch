# E-E-A-T 与 Info Gain 基线评估

> **版本：** v1.0  
> **评估日期：** 2026-07-04  
> **评估阶段：** C2 SEO 冷启动（GSC 提交前 · CF Pages 暂缓）  
> **数据基线：** 118 published 页 · sitemap ≤35 URL · 测速 cron 每 6h  
> **关联：** [IG信息登记册.md](../../IG信息登记册.md) · [01-分支定位与流量获取.md](../../01-分支定位与流量获取.md) §十一 · [TRACKER](../TRACKER-E-E-A-T-InfoGain.md)

---

## 〇、执行摘要

ReleaseMatch 在 **策略与后端** 上对 Google 2026 E-E-A-T / Information Gain 要求理解深度领先同类下载站；差异化路径（Recommended + 跨源 + Group + 测速）清晰且已有工程落地。

**当前可索引页面的真实 Info Gain 约 5~7 分（A 级）**，距登记册目标 **8~9 分（S 级）** 仍有差距。E-E-A-T 最大短板为 **Authority（C）** 与 **Experience 的页面表达**；**Trust 基础良好（B）** 但 Contact 与语言一致性待补。

**阶段建议：** C2 维持 ≤30 页 sitemap；在单页 IG 稳定到 7~8 分之前，不宜 C4 扩至 100+ indexable 页。

---

## 一、总览评分

| 维度 | 战略设计 | 工程实现 | 页面呈现 | 综合 |
|------|---------|---------|---------|------|
| **Experience（经验）** | ★★★★☆ | ★★★☆☆ | ★★☆☆☆ | **B+** |
| **Expertise（专业）** | ★★★★★ | ★★★★☆ | ★★★☆☆ | **A-** |
| **Authoritativeness（权威）** | ★★★☆☆ | ★☆☆☆☆ | ★☆☆☆☆ | **C** |
| **Trustworthiness（信任）** | ★★★★☆ | ★★★☆☆ | ★★★☆☆ | **B** |
| **Info Gain（信息增益）** | ★★★★★ | ★★★☆☆ | ★★★☆☆ | **B / 5~7 分** |

---

## 二、E-E-A-T 分项分析

### 2.1 Experience（经验）— B+

**已具备：**

- libtorrent 实测 peer 可达性 + Phase 2 片段测速（BB S04E06：索引 50 seeders → 实测 29~46 peers、22~50 KB/s）
- `grab_index` 综合评分（可达性 + 速度 + peers）
- 每 6h 全 published 测速 cron（114 槽 ~81% ok）
- `/trust/how-matching-works/` 方法论说明页

**缺口：**

- 页面「一手经验」叙事不足：`recommend_reason` 多为规则拼接，缺少「我们于 UTC xxx 实测…」类可验证陈述
- 真实 DB 与演示页不一致：`portal/breaking-bad/s4e6/` 展示 NTb L0、3/3 源；登记册显示实际为 **XEBEC L4、1/3 源、confidence 全 0.333**
- 无作者/编辑署名、无 changelog、无「验证记录」时间线

**对 Google 的信号：** 后端有实测能力，但爬虫读到的 HTML 里「经验」证据不够稳定、不够可核查。

---

### 2.2 Expertise（专业）— A-

**强项：**

| 能力 | 状态 | E-E-A-T 贡献 |
|------|------|-------------|
| `groups.yaml` 98 组 L0~L4 分档 | ✅ | 体现 scene/release 领域知识 |
| 跨源 N/M + hash 级 confidence | ✅ 算法完整 | 方法论专业 |
| release 解析（source/codec/resolution） | ✅ | 编码规格理解 |
| 文档 §5.4 对版分析类型矩阵 | ✅ | 战略深度 |
| `scorer.py` 可下载性优先评分 | ✅ | 用户导向的专业判断 |

**弱项：**

- 真实数据 tier 分布偏 **L4**（BB 测试集推荐组多为 XEBEC/FQM/ASAP 等未入库组）
- `scene_compliant`、PTN/mediainfo 未接入 → 专业深度停留在「规则库 + 正则」
- 页面 Expertise 主要靠 badge + 一行 reason，缺少音轨同步、剪辑差异等高 IG 专业段落

---

### 2.3 Authoritativeness（权威）— C

**现状：**

- 独立域名 `releasematch.com`，与字幕站隔离 ✅
- **GSC 未提交、CF Pages 正式上线暂缓** → 零搜索可见度
- 无外链建设执行、无 Stremio 插件（T4 规划）、无社区引用
- 114~118 页规模对冷启动域仍偏大

**风险：** 下载垂直本身 YMYL-adjacent；新域无品牌认知，Authority 需 6~12 个月建立。

---

### 2.4 Trustworthiness（信任）— B

**已达标：**

| 信号 | 状态 |
|------|------|
| `/trust/about/` | ✅ 定位清晰，不托管视频 |
| `/trust/dmca/` | ✅ DMCA 政策 |
| `/trust/privacy/` | ✅ 隐私政策 |
| `/trust/how-matching-works/` | ✅ 方法论透明 |
| magnet `rel="nofollow"` | ✅ 全站 |
| 薄页门禁 `magnet ≥ 2` | ✅ `is_indexable()` |
| Hub `noindex,follow` | ✅ 权重集中到 L3 |
| `410.html` | ✅ DMCA 下架预留 |

**待补：**

- **Contact 功能性邮箱** — 战略文档要求 Day 1，Trust 四页中未见独立 Contact
- Trust 页仍为 `lang="zh-CN"`，内容页已切 `lang="en"` → 语言信号不一致
- 演示页含占位 magnet hash 若与生产混用会损害信任
- 盗版垂直固有 **Pirate Demotion** 风险（文档：-89% 流量）

---

## 三、Info Gain 分项分析

### 3.1 IG 能力栈 vs 真实产出

登记册 §九 组合估分：

| 组合 | 估分 | 项目当前位置 |
|------|------|-------------|
| 仅 magnet 列表 | 2~4 | 竞品基线 |
| + Recommended + 对版 | 5~7 | **← 多数真实页在此** |
| + 跨源 + Group | 7~8 | 算法有，**数据弱** |
| + Phase 1/2 测速 | 8~9 | 后端有，**页面 bake 不完整** |
| 多地域测速 | 9~10 | 📋 未建 |

### 3.2 S 级 IG 字段落地率

| IG-ID | 名称 | 后端 | 页面 | 真实数据质量 |
|-------|------|------|------|-------------|
| S-01 | Recommended Release | ✅ | ✅ | ✅ 有推荐 |
| S-02 | recommend_reason | ✅ | ✅ | ⚠️ 模板化，缺独特验证句 |
| S-03 | 跨源 N/M | ✅ | ✅ | ⚠️ 多数 **1/3** |
| S-04 | hash confidence | ✅ | 部分 | ❌ 真实数据 **全 0.333** |
| S-05 | Group tier | ✅ | Hero only | ⚠️ 推荐多为 **L4** |
| S-06 | 实测速度 | ✅ | 🔶 | 🔶 ~81% 槽有测速 |
| S-07 | 实测背书 | 🔶 | 🔶 | speed_endorsement 未全覆盖 |
| S-08 | 多地域 | 📋 | 📋 | — |

### 3.3 与 TOP10 竞品的 IG 对比

**典型 magnet 聚合页：** release 名 + quality + size + seeders + magnet

**ReleaseMatch 额外提供：**

| 增量类型 | 竞品是否有 | 本站是否有 | 真实差异化程度 |
|----------|-----------|-----------|---------------|
| magnet 列表 | ✅ | ✅ | **零 IG** |
| TMDB 侧栏 | 多数有 | ✅ | **B 级，零 IG** |
| Recommended + reason | 少数有 | ✅ | **中** — reason 多为 seeders/画质 |
| Group L0~L4 badge | 极少 | ✅ | **中~高** — L4 为主时价值低 |
| 跨源 2/3 badge | 无 | ✅ | **低~中** — 数据多为 1/3 |
| hash 级交叉验证 | 无 | 算法有 | **低** — 无真实 hash 重叠 |
| VPS 实测速度 | 几乎无 | ✅ | **高** — 最强 IG，未全站 bake |
| 音轨同步/剪辑差异 | 无 | 📋 | **未实现** |

**综合 IG 估分：** 真实生产页 **5~7**；理想演示页 **8~9**；较纯列表页约 **+3~4 分** 增量。

---

## 四、关键风险矩阵

| 风险 | 严重度 | 现状 | 建议 |
|------|--------|------|------|
| 模板化 114 页批量 index | 高 | sitemap 已限 ≤30 ✅ | 维持 D3 至 C3 收录率 >25% |
| recommend_reason 无独特事实 | 中 | 公式拼接 | 注入测速/peers 对比句（A-10） |
| 跨源 badge 名不副实 | 高 | 演示页与 DB 不一致 | 生成器必须读 DB，禁用手写 demo |
| Group tier L4 为主 | 中 | yaml 缺 BB 高频组 | 补 IMMERSE/XEBEC/FQM |
| Trust 页语言不一致 | 低 | zh vs en | Trust 同步 `lang="en"` |
| Pirate Demotion | 高 | 垂直固有 | 独立域 + DMCA + 无播放器 ✅ |

---

## 五、优势与短板

### 5.1 优势

1. **IG 登记册** — 系统化 IG 分级与字段追踪
2. **薄页门禁** — `magnet ≥ 2` + noindex，符合 Scaled Content 合规
3. **测速 pipeline** — 竞品几乎不做，最强可防御 IG 护城河
4. **跨源 + Group 双引擎** — 算法完整，文档可审计
5. **Trust 壳 + SEO 决策** — D1~D4 已拍板，C2 路径清晰

### 5.2 短板

1. **数据质量 < 算法能力** — 跨源 confidence 全 0.333；Group 多为 L4
2. **页面 IG 呈现不稳定** — 测速/grab_index/speed_endorsement 未 100% bake
3. **reason 文本缺乏「独家事实句」** — 缺索引 vs 实测 peers 硬数据
4. **Authority 为零** — 未上线、未 GSC、无外链
5. **演示与生产脱节** — 影响 Trust 评估

---

## 六、改进优先级（评估结论）

| 优先级 | 动作 | IG 提升 | E-E-A-T |
|--------|------|---------|---------|
| **P0** | 生成器 100% 读 DB，淘汰手写 demo 页 | 避免虚假 cross/tier | Trust ↑↑ |
| **P0** | `recommend_reason` + `speed_endorsement` 注入实测句（A-10） | +1~2 分 | Experience ↑↑ |
| **P1** | 补 `groups.yaml`（BB 高频组） | S-05 真实生效 | Expertise ↑ |
| **P1** | 全 published 测速 bake + grab_index Hero | S-06/S-07 全站 | Experience ↑↑ · **Hero 布局 2026-07-05 ✅** |
| **P1** | Sources 表加 group_tier + cross badge | 页内 IG 密度 ↑ | Expertise ↑ |
| **P2** | Trust 页英文化 + Contact 页 | — | Trust ↑ |
| **P2** | C2 首批 ~20 页 GSC → 观察收录率 | — | Authority 起步 |
| **P3** | title/fuzzy 跨源对齐 | S-04 真实 >0.333 | IG ↑↑ |
| **P3** | 音轨同步/剪辑差异（人工编辑层） | 最高 IG 段落 | Expertise ↑↑↑ |

---

## 七、专题：Release Match 是否「无需 E-E-A-T」

> 评估会话中的专项结论，纳入基线评估存档。

### 7.1 结论

**不是无需，而是权重分布不同。**

- 不在 YMYL 核心名单（医疗/金融），但仍在 Quality Rater 评估范围内
- **Trust 必做** — Pirate Demotion、DMCA、假播放器风险
- **Experience 必做（若声称推荐/实测）** — Recommended、测速是有经验声明
- **Expertise 建议有** — Group/对版支撑判断可信度
- **Authority 长期项** — 冷启动非 blocker

### 7.2 E-E-A-T 与 Info Gain 关系

| IG 能力 | 对应的 E-E-A-T |
|---------|----------------|
| VPS 实测速度 | Experience |
| Group L0~L4 + 对版 reason | Expertise |
| 跨源 N/M 验证 | Experience + Expertise |
| Trust 四页 + DMCA | Trust |
| Stremio/社区引用 | Authority |

**主战场是 Info Gain，Trust 是底线，Experience 是 IG 的可信载体** — 三者一体，不可二选一。

### 7.3 最低配 vs 差异化配

| 层级 | 内容 | 结果 |
|------|------|------|
| **最低配** | Trust 壳 + 薄页门禁 + 纯 listing | Trust 底线；IG ≈ 0 |
| **差异化配** | 上述 + Recommended + 实测 + 真实 bake | T + Experience + IG 同时成立 |

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-04 | 首次基线评估（C2 冷启动前） |
