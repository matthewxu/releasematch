# speedtest 安装、使用与 IG 评估

> **日期：** 2026-07-01（v1.1）  
> **模块：** `workflow/torrent_sources/speedtest/`  
> **当前阶段：** Phase 1 连接性探测（libtorrent 2.x）  
> **关联表：** `speedtest_results`、`slot_speed_summary`

---

## 一、模块概览

| 阶段 | 能力 | 单条耗时（实测/设计） | 状态 |
|------|------|----------------------|------|
| **Phase 1** | DHT/tracker peer 发现，不下载 payload | **~12s**（成功）/ 10~20s（超时） | ✅ 已实现 |
| **Phase 2** | 下载前 1MB 测 KB/s | 10~30s/条（设计） | 🔧 待建 |
| **Phase 3** | 多地域节点测速 | 分钟级/条 | 📋 M8+ |

**设计文档：** [docs/01-分支定位与流量获取.md](../../docs/01-分支定位与流量获取.md) §5.2.1、§5.4  
**存储 schema：** [docs/05-存储与部署配置.md](../../docs/05-存储与部署配置.md) §5.7~5.8

---

## 二、安装

### 2.1 环境要求

| 项 | 要求 |
|----|------|
| Python | 3.8+（推荐 3.11~3.13） |
| 系统 | macOS / Linux（Windows 需自行编译 libtorrent） |
| 网络 | UDP 6881+（DHT）；受限网络建议 **海外 VPS** 跑测速 Worker |
| VPS 选型 | 允许 BT 流量（Hetzner 等）；**避免** Linode/DigitalOcean ToS 限制 |

### 2.2 标准安装（项目 venv）

```bash
cd releasematch

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 安装依赖（含 libtorrent==2.0.13）
pip install -r requirements.txt

# 验证
python -m workflow.torrent_sources.speedtest.run status
```

**期望输出：**

```json
{
  "module": "speedtest",
  "phase": 1,
  "libtorrent_available": true,
  "implementation": "phase1"
}
```

### 2.3 常见问题

| 问题 | 原因 | 处理 |
|------|------|------|
| `No module named 'libtorrent'` | 未在 venv 内安装 | 用 `.venv/bin/pip install libtorrent==2.0.13` |
| PEP 668 拒绝系统 pip | macOS Homebrew Python | **必须用 venv**，勿 `--break-system-packages` |
| `peers_total=0` 且 timeout | 本机 UDP/DHT 被墙或防火墙 | 传完整 `--magnet-uri`；或改在海外 VPS 跑 |
| `sha1_hash has no len()` | libtorrent 1.x 旧 API | 已修复为 `parse_magnet_uri`（2.x） |

### 2.4 可选：仅 scaffold（不装 libtorrent）

```bash
python -m workflow.torrent_sources.speedtest.run test \
  --infohash 583d172ea1eaf082f6b73627c1a56b1299f92ba7 \
  --dry-run
# status: dry_run — 仅校验 infohash 格式
```

---

## 三、使用说明

### 3.1 CLI 命令

```bash
# 模块状态
python -m workflow.torrent_sources.speedtest.run status

# Phase 1 单条探测（推荐传完整 magnet，含 tracker）
python -m workflow.torrent_sources.speedtest.run test \
  --infohash <40位小写hex> \
  --page-id tv:1396:s04e06 \
  --timeout 20 \
  --magnet-uri "magnet:?xt=urn:btih:...&tr=udp://..."

# 格式校验（不联网）
python -m workflow.torrent_sources.speedtest.run test \
  --infohash <hash> --dry-run
```

### 3.2 从缓存取 magnet 测 Recommended

```bash
cd releasematch

# 取 BB S04E06 缓存中 seeders 最高条的 magnet
MAGNET=$(python -c "
import json
from workflow.torrent_sources.cache_index import CacheIndex
row = CacheIndex().get('tv:1396:s04e06')
items = json.loads(row['payload_json'])
best = max(items, key=lambda x: x.get('seeders', 0))
print(best['magnet_uri'])
")

python -m workflow.torrent_sources.speedtest.run test \
  --infohash 583d172ea1eaf082f6b73627c1a56b1299f92ba7 \
  --page-id tv:1396:s04e06 \
  --timeout 20 \
  --magnet-uri \"\$MAGNET\"
```

### 3.3 输出字段说明

| 字段 | 含义 | Phase |
|------|------|-------|
| `infohash` | 被测 hash（小写 40 位） | 1 |
| `peers_total` | 观测到的 peer 总数 | 1 |
| `peers_reachable` | 已连接 peer 数（flags bit 0） | 1 |
| `elapsed_ms` | 探测耗时毫秒 | 1 |
| `status` | `ok` \| `timeout` \| `error` \| `dry_run` | 1 |
| `mode` | `libtorrent` \| `dry_run` | 1 |
| `avg_kbps` / `max_kbps` | 平均/峰值速度 | 2（待建） |
| `latency_ms` | 首包延迟 | 2（待建） |

