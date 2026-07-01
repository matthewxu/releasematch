# IG 信息登记册

> **日期：** 2026-07-01（v1.3）  
> **范围：** 测试 / pipeline 全流程可获取字段，按 Information Gain 分级登记  
> **分级标准：** [01-分支定位与流量获取.md](./01-分支定位与流量获取.md) §5.1  
> **关联：** [speedtest-Phase1探测.md](../worklogs/2026-07-01/speedtest-Phase1探测.md)、[今日验收清单.md](../worklogs/2026-07-01/今日验收清单.md)

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
| S-03 | **跨源验证 N/M** | `cross_source_page_count/total` | 拉取 | T1 `cross_source` | FetchResult / 页面 | Hero badge「2/3 源一致」 | ✅ [§五](./IG信息登记册.md#五跨源验证-s-03--s-04计算逻辑与测试结果) |
| S-04 | **单条跨源置信度** | `cross_source_count`、`cross_source_confidence` | 拉取 | T1 cross_source | `download_resources` | Sources 表 badge | ✅ [§五](./IG信息登记册.md#五跨源验证-s-03--s-04计算逻辑与测试结果) |
| S-05 | **Release Group 信誉** | `group_tier`（L0~L4） | 评分 | T1 `groups.yaml` | `download_resources` | 组名旁 tier 标 | ✅ [§六](./IG信息登记册.md#六release-group-信誉-s-05--a-06计算逻辑与实现进度) |
| S-06 | **实测下载速度** | `avg_kbps`、`max_kbps` → `recommended_speed` | 测速 P2 | T2 speedtest | `speedtest_results` → `slot_speed_summary` | 「前次测速 4.2 MB/s」 | 🔶 [§七](./IG信息登记册.md#七测速-s-06phase-2片段测速) |
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
| A-06 | **压制组名** | `release_group` | 拉取+解析 | T0 parser | `download_resources` | 标题 / 组 badge | ✅ [§六](./IG信息登记册.md#六release-group-信誉-s-05--a-06计算逻辑与实现进度) |
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

### 阶段 4：测速 Phase 2（S-06）

| 字段 | 类型 | IG 等级 | 已实现 | 说明 |
|------|------|---------|--------|------|
| `avg_kbps` | float | **S** | ✅ | S-06 |
| `max_kbps` | float | **S** | ✅ | S-06 |
| `latency_ms` | int | A | ✅ | A-09 |
| `bytes_downloaded` | int | — | ✅ | 运维 |
| `phase` | int | — | ✅ | 固定 2 |

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
| Hero Recommended | S-01, S-02, S-05, S-07 | S |
| Hero Group tier badge | S-05 | S |
| Hero 跨源 badge | S-03 | S |
| Speed 摘要条 | A-01, A-03, S-06（P2） | A |
| All Sources 表 | A-05, A-06, S-04, B-01 | A + B |
| 侧栏 TMDB | B-06 | B |
| Trust / 方法论 | 文字说明 IG 来源 | A |

**薄页门禁：** `fetch.count >= 2` 且至少含 **1 条 S 级**（Recommended）才允许 index。

---

## 五、跨源验证（S-03 / S-04）— 计算逻辑与测试结果

> **代码：** `workflow/torrent_sources/cross_source.py`  
> **调用链：** `fetch_service.fetch_slot` → `compute_page_cross_source`（页面 N/M）→ `merge_by_infohash`（单条 confidence）

### 5.1 两套指标的区别（必读）

| 指标 | IG-ID | 字段 | 回答的问题 |
|------|-------|------|------------|
| **页面 N/M** | S-03 | `cross_source_page_count` / `cross_source_page_total` | 本次拉取中，**有几个源族至少返回了 1 条 magnet** |
| **单条置信度** | S-04 | `cross_source_count` / `cross_source_confidence` | **同一个 infohash** 被几个源族同时索引到 |

二者相关但**不等价**：页面可以是 **2/3**，而所有单条 confidence 仍全是 **0.333**（见 §5.5 实测）。

### 5.2 源族（Family）归一化

`indexer` 先映射为源族，再参与统计（`normalize_source_family`）：

| indexer 示例 | 源族 |
|--------------|------|
| `eztv` | eztv |
| `yts` | yts |
| `nyaa` / `nyaa:…` | nyaa |
| `jackett:thepiratebay` / `jackett:nyaasi` | **jackett**（多个 Jackett indexer 仍算 **1 族**） |

**注意：** 同一 infohash 若同时出现在 `jackett:thepiratebay` 与 `jackett:nyaasi`，`cross_source_count` 仍为 **1**（同属 jackett 族，不重复计数）。

**剧集默认参与源族：** eztv、nyaa、jackett → 分母 **M = 3**  
**电影默认参与源族：** yts、jackett → 分母 **M = 2**

实际分母以 `fetch_service` 中 `source_enabled`（本次真正发起请求的源族）为准：

```python
# 剧集 _fetch_tv 初始
source_enabled = {"eztv": False, "nyaa": False, "jackett": bool(jackett_client)}
# 欧美剧：eztv=True；nyaa 按配置尝试；jackett 有 VPS 则为 True
```

### 5.3 页面级 N/M（S-03）

**函数：** `compute_page_cross_source(items, source_enabled, media_type)`

**公式：**

```
N = |{ 源族 f : source_enabled[f]=True 且 items 中至少 1 条来自 f }|
M = |{ 源族 f : source_enabled[f]=True }|
```

**写入：**

- `FetchResult.cross_source_page_count` / `cross_source_page_total`
- `media_pages.cross_source_count` / `cross_source_total`
- pipeline 日志：`跨源 N/M`

**缓存路径差异：** `cached=True` 时无 `source_enabled`，从 items 推断 N，M 用默认值 3（剧）/ 2（电影）。

### 5.4 单条跨源置信度（S-04）

**函数：** `merge_by_infohash(items, total_source_families=M)`

**步骤：**

1. 按 `infohash`（40 位小写）分桶  
2. 每桶统计 **不同源族** 集合 `families`  
3. 保留 **seeders 最高**（同分比 `size_bytes`）的一条作为代表  
4. 写入：

```
cross_source_count     = len(families)          # 1 ~ M
cross_source_confidence = min(count / M, 1.0)   # 保留 3 位小数
```

**示例（剧集 M=3）：**

| 场景 | count | confidence |
|------|-------|------------|
| 仅 Jackett 命中该 hash | 1 | **0.333** |
| EZTV + Jackett 同一 hash | 2 | **0.667** |
| 三族同一 hash | 3 | **1.000** |

**N/M 与 confidence 对照：**

| 场景 | 页面 N/M | 单条 confidence |
|------|----------|-----------------|
| EZTV 1 条 + Jackett 13 条，**无相同 hash** | **2/3** | 全部 **0.333** |
| 某 hash 在 EZTV + Jackett 均出现 | 2/3 | 该条 **0.667** |
| 三族均有数据且某 hash 三族都有 | 3/3 | 该条 **1.000** |

### 5.5 下游消费（scorer / 页面）

| 用途 | 逻辑 |
|------|------|
| 排序 tie-break | seeders → 1080p → **`cross_source_count`** → group tier |
| `recommend_reason` | `cross_source_count > 1` 时追加「跨 N 个数据源交叉验证」 |
| Hero badge | 展示页面 **N/M**，不直接展示单条 confidence |
| Sources 表 | 可展示 `cross_source_count` badge（待生成器模板） |

### 5.6 测试结果 — Pipeline 基准（2026-06-30，7 槽 `--force`）

来源：[slot-pipeline-benchmark.json](../worklogs/2026-06-30/slot-pipeline-benchmark.json)

| 槽位 | magnets | 页面 N/M | 备注 |
|------|---------|----------|------|
| BB S04E01 | 14 | **1/3** | 仅 Jackett 有数据 |
| BB S04E02 | 20 | **1/3** | 同上 |
| BB S04E04 | 14 | **2/3** | EZTV + Jackett 均有返回 |
| BB S04E06 | 12 | **1/3** | 仅 Jackett |
| BB S04E07 | 14 | **1/3** | 仅 Jackett |
| BB S04E08 | 12 | **1/3** | 仅 Jackett |
| Inception | 3 | **1/2** | 仅 YTS |

### 5.7 测试结果 — MySQL 当前数据

**页面级（`media_pages`）：**

| page_id | N/M |
|---------|-----|
| tv:1396:s04e01、s04e02、s04e06~08 | **1/3** |
| tv:1396:s04e03、s04e04、s04e05 | **2/3** |
| movie:27205 | **1/2** |

**单条级（`download_resources`，live 拉取）：**

| page_id | 条数 | cross_source_count | confidence |
|---------|------|-------------------|------------|
| 各 BB 集 | 12~20 | **全部为 1** | **0.333** |
| Inception | 3 | **全部为 1** | **0.5** |

**解读：** 当前环境 **尚无真实 magnet 的 `cross_source_count > 1`**。S04E04 页面虽为 **2/3**（两族有响应），但 14 条 hash **互不重复**，故每条 confidence 仍为 **0.333**。

### 5.8 测试结果 — 缓存路径（2026-07-01，无 `--force`）

来源：[cache-path-benchmark.json](../worklogs/2026-07-01/cache-path-benchmark.json)

| 槽位 | N/M | 与冷拉取一致 |
|------|-----|-------------|
| BB S04E06 | 1/3 | ✅ |
| Inception | 1/2 | ✅ |

### 5.9 Demo 预期形态（`pipeline.py` demo，非真实数据）

| infohash | 源 | count | confidence |
|----------|-----|-------|------------|
| `aaaa…` | 模拟三族 | 3 | **1.0** |
| `bbbb…` | eztv | 2 | **0.67** |
| `cccc…` | jackett | 2 | **0.67** |
| `dddd…` | jackett | 1 | **0.33** |

### 5.10 现状瓶颈与改进方向

| 现象 | 原因 | 改进方向 |
|------|------|----------|
| 页面多为 1/3 | Nyaa 未贡献数据；EZTV 常空 | 修复 Nyaa SOCKS；EZTV 稳定性 |
| 单条 confidence 全为 0.333 | 同一 hash 极少跨 EZTV/Jackett 重复 | 正常：release 命名/索引范围不同 |
| N/M=2/3 但 confidence 仍低 | **N/M 衡量「有响应」**，confidence 衡量 **hash 重叠** | 页面文案需区分两种含义 |
| 未来提升 IG | 需 hash 级交叉验证 | 可选：title/fuzzy 对齐（未实现） |

**现状小结：**

1. **N/M** 衡量「几个源**有响应**」—— 当前多数槽位 **1/3**，S04E03~05 为 **2/3**。
2. **单条 confidence** 衡量「同一 hash **被几个源族同时索引**」—— 真实数据目前 **全部为 1**，confidence **0.333**（剧）或 **0.5**（电影）。
3. **瓶颈在数据而非算法：** EZTV 与 Jackett 极少报相同 infohash；Nyaa 在 BB 测试路径基本未贡献。
4. 提升单条 confidence 需更多源返回重叠 hash，或后续实现 title/fuzzy 对齐（P1，见 §十）。

---

## 六、Release Group 信誉（S-05 / A-06）— 计算逻辑与实现进度

> **代码：** `workflow/recommended/groups_registry.py`、`scorer.py`  
> **数据：** `workflow/recommended/data/groups.yaml`（98 组）  
> **组名输入：** `workflow/torrent_sources/release_parser.py`（A-06）  
> **调用链：** `title_raw` → `release_group` → `lookup_group` → `group_tier` → `rank_items` → MySQL / 页面

### 6.1 Tier 体系（L0~L4）

| Tier | 含义 | 示例 | 页面 Badge |
|------|------|------|------------|
| **L0** | 顶级压制组 | NTb, CtrlHD, QxR | Gold（`rm-badge--tier-l0`） |
| **L1** | 主流 Scene 组 | SPARKS, ROVERS | Verified（l1） |
| **L2** | P2P / 内部组 | ION10, TBS | Community（l2） |
| **L3** | 低质量 / 重编码 | YIFY, YTS, mSD | Low Quality（l3） |
| **L4** | 未知 / 未收录 | 解析失败、库外组名 | Unverified（l4） |

设计文档：[01-分支定位与流量获取.md](./01-分支定位与流量获取.md) §5.4.3。

### 6.2 端到端数据流

```
title_raw
  → release_parser.parse_release_title()     # A-06：正则取最后一个 - 后 token
  → ResourceItem.release_group
  → groups_registry.lookup_group()           # yaml 查 canonical + tier
  → scorer.score_item() / rank_items()       # 50% 权重 + tie-break
  → mysql_store.upsert_slot_resources()      # download_resources.group_tier 冗余
  → recommended_block.html                   # Hero Group Badge
```

**权威数据源（当前）：** 本地 `groups.yaml`，运行时直读；**非** MySQL `release_groups` 表。

### 6.3 组名解析（A-06）

**模块：** `release_parser.py`（T0 正则版，非 PTN）

规则：取 `title_raw` 最后一个 `-` 后的首段 token；排除 `S04E06`、`1080p` 等；截断至 64 字符。

**局限：**

| 情况 | 结果 |
|------|------|
| 标题无 `-` 或格式非标准 | `release_group=''` → tier **L4** |
| 尾部带扩展名 | 如 `Cosumez.avi`、`TB.mkv` → 误解析为组名 |
| indexer 标记混入 | 部分需 `groups_registry` 的 `_STRIP_SUFFIXES` 过滤 |

### 6.4 查表逻辑（groups_registry）

**文件：** `data/groups.yaml` — **98 组**（L0:20 / L1:34 / L2:33 / L3:11；**无 L4 条目**，未命中运行时默认 L4）

**匹配顺序：**

1. 整串精确匹配（含 `aliases`，大小写不敏感）
2. 按 `[\s._\-]+` 拆 token，**优先较长 token**
3. 过滤 eztv / yts / rarbg 等 indexer 后缀
4. 未命中 → canonical `""`，tier **L4**

**示例：**

| release_group | canonical | tier |
|---------------|-----------|------|
| NTb | NTb | **L0** |
| SPARKS | SPARKS | **L1** |
| YTS | YTS | **L3** |
| mSD | mSD | **L3** |
| IMMERSE / XEBEC / FQM | — | **L4**（未入 yaml） |

### 6.5 评分公式与 tie-break（scorer v1）

**主分（0~100）：**

```
score = tier_w × 50 + seeder_w × 30 + cross_w × 20

tier_w:   L0=1.0, L1=0.85, L2=0.6, L3=0.3, L4=0.1
seeder_w: min(seeders / 50, 1.0)
cross_w:  min(cross_source_count / 3, 1.0)
```

**Group tier 占 50% 权重**，但在当前 BB 测试集多数条目为 L4 时，**seeders 往往决定 Recommended**。

**同分 tie-break（降序）：** seeders → 1080p → `cross_source_count` → tier

### 6.6 推荐理由与页面展示

| tier | `recommend_reason` 文案 |
|------|-------------------------|
| L0 / L1 | `Verified Group {name}（Lx 档信誉）` |
| L2 | `Community Group {name}（L2 档）` |
| L3 / L4 | 不追加 Verified 前缀；仍可有 resolution / seeders 等 |

**页面：**

| 位置 | 状态 | 模板 |
|------|------|------|
| Recommended Hero Group Badge | ✅ | `partials/recommended_block.html` |
| Sources 表逐条 tier | ❌ 未做 | 待 T3 生成器 |
| `scene_compliant` / 合规率 | ❌ yaml 有字段，scorer **不读取** | 规划 |

### 6.7 groups.yaml 规模（2026-07-01）

| 统计 | 值 |
|------|-----|
| 总组数 | **98** |
| L0 | 20 |
| L1 | 34 |
| L2 | 33 |
| L3 | 11 |
| 维护方式 | 手工整理（T1-G1 验收） |

路径：`workflow/recommended/data/groups.yaml`

### 6.8 实现进度对照

| 模块 | 状态 | 说明 |
|------|------|------|
| `groups.yaml` + `groups_registry.py` | ✅ | T1-G1；别名 + token 匹配 |
| `scorer.py` 评分 / tie-break | ✅ | 已接真实 FetchService |
| `pipeline --fetch` 写 `group_tier` | ✅ | 冗余至 `download_resources` |
| `workflow.run recommended` | ✅ | 单槽调试 |
| Hero Group Badge 模板 + CSS | ✅ | tier-l0~l4 色板 |
| Sources 表 tier badge | ❌ | 仅 Recommended 卡片 |
| MySQL `release_groups` 表 | 🔶 | schema 有；**仅 4 条 demo seed**，未从 yaml 同步 |
| `scene_compliant` / `compliance_rate` | ❌ | yaml 字段存在，运行时未用 |
| cron 自动统计更新 | ❌ | 设计文档 §5.4.3 规划 |
| PTN / mediainfo 组名提取 | ❌ | 仍 T0 正则 |
| 生成器批量出页接 DB | 🔶 | T3 待完整 |

**登记含义：** S-05 标 ✅ = **评分链路已通**；距「信誉数据库 + 自动更新 + 合规率展示」仍有缺口。

### 6.9 测试结果 — MySQL 当前数据

**Recommended 行（`is_recommended=1`）：**

| page_id | release_group | group_tier | match_score | 说明 |
|---------|---------------|------------|-------------|------|
| tv:1396:s04e01~02, s04e04, s04e06~08 | XEBEC | **L4** | ~41 | 未入 yaml |
| movie:27205 | YTS | **L3** | ~52 | yaml 命中 |

**全库 group 分布（摘录）：**

| release_group | group_tier | 条数 | 备注 |
|---------------|------------|------|------|
| ``（空） | L4 | 25 | 解析失败 |
| FQM | L4 | 11 | 未入 yaml |
| mSD | L3 | 7 | yaml 命中 |
| ASAP | L4 | 6 | 未入 yaml |
| XEBEC | L4 | 6 | **当前 BB 推荐组** |
| YTS | L3 | 2 | 电影 |

**解读：** BB S04 测试集 **几乎没有 L0/L1 组被推荐**；Group 信誉对排序的实际 IG 贡献有限，主要靠 seeders 与 cross_source 拉分。

### 6.10 现状瓶颈与改进方向

| 现象 | 原因 | 改进方向 |
|------|------|----------|
| 多数条目 tier=L4 | 库外组名 + 解析失败 | 补 yaml：IMMERSE、XEBEC、FQM、ASAP 等 |
| 25 条空 `release_group` | T0 正则局限 | PTN 或更强 parser |
| Recommended 为 L4 组 | 池内无高 tier 竞争 | 扩源 + 补组库 |
| `release_groups` 表空壳 | 未做 yaml 同步 | 同步脚本 + 以表为权威（远期） |
| 合规率未展示 | scorer 不读 `scene_compliant` | 写入 `recommend_reason`（远期） |

**现状小结：**

1. **当前是静态手工分档**（yaml），非动态统计信誉。
2. **评分链路完整**，但真实数据 tier 分布偏 L4，S-05 的页面 IG 尚未充分体现。
3. 优先 **补 groups.yaml** 与 **改进组名解析**，比 cron 统计更紧迫（见 §十 P1）。

---

## 七、测速 S-06（Phase 2 片段测速）

> **代码：** `speedtest/phase2_speed.py`、`full_speed.py`、`store_service.py`  
> **CLI：** `python -m workflow.torrent_sources.speedtest.run speed|full|slot`

### 7.1 能力说明

| 字段 | 来源 | 存储 |
|------|------|------|
| `avg_kbps` / `max_kbps` | libtorrent 下载 target_bytes（默认 1MB） | `speedtest_results` phase=2 |
| `latency_ms` | 首字节 payload 延迟 | 同上 |
| `recommended_speed` | `format_recommended_speed(avg_kbps)` | `slot_speed_summary` |
| `reachability` | Phase1/2 peers → 高/中/低 | `slot_speed_summary` |

### 7.2 CLI 用法

```bash
# Phase 2 单条
python -m workflow.torrent_sources.speedtest.run speed \
  --infohash <40hex> --page-id tv:1396:s04e06 --timeout 45

# Phase 1 + 2 + 写 MySQL
python -m workflow.torrent_sources.speedtest.run full \
  --infohash <40hex> --page-id tv:1396:s04e06 --write

# 槽位 Recommended（推荐）
python -m workflow.torrent_sources.speedtest.run slot \
  --page-id tv:1396:s04e06 --write --target-bytes 262144
```

### 7.3 实测（2026-07-01，BB S04E06 Recommended）

来源：[speedtest-phase2-benchmark.json](../worklogs/2026-07-01/speedtest-phase2-benchmark.json)

| 模式 | target | elapsed | avg_kbps | max_kbps | peers | recommended_speed |
|------|--------|---------|----------|----------|-------|-------------------|
| Phase 1 | — | **6.0s** | — | — | **30** | — |
| Phase 2 | 256 KB | **8.1s** | **22.2** | **87.3** | 46 | 22 KB/s |
| Phase 2 | 1 MB | **18.0s** | **50.2** | **239.0** | 37 | 50 KB/s |
| slot + write | 256 KB | P1+P2 **~30s** | **21.9** | **77.9** | 46 | → MySQL |

**索引 vs 实测：** 索引 seeders **50** → 实测 peers **30–46**、速度 **22–50 KB/s**（2160p WEB-DL）。

### 7.4 批量时间成本（综合评估）

> 完整推导见 [speedtest-Phase1探测.md §五](../worklogs/2026-07-01/speedtest-Phase1探测.md#五速度与批量时间成本综合评估)

**规划取值（+20% buffer）：**

| 策略 | 单槽 | 7 槽 | 100 页（串行） | 100 页（5 Worker） |
|------|------|------|----------------|-------------------|
| A0 仅 Phase 1 | 12s | 1.4 min | 20 min | 4 min |
| **A2 slot @256KB（默认）** | **25s** | **2.9 min** | **42 min** | **~8 min** |
| A3 slot @1MB | 35s | 4.1 min | 58 min | ~12 min |
| C 全量 15 条/槽 | 6.3 min | 44 min | 6.3 h | 不可行 |

**cron 推荐：** `slot --write --target-bytes 262144`；重点页升 1MB。

**与 pipeline 对比（7 槽）：** 冷拉取 **507s** vs 测速 A2 **~175s** — 可独立异步跑。

### 7.5 实现状态

| 模块 | 状态 |
|------|------|
| Phase 2 libtorrent 测速 | ✅ |
| 写 `speedtest_results` | ✅ |
| 聚合 `slot_speed_summary` | ✅ |
| 生成器 speed bar 渲染 | 📋 T3 |
| 批量 cron Worker | 📋 |

**登记 🔶：** 后端链路已通；页面静态 bake 待 T3 生成器。

---

## 八、索引 seeders vs 实测 peer（对照登记）

| 维度 | 索引 seeders（B-02） | 实测 peers（A-02） |
|------|----------------------|---------------------|
| 来源 | Jackett/EZTV API | libtorrent DHT/tracker |
| IG | 2~4 | **5~7** |
| 典型偏差 | 偏高/过期 | 时点真实 |
| 示例 | seeders=50 | peers_total=29 |
| 页面用法 | Sources 表参考列 | speed 区 + IG 文案 |

---

## 九、IG 组合与页面分数估算

| 组合 | 含 IG-ID | 页面 IG 估分 |
|------|----------|--------------|
| 仅 magnet 列表 | B-01~B-05 | **2~4** |
| + Recommended + 对版 | S-01, S-02, A-04~A-06 | **5~7** |
| + 跨源 + Group | + S-03, S-04, S-05 | **7~8** |
| + Phase 1 测速 | + A-01, A-02, A-03, S-07 | **6~8** |
| + Phase 2 测速 | + S-06, A-09 | **8~9** |
| 全栈 + 多地域 | + S-08 | **9~10** |

---

## 十、实现缺口（登记 → 开发）

| 优先级 | IG-ID | 缺口 | 负责 |
|--------|-------|------|------|
| P0 | A-01, A-03, S-07 | 生成器渲染 `slot_speed_summary` speed bar | T2 + T3 |
| P0 | A-07 | timeout 条目不展示 / 降权 | T2 + 生成器 |
| P1 | S-05 | 补 `groups.yaml`（IMMERSE/XEBEC/FQM 等 BB 高频组） | T1 |
| P1 | S-05 | yaml → MySQL `release_groups` 同步脚本 | T1 |
| P1 | S-05 | Sources 表 `group_tier` badge | T3 生成器 |
| P1 | S-06 | 批量 `slot` cron + 增量测速 TTL | T2 |
| P1 | A-09 | Phase 2 首包延迟页面展示 | T3 |
| P1 | S-04 | title/fuzzy 对齐提升 hash 级跨源重叠 | T1 |
| P1 | A-10 | 索引 vs 实测对比文案模板 | T3 生成器 |
| P2 | S-05 | cron 统计 + `scene_compliant` 入推荐理由 | T1 |
| P2 | S-05 | PTN / mediainfo 组名提取 | T0 |
| P2 | S-08 | 多节点 Worker | T2+ |

---

## 十一、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-01 | 初版：按 IG 等级 + 测试阶段 + 页面区块登记 |
| v1.1 | 2026-07-01 | §五 跨源 S-03/S-04 计算逻辑 + 基准/MySQL/缓存测试结果 |
| v1.2 | 2026-07-01 | §六 Release Group S-05/A-06 计算逻辑 + 实现进度 + MySQL 实测 |
| v1.3 | 2026-07-01 | §七 S-06 Phase 2 + 批量成本综合评估 + benchmark JSON |
| v1.4 | 2026-07-01 | 迁移至 `docs/IG信息登记册.md`（正式文档） |
