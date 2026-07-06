# 2026-07-06 — torrent metadata 回填与页面优化

> **日期：** 2026-07-06  
> **关联：** [TRACKER §五](../TRACKER-E-E-A-T-InfoGain.md) · [IG 登记册 A-11](../../IG信息登记册.md) · [12-日常运营执行手册 §五](../../12-日常运营执行手册.md)

---

## 一、背景

Phase 2 测速已能写入 `torrent_metadata` 表（swarm 侧 `.torrent` info 结构），但旧库缺表、页面未 bake、展示层存在 UIndex 垃圾前缀。需在 **不重拉 indexer** 前提下回填 metadata 并优化 Recommended 区块呈现。

---

## 二、变更摘要

### 2.1 数据层

| 项 | 说明 |
|----|------|
| 表 | `torrent_metadata`（旧库 `schema/mysql_migrate_torrent_metadata.sql` 或脚本自动迁移） |
| 回填脚本 | `scripts/speedtest_retest_no_refetch.py` — 只读 Recommended magnet，默认 `--force` |
| Phase 2 修复 | 须 `has_metadata` 后才因下载字节达标退出（避免 metadata 未就绪即结束） |
| 迁移修复 | `ensure_torrent_metadata_table()` 改用 `execute_sql_file()`（原 `--` 注释导致 CREATE 被跳过） |

### 2.2 页面 / 生成器

| 项 | 说明 |
|----|------|
| 面板 | `partials/torrent_metadata_panel.html` — Recommended 理由下方折叠展示 |
| 展示优化 | 清理 UIndex 前缀；文件列表仅视频；summary 含 `5.5 GB · 3 files · Matches indexer` |
| **A-11** | swarm 体积 vs indexer 交叉验证（`size_match`） |
| **E-05 扩展** | `recommend_reason` 追加 swarm 体积验证句（与 A-10 peers 句并列） |
| IG Debug | `ig_debug._entries_for_torrent_metadata()` 登记 A-11 |

---

## 三、验收数据（2026-07-06）

| 指标 | 结果 |
|------|------|
| 全 published 测速槽 | **115** |
| metadata 写入 MySQL | **75**（`size_match=ok` 100%） |
| dist 含 torrent 面板 | **75**（`generate all` 后） |
| 无 metadata（dead swarm / timeout） | **40** |
| 全量重测耗时 | ~32 min（5 workers · `--timeout 120`） |
| 报告 | [speedtest-retest-no-refetch.json](../../../worklogs/2026-07-06/speedtest-retest-no-refetch.json) |
| SEO 门禁 | **13 pass / 0 fail**（generate 后复跑） |
| 回归槽 | BB S04E06 — 面板 + reason 含 swarm 5.5 GB 验证句 |

---

## 四、E-E-A-T 影响

| 维度 | 影响 |
|------|------|
| **Experience** | 测速流程产出可核对 swarm 结构，强化「实测非 indexer 复述」 |
| **Expertise** | 展示 file list / piece / size 交叉验证，体现 torrent 结构理解 |
| **Trust** | 去除 UIndex 垃圾路径；非视频文件折叠说明，避免 spam 观感 |
| **Authority** | 无直接变化（仍待 GSC） |

---

## 五、Info Gain 影响

| IG-ID | 变化 |
|-------|------|
| **A-11**（新） | Swarm 体积交叉验证 — 折叠面板 + summary 可爬 |
| **S-02 / E-05** | `recommend_reason` 首屏追加 swarm 验证句 — **+0.3~0.5 分** 量级补充 |
| **S-06** | 无算法变更；metadata 为 Phase 2 副产物 |

**定位：** A-11 为 S-06 测速的 **验证层**，非独立主关键词；价值在差异化与 E-E-A-T 背书，非新长尾流量。

---

## 六、标准运维路径（不重拉）

```bash
cd releasematch

# 1. 回填 metadata（全 published）
python scripts/speedtest_retest_no_refetch.py --write --workers 5 --timeout 120 \
  --report worklogs/$(date +%Y-%m-%d)/speedtest-retest-no-refetch.json

# 2. bake 进 dist
python -m workflow.run generate all
bash scripts/seo_c2_checklist.sh

# 3. 抽查
rg -l "rm-torrent-meta" portal/dist | wc -l   # 应 ≈ metadata 行数
python -m workflow.run generate page --page-id tv:1396:s04e06  # 回归槽
```

---

## 七、下一步

| 优先级 | 动作 |
|--------|------|
| P1 | 40 无 metadata 槽：`--timeout 180` 针对性重试或接受无面板 |
| P2 | `extracted_at` 人性化（「2h ago」） |
| P2 | TRACKER / 登记册维持 A-11 跟进 |
| P3 | mismatch 页 Trust 文案策略（当前 75 页全 ok） |