### 3.4 2026-07-01 实测样例

| 槽位 | infohash（前 8 位） | seeders（索引源） | peers_total | elapsed | status |
|------|---------------------|-------------------|-------------|---------|--------|
| BB S04E06 | `583d172e…` | 50 | **29** | 12.0s | ok |

---

## 四、IG 信息登记册

> **完整登记：** [IG信息登记册.md](./IG信息登记册.md)（按 S/A/B/C 等级 + 测试阶段 + 页面落点）  
> 本节保留测速模块摘要。

### 4.0 登记等级速查

| 等级 | 分数 | 测速相关代表字段 |
|------|------|------------------|
| **S** | 8~10 | `recommended_speed`（P2）、Recommended 实测背书 |
| **A** | 5~7 | `reachability`、`peers_total`、`tested_at`、死链过滤 |
| **B** | 2~4 | 索引 `seeders`（非实测，不算 IG） |
| **C** | 0~1 | 0 条 magnet 薄页 |

### 4.1 测速模块 IG-ID 对照

| IG-ID | 名称 | Phase | 字段 | 等级 | 状态 |
|-------|------|-------|------|------|------|
| S-06 | 实测下载速度 | P2 | `avg_kbps` → `recommended_speed` | S | 📋 |
| S-07 | Recommended 实测背书 | P1+P2 | `recommended_infohash` + reachability | S | 🔶 |
| A-01 | Peer 可达性 | P1 | `reachability`（派生） | A | 🔶 |
| A-02 | 实测 peer 数 | P1 | `peers_total` / `peers_reachable` | A | ✅ |
| A-03 | 测速时间戳 | P1 | `tested_at` | A | 🔶 |
| A-07 | 死链过滤 | P1 | `status=timeout` | A | 🔶 |
| A-09 | 首包延迟 | P2 | `latency_ms` | A | 📋 |
| A-10 | 索引 vs 实测 | P1 | seeders vs peers_total | A | 🔶 |
| B-02 | 索引 seeders | 拉取 | `seeders` | B | ✅（非 IG） |

### 4.2 按阶段：测速产出 vs 页面展示

| IG 信号 | Phase 1（当前） | Phase 2（规划） | 写入位置 | 页面展示 |
|---------|----------------|-----------------|----------|----------|
| **可达性等级** | ✅ peers → 高/中/低 | ✅ | `slot_speed_summary.reachability` | 顶栏 speed bar |
| **peer 数量** | ✅ peers_total | ✅ | `speedtest_results` | 可选 badge |
| **实测速度** | ❌ | ✅ avg/max KB/s | `recommended_speed` | 「前次测速 4.2 MB/s」 |
| **延迟** | ❌ | ✅ latency_ms | `speedtest_results` | 高级用户区 |
| **测速时间戳** | ✅ tested_at | ✅ | `updated_at` | 「UTC 更新时间」 |
| **死链过滤** | ✅ status=timeout | ✅ | 间接 | 列表隐藏不可达项 |
| **Recommended 实测背书** | ✅ 仅测 is_recommended | ✅ | `recommended_infohash` | IG 文案增强 |

### 4.3 reachability 映射规则（A-01 派生）

| peers_total | reachability | 页面文案示例 |
|-------------|--------------|--------------|
| ≥ 10 | **高** | 「Peer 可达性：高（29 peers 观测）」 |
| 3~9 | **中** | 「Peer 可达性：中（5 peers）」 |
| 1~2 | **低** | 「Peer 可达性：低（1 peer）」 |
| 0 / timeout | **不可达** | 不展示或标注「上次测速不可达」 |

### 4.4 测速不能单独提供的 IG（见登记册 §2.1 其他 S/A 项）

| IG 能力 | IG-ID | 负责模块 |
|---------|-------|----------|
| Recommended 选型 | S-01 | T1 scorer |
| 推荐理由 | S-02 | T1 scorer |
| 跨源 N/M | S-03, S-04 | T1 cross_source |
| Group 信誉 | S-05 | T1 groups.yaml |
| 质量解析 | A-05, A-06 | T0 parser |

### 4.5 IG 组合分数（测速视角）

| 能力组合 | IG 分数（估） | 说明 |
|----------|---------------|------|
| 仅 seeders（无测速） | 2~4 | 竞品普遍有，IG 低 |
| Phase 1 reachability | **5~7** | 「本站实测 peer 可达」— 多数站没有 |
| Phase 1 + Recommended 背书 | **6~8** | 推荐项 + 实测可达 = 强 IG |
| Phase 2 实测 MB/s | **8~9** | 「Group-X 2.4 MB/s」— 独家数据 |
| Phase 2 + 跨源 + Group 信誉 | **8~10** | docs/01 所述前 3 项覆盖 ~70% IG 增量 |

