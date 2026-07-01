# speedtest 安装、使用与 IG 评估

> **日期：** 2026-07-01（**v1.3**）  
> **模块：** `workflow/torrent_sources/speedtest/`  
> **当前阶段：** Phase 1 连接性 + **Phase 2 片段测速（S-06）**  
> **关联表：** `speedtest_results`、`slot_speed_summary`  
> **基准数据：** [speedtest-phase2-benchmark.json](./speedtest-phase2-benchmark.json)

---

## 一、模块概览

| 阶段 | 能力 | 单条耗时（实测/规划） | 状态 |
|------|------|----------------------|------|
| **Phase 1** | DHT/tracker peer 发现，不下载 payload | **~6–12s**（成功）/ 20s（超时） | ✅ |
| **Phase 2** | 下载片段测 KB/s → `recommended_speed` | **~10s**（256KB）/ **~20s**（1MB） | ✅ |
| **Phase 3** | 多地域节点测速 | 分钟级/条 | 📋 M8+ |

**设计文档：** [docs/01-分支定位与流量获取.md](../../docs/01-分支定位与流量获取.md) §5.2.1、§5.4  
**存储 schema：** [docs/05-存储与部署配置.md](../../docs/05-存储与部署配置.md) §5.7~5.8  
**IG 登记：** [IG信息登记册.md §七](../../docs/IG信息登记册.md#七测速-s-06phase-2片段测速)

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

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python -m workflow.torrent_sources.speedtest.run status
```

**期望输出：**

```json
{
  "module": "speedtest",
  "phases": [1, 2],
  "libtorrent_available": true,
  "implementation": "phase1+phase2",
  "s06_fields": ["avg_kbps", "max_kbps", "recommended_speed"]
}
```

### 2.3 常见问题

| 问题 | 原因 | 处理 |
|------|------|------|
| `No module named 'libtorrent'` | 未在 venv 内安装 | `.venv/bin/pip install libtorrent==2.0.13` |
| PEP 668 拒绝系统 pip | macOS Homebrew Python | **必须用 venv** |
| `peers_total=0` 且 timeout | UDP/DHT 受限 | 传 `--magnet-uri`；改海外 VPS |
| Phase1 timeout 但 Phase2 ok | P1 等待 peer 较慢，P2 下载时 peer 增加 | 正常；`reachability` 取 Phase1/2 max peers |
| 速度偏低（~22 KB/s） | 2160p WEB-DL 单连接、本机网络 | VPS 复测；页面仍展示「实测」IG |

---

## 三、使用说明

### 3.1 CLI 命令一览

| 子命令 | 阶段 | 用途 |
|--------|------|------|
| `status` | — | libtorrent 可用性 |
| `test` | Phase 1 | peer 可达性 |
| `speed` | Phase 2 | 片段下载测速（S-06） |
| `full` | P1+P2 | 组合测速，可选 `--write` |
| `slot` | P1+P2 | **MySQL Recommended 槽位**，可选 `--write` |

```bash
# Phase 1
python -m workflow.torrent_sources.speedtest.run test \
  --infohash <40hex> --page-id tv:1396:s04e06 --timeout 20 \
  --magnet-uri "magnet:?xt=urn:btih:..."

# Phase 2（S-06）
python -m workflow.torrent_sources.speedtest.run speed \
  --infohash <40hex> --page-id tv:1396:s04e06 \
  --timeout 45 --target-bytes 262144

# 槽位 Recommended + 写 MySQL（日常推荐）
python -m workflow.torrent_sources.speedtest.run slot \
  --page-id tv:1396:s04e06 --write --target-bytes 262144

# Phase 1 + 2 + 写库
python -m workflow.torrent_sources.speedtest.run full \
  --infohash <40hex> --page-id tv:1396:s04e06 --write
```

### 3.2 从 MySQL / 缓存取 magnet

**slot 命令**自动从 `download_resources` 读取 `is_recommended=1` 的 `magnet_uri`。

手动从缓存：

```bash
MAGNET=$(python -c "
import json
from workflow.torrent_sources.cache_index import CacheIndex
row = CacheIndex().get('tv:1396:s04e06')
items = json.loads(row['payload_json'])
best = max(items, key=lambda x: x.get('seeders', 0))
print(best['magnet_uri'])
")
```

### 3.3 输出字段说明

| 字段 | 含义 | Phase |
|------|------|-------|
| `peers_total` / `peers_reachable` | 观测 / 已连接 peer | 1 |
| `elapsed_ms` | 探测或下载耗时 | 1 / 2 |
| `status` | ok \| timeout \| error \| dry_run | 1 / 2 |
| `avg_kbps` / `max_kbps` | 平均 / 峰值 KiB/s | **2** |
| `latency_ms` | 首字节 payload 延迟 | **2** |
| `bytes_downloaded` | 实际下载字节 | **2** |
| `recommended_speed` | 页面文案，如 `22 KB/s` | 聚合 |
| `reachability` | 高 \| 中 \| 低 \| 不可达 | 聚合 |

### 3.4 2026-07-01 实测样例（BB S04E06 Recommended）

来源：[speedtest-phase2-benchmark.json](./speedtest-phase2-benchmark.json)

| 模式 | target | elapsed | avg_kbps | max_kbps | peers | recommended_speed |
|------|--------|---------|----------|----------|-------|-------------------|
| Phase 1 | — | **6.0s** | — | — | **30** | — |
| Phase 2 | 256 KB | **8.1s** | **22.2** | **87.3** | 46 | 22 KB/s |
| Phase 2 | **1 MB** | **18.0s** | **50.2** | **239.0** | 37 | 50 KB/s |
| slot + write | 256 KB | P1 20s + P2 8s | **21.9** | **77.9** | 46 | 22 KB/s → MySQL |

**索引 vs 实测：**

| 维度 | 索引（B-02） | 实测（A-02 / S-06） |
|------|--------------|---------------------|
| BB S04E06 | seeders **50** | peers **30–46**；速度 **22–50 KB/s** |
| IG 价值 | 2~4 | **8~9**（Phase 2 含 MB/s 文案） |

---

## 四、IG 信息登记册

> **完整登记：** [IG信息登记册.md](../../docs/IG信息登记册.md)

### 4.1 测速模块 IG-ID 对照（更新）

| IG-ID | 名称 | Phase | 字段 | 等级 | 状态 |
|-------|------|-------|------|------|------|
| S-06 | 实测下载速度 | P2 | `avg_kbps` → `recommended_speed` | S | 🔶 CLI+MySQL ✅ |
| S-07 | Recommended 实测背书 | P1+P2 | `recommended_infohash` + reachability | S | 🔶 MySQL ✅ |
| A-01 | Peer 可达性 | P1 | `reachability` | A | 🔶 写库 ✅ |
| A-02 | 实测 peer 数 | P1 | `peers_total` | A | ✅ |
| A-03 | 测速时间戳 | P1+P2 | `tested_at` / `updated_at` | A | 🔶 写库 ✅ |
| A-07 | 死链过滤 | P1 | `status=timeout` | A | 🔶 |
| A-09 | 首包延迟 | P2 | `latency_ms` | A | ✅ CLI |
| A-10 | 索引 vs 实测 | P1 | seeders vs peers | A | 🔶 |

### 4.2 按阶段：测速产出 vs 页面展示

| IG 信号 | Phase 1 | Phase 2 | 写入位置 | 页面展示 |
|---------|---------|---------|----------|----------|
| 可达性 | ✅ | ✅ | `slot_speed_summary.reachability` | speed bar |
| peer 数量 | ✅ | ✅ | `speedtest_results` | 可选 |
| **实测速度** | ❌ | ✅ | `recommended_speed` | 「前次测速 22 KB/s」 |
| 延迟 | ❌ | ✅ | `latency_ms` | 高级区 |
| 时间戳 | ✅ | ✅ | `updated_at` | 更新日期 |
| Recommended 背书 | ✅ | ✅ | `recommended_infohash` | Hero 块 |

### 4.3 reachability 映射（A-01）

| peers_total（取 P1/P2 max） | reachability |
|----------------------------|--------------|
| ≥ 10 | **高** |
| 3~9 | **中** |
| 1~2 | **低** |
| 0 且双阶段失败 | **不可达** |

### 4.4 IG 组合分数（测速视角）

| 能力组合 | IG 估分 |
|----------|---------|
| 仅 seeders | 2~4 |
| Phase 1 reachability | 5~7 |
| Phase 1 + Recommended 背书 | 6~8 |
| **Phase 2 实测 KB/s（当前）** | **8~9** |
| Phase 2 + 跨源 + Group | **8~10** |

---

## 五、速度与批量时间成本（综合评估）

> **基准：** [speedtest-phase2-benchmark.json](./speedtest-phase2-benchmark.json)  
> **规划取值：** 在实测基础上 +20% buffer，用于 cron 容量规划

### 5.1 单条耗时（实测 vs 规划）

| 场景 | 实测 wall | 规划取值 | 说明 |
|------|-----------|----------|------|
| Phase 1 成功 | **6–12s** | **12s** | peer 发现 |
| Phase 1 超时 | 20s | **20s** | = `--phase1-timeout` |
| Phase 2 @ **256 KB** | **~10s** | **12s** | **cron 推荐**：够算 avg/max，省时 |
| Phase 2 @ **1 MB** | **~19s** | **20s** | 设计文档目标；更稳的速度样本 |
| **slot 完整**（P1+P2 @256KB） | **~30s** | **25s** | `slot --write` 端到端 |
| **slot 完整**（P1+P2 @1MB） | — | **35s** | 1MB 目标估算 |
| dry-run | <0.1s | — | 不联网 |

**速度质量（BB S04E06，2160p）：**

| target_bytes | avg_kbps | max_kbps | 页面文案 | 样本质量 |
|--------------|----------|----------|----------|----------|
| 256 KB | ~22 | ~87 | 22 KB/s | 够 S-06 MVP |
| 1 MB | ~50 | ~239 | 50 KB/s | 更平滑，多 10s |

**结论：** 日常 cron 用 **`--target-bytes 262144`（256KB）**；C1 验证集或重点页可升到 1MB。

### 5.2 测速策略矩阵

| 策略 | 每槽条数 | 单槽规划耗时 | S-06 | 适用 |
|------|----------|--------------|------|------|
| **A0. 仅 Phase 1** | 1 | **12s** | ❌ | 死链筛选、不写速度 |
| **A1. 仅 Phase 2**（256KB） | 1 | **12s** | ✅ | P1 近期已测时增量 |
| **A2. slot 完整**（256KB） | 1 | **25s** | ✅ | **日常 cron 默认** |
| **A3. slot 完整**（1MB） | 1 | **35s** | ✅ | 重点页 / 验证集 |
| B. Top 3 / 槽 | 3 | 75s（A2×3） | 部分 | C1 多源对比 |
| C. 全量 15 条/槽 | 15 | **6.3 min** | 部分 | 不推荐常规 |

### 5.3 批量估算表（串行单 Worker）

**策略 A2（slot 完整 @256KB，25s/槽）— 推荐默认**

| 批量规模 | wall 时间 | 说明 |
|----------|-----------|------|
| **7 槽**（benchmark 集） | **2.9 min** | vs pipeline 冷拉取 507s |
| **20 页**（C1 验证集） | **8.3 min** | |
| **100 页** | **42 min** | |
| **1,000 页** | **7.0 h** | 需并行 |

**策略 A0（仅 Phase 1，12s/槽）— 仅筛 dead link**

| 批量规模 | wall 时间 |
|----------|-----------|
| 7 槽 | 1.4 min |
| 100 页 | 20 min |

**策略 A3（slot @1MB，35s/槽）— 高质量速度**

| 批量规模 | wall 时间 |
|----------|-----------|
| 7 槽 | 4.1 min |
| 100 页 | 58 min |

**策略 C（全量 15 条×25s）**

| 批量规模 | wall 时间 |
|----------|-----------|
| 7 槽 | 44 min |
| 100 页 | **6.3 h** |

### 5.4 并行与降本

| 手段 | 效果 | 说明 |
|------|------|------|
| **5 并发 VPS Worker** | 时间 ÷5 | 100 页 A2：42min → **~8 min** |
| **仅测 Recommended** | 条数 ÷12~15 | 默认 cron |
| **256KB 替代 1MB** | Phase2 **~10s vs ~20s** | S-06 MVP 足够 |
| **增量 TTL 6h** | 跳过近期 hash | 类似 torrent cache |
| **Phase2-only 增量** | 省 Phase1 12s | P1 未过期时只跑 `speed` |
| **海外 VPS** | 降低 timeout 率 | 本机 UDP 受限时 |

### 5.5 与 pipeline 耗时对比

| 阶段 | 7 槽 | 100 页 | 备注 |
|------|------|--------|------|
| pipeline 冷拉取 `--force` | **507s（8.5min）** | ~2 h（估） | 2026-06-30 |
| pipeline 缓存命中 | **0.4s** | — | 2026-07-01 |
| 测速 A0（P1 only） | **~84s** | ~20 min | 不写 S-06 |
| 测速 **A2（slot 256KB）** | **~175s（2.9min）** | **~42 min** | **S-06 默认** |
| 测速 A3（slot 1MB） | **~245s** | ~58 min | 高质量 |

**结论：**

1. 测速与 pipeline **解耦**；页面生成不阻塞测速。
2. S-06 完整链路（A2）比仅 Phase 1 多 **~13s/槽**，换 **8~9 分 IG** 值得。
3. 100 页串行 ~42min 不可接受 → **5 Worker ≈ 8min** 为生产目标。

### 5.6 带宽与资金成本

**单条 payload（Phase 2）：**

| target_bytes | 每槽下载 | 100 页 | 1,000 页 |
|--------------|----------|--------|----------|
| 256 KB | ~0.25 MB | **~25 MB** | ~250 MB |
| 1 MB | ~1 MB | **~100 MB** | ~1 GB |

**月度（策略 A2，100 页/天 × 30，256KB）：**

| 项 | 估算 |
|----|------|
| 出站带宽 | ~750 MB/月（可忽略） |
| VPS | **~$9/月**（Hetzner CPX21，允许 BT） |
| MySQL | $0（已有） |

### 5.7 生产 cron 建议

```bash
# 每日 04:00 UTC — 仅 Recommended，256KB，写 MySQL
python -m workflow.torrent_sources.speedtest.run slot \
  --page-id "$PAGE_ID" \
  --write \
  --target-bytes 262144 \
  --phase1-timeout 20 \
  --timeout 45
```

| 参数 | 推荐值 | 原因 |
|------|--------|------|
| `--target-bytes` | **262144** | 10s 级 Phase2；够 S-06 |
| `--phase1-timeout` | 20 | 与实测一致 |
| `--timeout` | 45 | Phase2 上限 |
| 并发 | 5 Worker | 100 页 <10min |

---

## 六、后续路线图（T2/T3）

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P0 | Phase 2 + MySQL + `slot_speed_summary` | ✅ |
| P0 | 生成器渲染 `recommended_speed` speed bar | 📋 T3 |
| P1 | `batch` 子命令（多 page_id） | 📋 |
| P1 | 海外 VPS cron + 5 并发 Worker | 📋 |
| P1 | 增量 TTL（6h 内跳过已测 hash） | 📋 |
| P2 | Phase2-only 增量（跳过新鲜 P1） | 📋 |
| P3 | Phase 3 多地域 | 📋 |

---

## 七、关联命令速查

```bash
python -m workflow.torrent_sources.speedtest.run status

python -m workflow.torrent_sources.speedtest.run slot \
  --page-id tv:1396:s04e06 --write --target-bytes 262144

python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6

python -m workflow.storage.pipeline query --page-id tv:1396:s04e06
```

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-01 | Phase 1 真实探测；libtorrent 2.x |
| v1.1 | 2026-07-01 | 批量时间成本 §五 |
| v1.2 | 2026-07-01 | 对接 [IG信息登记册](../../docs/IG信息登记册.md) |
| v1.3 | 2026-07-01 | **Phase 2 实现**；综合速度/成本评估；benchmark JSON |
| v1.4 | 2026-07-01 | IG 登记册迁移至 [docs/IG信息登记册.md](../../docs/IG信息登记册.md) |
