# IG 信息登记册

> **日期：** 2026-07-01  
> **范围：** 测试 / pipeline 全流程可获取字段，按 Information Gain 分级登记  
> **分级标准：** [docs/01-分支定位与流量获取.md](../../docs/01-分支定位与流量获取.md) §5.1  
> **关联：** [speedtest-Phase1探测.md](./speedtest-Phase1探测.md)、[今日验收清单.md](./今日验收清单.md)

---

## 一、IG 分级说明

| 等级 | 分数 | 定义 | 页面策略 |
|------|------|------|----------|
| **S** | 8~10 | 竞品难以复制：Recommended + 实测 + 跨源 + Group 信誉 | 必须 index；Hero 区展示 |
| **A** | 5~7 | 有差异化：实测 peer、quality 解析、对版说明 | 正文 + 静态 HTML |
| **B** | 2~4 | 行业通用：seeders 列表、TMDB 卡、模板文案 | 可有，不构成 IG |
| **C** | 0~1 | 无增量或薄页：0 条 magnet、纯占位 | **禁止 index** |

**图例（实现状态）：** ✅ 已实现　🔶 部分/派生未入库　📋 规划　❌ 非本模块

---

## 二、按 IG 等级登记（总表）

### 2.1 S 级（8~10）— 核心差异化

| IG-ID | 信息名称 | 字段 / 产出 | 获取阶段 | 负责模块 | 存储 | 页面展示 | 状态 |
|-------|----------|-------------|----------|----------|------|----------|------|
| S-01 | **Recommended Release** | `is_recommended=1` + 完整 release 元数据 | 评分 | T1 `scorer.py` | `download_resources` | Hero 推荐块 | ✅ |
| S-02 | **推荐理由** | `recommend_reason` | 评分 | T1 scorer | `download_resources` | Recommended 下方文案 | ✅ |
| S-03 | **跨源验证 N/M** | `cross_source_page_count/total` | 拉取 | T1 `cross_source` | FetchResult / 页面 | Hero badge「2/3 源一致」 | ✅ |
| S-04 | **单条跨源置信度** | `cross_source_count`、`cross_source_confidence` | 拉取 | T1 cross_source | `download_resources` | Sources 表 badge | ✅ |
| S-05 | **Release Group 信誉** | `group_tier`（L0~L4） | 评分 | T1 `groups.yaml` | `download_resources` | 组名旁 tier 标 | ✅ |
| S-06 | **实测下载速度** | `avg_kbps`、`max_kbps` → `recommended_speed` | 测速 P2 | T2 speedtest | `speedtest_results` → `slot_speed_summary` | 「前次测速 4.2 MB/s」 | 📋 |
| S-07 | **Recommended 实测背书** | reachability + speed 绑定 `recommended_infohash` | 测速 P1+P2 | T2 聚合 | `slot_speed_summary` | 推荐块追加实测句 | 🔶 |
| S-08 | **多地域测速** | Region Speed Map | 测速 P3 | T2 多节点 | 待建 | 地域速度表 | 📋 |

### 2.2 A 级（5~7）— 有效差异化

| IG-ID | 信息名称 | 字段 / 产出 | 获取阶段 | 负责模块 | 存储 | 页面展示 | 状态 |
|-------|----------|-------------|----------|----------|------|----------|------|
| A-01 | **Peer 可达性等级** | `reachability`（高/中/低） | 测速 P1 派生 | T2 speedtest | `slot_speed_summary` | speed bar | 🔶 |
| A-02 | **实测 peer 数量** | `peers_total`、`peers_reachable` | 测速 P1 | T2 speedtest | `speedtest_results` | 「观测 29 peers」 | ✅ CLI |
| A-03 | **测速 freshness** | `tested_at` / `updated_at` | 测速 | T2 | `speedtest_results` | 「UTC 2026-07-01 更新」 | 🔶 |
| A-04 | **对版匹配说明** | scorer 规则命中说明 | 评分 | T1 scorer | `recommend_reason` 内 | 对版段落 | ✅ |
| A-05 | **Release 质量解析** | `resolution`、`codec`、`source` | 拉取+解析 | T0 parser | `download_resources` | Sources 表列 | ✅ |
| A-06 | **压制组名** | `release_group` | 拉取+解析 | T0 parser | `download_resources` | 标题 / 组 badge | ✅ |
| A-07 | **死链过滤标记** | `status=timeout/error` | 测速 P1 | T2 | `speedtest_results` | 隐藏或灰显不可达项 | 🔶 |
| A-08 | **匹配排序分** | `match_score` | 评分 | T1 scorer | `download_resources` | 内部排序（可不展示） | ✅ |
| A-09 | **首包延迟** | `latency_ms` | 测速 P2 | T2 | `speedtest_results` | 高级区 | 📋 |
| A-10 | **索引 vs 实测对比** | seeders（索引）vs peers_total（实测） | 拉取+测速 | T0+T2 | 派生文案 | 「索引 50 seeders，实测 29 peers」 | 🔶 |