**SEO 落地：** 测速摘要必须以 **静态 HTML 文本** bake 进页面（非纯 JS），供 Googlebot 索引。

---

## 五、速度与批量时间成本

### 5.1 单条耗时（基于 2026-07-01 实测）

| 场景 | 耗时 | 备注 |
|------|------|------|
| Phase 1 成功（有 peer） | **~12s** | BB S04E06，timeout=20 |
| Phase 1 超时（无 peer） | **~10~20s** | 等于 `--timeout` |
| dry-run | **<0.1s** | 不联网 |
| Phase 2（设计目标） | **10~30s/条** | 下载 1MB |

> 设计文档原估 Phase 1 为 3~5s/条；实测 **~12s** 更保守，批量规划按 **15s/条** 估算。

### 5.2 单槽成本（每槽 magnet 条数来自 pipeline）

| 策略 | 每槽测几条 | 单槽耗时（@15s/条） | 适用 |
|------|-----------|---------------------|------|
| **A. 仅 Recommended** | 1 | **~15s** | 日常 cron、MVP |
| **B. Top 3 by seeders** | 3 | **~45s** | C1 验证集 |
| **C. 全量列表** | 12~20 | **~3~5min** | 不推荐常规跑 |

### 5.3 批量估算表

| 批量规模 | 策略 A（1条/槽） | 策略 B（3条/槽） | 策略 C（15条/槽） |
|----------|------------------|------------------|-------------------|
| **7 槽**（当前 benchmark） | 1.8 min | 5.3 min | 26 min |
| **20 页**（C1 验证集） | 5 min | 15 min | 75 min |
| **100 页** | 25 min | 75 min | **6.3 h** |
| **1,000 页** | 4.2 h | 12.5 h | **62 h** |
| **10,000 页** | **42 h** | 125 h | 不可行（需并行） |

*上表为 **串行** 单 Worker；timeout 15s、无并发。*

### 5.4 并行与降本策略

| 手段 | 效果 | 说明 |
|------|------|------|
| **5 并发 Worker**（VPS） | 时间 ÷5 | 100 页策略 A：25min → **5min** |
| **仅测 Recommended** | 条数 ÷12 | 默认 cron 策略 |
| **增量测速** | 跳过 6h 内已测 hash | 类似 torrent cache TTL |
| **Phase 1 筛选 + Phase 2 子集** | Phase 2 仅对 top 3 | 速度数据只给高价值项 |
| **部署在海外 VPS** | 减少 timeout 浪费 | 本机 UDP 受限时 timeout 率高 |

### 5.5 与 pipeline 耗时对比

| 阶段 | 7 槽冷拉取（2026-06-30） | 7 槽缓存（2026-07-01） | 7 槽 Phase 1 测速（策略 A） |
|------|--------------------------|------------------------|----------------------------|
| wall 时间 | **507s（8.5min）** | **0.4s** | **~105s（1.8min）** |

**结论：** 测速可独立于 pipeline 跑；日常建议 **pipeline 写库 → cron 仅测 Recommended**，不阻塞页面生成。

### 5.6 资金成本（月度，来自 docs/01）

| 项 | Phase 1 | Phase 1+2 |
|----|---------|-----------|
| VPS | ~$5（Hetzner CPX11） | ~$9（CPX21） |
| 带宽 | ~$0（Phase 1 几乎无 payload） | ~$0（25GB/月量级在套餐内） |

---

## 六、后续路线图（T2）

| 优先级 | 任务 | 估时 |
|--------|------|------|
| P0 | `result_store.py` 写 MySQL `speedtest_results` | 0.5d |
| P0 | 聚合 → `slot_speed_summary` + 生成器渲染 | 0.5d |
| P1 | `batch` 子命令：按 page_id 测 Recommended | 1d |
| P1 | 海外 VPS daemon + cron | 1d |
| P2 | Phase 2 片段测速 `phase2_speed.py` | 3d |
| P3 | 增量 TTL、并发 Worker 池 | 1.5d |

---

## 七、关联命令速查

```bash
# 状态
python -m workflow.torrent_sources.speedtest.run status

# 真实 Phase 1
python -m workflow.torrent_sources.speedtest.run test \
  --infohash <hash> --page-id <page_id> --timeout 20 --magnet-uri "<magnet>"

# pipeline 拉取（测速前需有 magnet 数据）
python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6

# 页面生成（T2 后含 speed_summary）
python -m workflow.run generate page --page-id tv:1396:s04e06
```

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-01 | Phase 1 真实探测；libtorrent 2.x |
| v1.2 | 2026-07-01 | 对接 [IG信息登记册.md](./IG信息登记册.md)；IG-ID 对照表 |