### 2.3 B 级（2~4）— 通用信息（非 IG）

| IG-ID | 信息名称 | 字段 | 获取阶段 | 负责模块 | 说明 |
|-------|----------|------|----------|----------|------|
| B-01 | magnet 列表 | `items[]` | 拉取 | T0 fetch | 竞品均有 |
| B-02 | 索引 seeders/peers | `seeders`、`peers` | 拉取 | indexer API | **非实测**，IG 低 |
| B-03 | 文件大小 | `size_bytes` | 拉取 | indexer | 通用 |
| B-04 | magnet 链接 | `magnet_uri` | 拉取 | client | 通用 |
| B-05 | 来源 indexer | `indexer` | 拉取 | fetch | 通用 |
| B-06 | TMDB 元数据 | title、imdb、tvdb | 元数据 | `external_ids` | 侧栏 |
| B-07 | 缓存命中 | `cached` | 拉取 | cache_index | 运维用 |
| B-08 | 槽位 cache_key | `tv:1396:s04e06` | 拉取 | FetchRequest | 内部 |

### 2.4 C 级（0~1）— 禁止依赖为 IG

| IG-ID | 情况 | 门禁 |
|-------|------|------|
| C-01 | 0 条 magnet | 薄页，不 index |
| C-02 | 仅 B 级字段、无 Recommended | IG < 5，验证集不通过 |
| C-03 | 纯手写演示页 `portal/breaking-bad/` | 已废弃，以 DB+generator 为准 |

---

## 三、按测试流程登记（阶段 × 字段）

### 阶段 1：槽位拉取（`torrent_sources.run test` / pipeline fetch）

**输入：** `tmdb_id`、`season`、`episode`、`media_type`

| 字段 | 类型 | IG 等级 | 说明 |
|------|------|---------|------|
| `external_ids.imdb_id` | string | B | standalone / MySQL |
| `external_ids.tvdb_id` | int | B | 剧集 Jackett 搜索用 |
| `external_ids.title` | string | B | 槽位过滤、Nyaa 搜索 |
| `fetch.cached` | bool | — | 运维 |
| `fetch.count` | int | — | 薄页门禁 ≥2 |
| `fetch.cross_source_page_count` | int | **S** | Hero N/M 分子 |
| `fetch.cross_source_page_total` | int | **S** | Hero N/M 分母 |
| `items[].infohash` | string | B | 测速输入 |
| `items[].title_raw` | string | B | parser 输入 |
| `items[].release_group` | string | A | S-05 输入 |
| `items[].source` | string | A | A-05 |
| `items[].resolution` | string | A | A-05 |
| `items[].codec` | string | A | A-05 |
| `items[].size_bytes` | int | B | |
| `items[].seeders` | int | B | **索引报告，非实测** |
| `items[].peers` | int | B | 索引报告 |
| `items[].magnet_uri` | string | B | 测速 `--magnet-uri` 输入 |
| `items[].indexer` | string | B | 如 `jackett:thepiratebay` |
| `items[].cross_source_count` | int | **S** | S-04 |
| `items[].cross_source_confidence` | float | **S** | S-04 |

### 阶段 2：评分（`workflow.run run recommended` / pipeline scorer）

| 字段 | 类型 | IG 等级 | 说明 |
|------|------|---------|------|
| `is_recommended` | bool | **S** | S-01 |
| `match_score` | float | A | A-08 |
| `recommend_reason` | string | **S** | S-02 |
| `group_tier` | string | **S** | S-05（L0~L4） |
| `recommended.infohash` | string | — | 测速 S-07 目标 hash |

### 阶段 3：测速 Phase 1（`speedtest.run test`）

**输入：** `infohash`、`page_id`、`magnet_uri`、`timeout_sec`

| 字段 | 类型 | IG 等级 | 已实现 | 说明 |
|------|------|---------|--------|------|
| `infohash` | string | — | ✅ | 关联键 |
| `page_id` | string | — | ✅ | 槽位 FK |
| `peers_total` | int | **A** | ✅ | A-02；BB S04E06=29 |
| `peers_reachable` | int | A | ✅ | 已连接 peer |
| `elapsed_ms` | int | — | ✅ | 运维/成本 |
| `status` | enum | A | ✅ | ok/timeout → A-07 |
| `mode` | enum | — | ✅ | libtorrent/dry_run |
| `error` | string | — | ✅ | 诊断 |
| `reachability` | 高/中/低 | **A** | 🔶 | A-01，由 peers 派生 |
| `tested_at` | ISO8601 | A | 🔶 | A-03，待写库 |

**libtorrent 可见未登记（扩展候选）：**

| 字段 | IG 潜力 | 状态 |
|------|---------|------|
| tracker announce 状态 | B | 📋 |
| peer IP / client | B~A | 📋 需 GeoIP 才有 IG |
| metadata 下载状态 | — | 诊断 |

### 阶段 4：测速 Phase 2（规划）

| 字段 | 类型 | IG 等级 | 说明 |
|------|------|---------|------|
| `avg_kbps` | float | **S** | S-06 |
| `max_kbps` | float | **S** | S-06 |
| `latency_ms` | int | A | A-09 |
| `phase` | int | — | 固定 2 |

### 阶段 5：聚合 → 页面（T2 待建 + T3 生成器）

| 表 / 上下文 | 字段 | IG 等级 | 页面位置 |
|-------------|------|---------|----------|
| `slot_speed_summary` | `recommended_speed` | **S** | speed bar |
| `slot_speed_summary` | `reachability` | **A** | speed bar |
| `slot_speed_summary` | `updated_at` | A | 更新时间 |
| `slot_speed_summary` | `recommended_infohash` | — | 关联 |
| `download_resources` | 全表推荐 + sources | S/A | episode.html |
| 静态 HTML | 上述 bake 为文本 | S/A | Googlebot 可读 |

---

## 四、按页面区块登记（IG 落点）

| 页面区块 | 需要的 IG-ID | 最低 IG 等级 |
|----------|--------------|--------------|
| Hero Recommended | S-01, S-02, S-07 | S |
| Hero 跨源 badge | S-03 | S |
| Speed 摘要条 | A-01, A-03, S-06（P2） | A |
| All Sources 表 | A-05, A-06, S-04, B-01 | A + B |
| 侧栏 TMDB | B-06 | B |
| Trust / 方法论 | 文字说明 IG 来源 | A |

**薄页门禁：** `fetch.count >= 2` 且至少含 **1 条 S 级**（Recommended）才允许 index。

---

## 五、索引 seeders vs 实测 peer（对照登记）

| 维度 | 索引 seeders（B-02） | 实测 peers（A-02） |
|------|----------------------|---------------------|
| 来源 | Jackett/EZTV API | libtorrent DHT/tracker |
| IG | 2~4 | **5~7** |
| 典型偏差 | 偏高/过期 | 时点真实 |
| 示例 | seeders=50 | peers_total=29 |
| 页面用法 | Sources 表参考列 | speed 区 + IG 文案 |

---

## 六、IG 组合与页面分数估算

| 组合 | 含 IG-ID | 页面 IG 估分 |
|------|----------|--------------|
| 仅 magnet 列表 | B-01~B-05 | **2~4** |
| + Recommended + 对版 | S-01, S-02, A-04~A-06 | **5~7** |
| + 跨源 + Group | + S-03, S-04, S-05 | **7~8** |
| + Phase 1 测速 | + A-01, A-02, A-03, S-07 | **6~8** |
| + Phase 2 测速 | + S-06, A-09 | **8~9** |
| 全栈 + 多地域 | + S-08 | **9~10** |

---

## 七、实现缺口（登记 → 开发）

| 优先级 | IG-ID | 缺口 | 负责 |
|--------|-------|------|------|
| P0 | A-01, A-03, S-07 | 写 MySQL + 聚合 `slot_speed_summary` | T2 |
| P0 | A-07 | timeout 条目不展示 / 降权 | T2 + 生成器 |
| P1 | S-06, A-09 | Phase 2 片段测速 | T2 |
| P1 | A-10 | 索引 vs 实测对比文案模板 | T3 生成器 |
| P2 | S-08 | 多节点 Worker | T2+ |

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-01 | 初版：按 IG 等级 + 测试阶段 + 页面区块登记 |
