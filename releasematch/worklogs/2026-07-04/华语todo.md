# 华语支持 Todo（2026-07-04 起）

> **状态快照：** cn 路由已落地 · PoC **4/5** · pipeline **4 页 published** · 庆余年已登记 `genuine_scarcity`  
> **关联：** [11-CN华语影视资源方案.md](../../docs/11-CN华语影视资源方案.md) · [12-日常运营执行手册.md](../../docs/12-日常运营执行手册.md) §九 · [今日验收清单.md](./今日验收清单.md) 块 F

---

## 一、已完成 ✅

| # | 项 | 说明 |
|---|-----|------|
| H1 | `cn` 路由 + DMHy 直连 | `asia_region.py` · `dmhy_client.py` · `fetch_service.py` |
| H2 | Jackett API Key 同步 | VPS `172.237.11.232` · `accounts.local.json` |
| H3 | TMDB ID 修正 | 97113 三体 · 64197 琅琊榜 · 90761 陈情令 · 535167 流浪地球 |
| H4 | 亚洲 Jackett 文本搜索 | 跳过 tvdb 误匹配 · `build_cn_jackett_queries` |
| H5 | 整季 Complete 包（真人剧） | `matches_cn_season_pack` → 琅琊榜 TPB Complete ✅ |
| H6 | 华语 Jackett 扩展 | **dmhy / mikan / acgrip** · `configure_jackett_cn_indexers.sh` |
| H7 | 华语专用探测 | `cn_sources` 配置 · `scripts/cn_probe_sources.py` |
| H8 | Nyaa 动漫区 | `nyaa_anime` c=1_0 · 国漫补充 |
| H9 | PoC 报告 | [cn-dmhy-poc.json](./cn-dmhy-poc.json) **4/5** · [cn-sources-probe-socks-retest-v2.json](./cn-sources-probe-socks-retest-v2.json) **1/4** |
| H10 | 国漫全集包 → S01E01 | `matches_cn_episode_in_pack` · 三体 **8 条**（mikan） |
| H11 | 庆余年稀缺槽登记 | `tv:95842:s01e01` → `genuine_scarcity` · active **18** |
| H13 | pipeline 华语 demo 入库 | 三体/琅琊榜/陈情令/流浪地球 **published**（庆余年 thin 1 magnet） |

---

## 二、进行中 🔧

| # | 项 | 优先级 | 下一步 |
|---|-----|--------|--------|
| H12 | **VPS 侧 DMHy 拉取** | P1 | SSH SOCKS 隧道已验证 ✅ · `scripts/test_dmhy_via_socks.sh` |

---

## 三、待办 📋

| # | 项 | 优先级 | 说明 |
|---|-----|--------|------|
| H14 | `cn_probe_sources` 加速 | P2 | DMHy unreachable 快速跳过 |
| H19 | 华语季集命名 | ✅ | 搜索/过滤优先「第N集/[01]/全集」，S01E01 仅兜底 |
| H15 | acgrip 误匹配过滤 | P2 | 咒术回战误命中收紧 |
| H16 | CLI 文档 cn 段 | P2 | `06-run-cli` 补充 |
| H17 | 文档 §十 T1 闭合 | P2 | 更新 `11-CN` 排期 |
| H18 | 私有 PT（M-Team/U2） | P3 | Phase 3+ |

---

## 四、探测结论（勿忘）

| 内容类型 | 华语原生源 | 国际源（cn_tv 后半） |
|----------|------------|----------------------|
| 国漫（三体） | dmhy ✅ mikan ✅ | — |
| 真人剧 S01E01 | ❌ 普遍无 | TPB Complete ✅（琅琊榜） |
| 庆余年 S01E01 | ❌ | ❌（S02 部分集存在） |

**产品策略：** 华语页 metric = Recommended + 平台源标识 + 稀缺叙事，非 magnet 条数。

---

## 五、命令备忘

```bash
# 仅测华语源（不含 TPB/1337x）
python scripts/cn_probe_sources.py \
  --slots-json worklogs/2026-07-04/cn-sources-test-slots.json \
  --report worklogs/2026-07-04/cn-sources-probe.json

# VPS 低延迟探测
ssh root@172.237.11.232 'python3 /tmp/cn_probe_sources_vps.py YOUR_API_KEY'

# 全 pipeline PoC（含国际源）
python scripts/cn_poc_fetch.py --force --report worklogs/2026-07-04/cn-dmhy-poc.json

# 华语槽入库 + 生成（H13）
python -m workflow.run pipeline batch \
  --slots-json worklogs/2026-07-04/cn-benchmark-slots.json --fetch

# DMHy 经 SSH SOCKS 隧道测试（H12）
bash scripts/start_ssh_socks_tunnel.sh
bash scripts/test_dmhy_via_socks.sh
export TORRENT_PROXY=socks5h://127.0.0.1:1080
```

---

## 六、验收目标（华语 Phase 1 闭合）

- [x] H10 三体 S01E01：国漫 `01-15 Fin` / `1~15 全集` 槽位映射（slot_filter 单元测试 ✅）
- [x] H11 庆余年写入稀缺槽 registry（`genuine_scarcity` · [failed-slots-registry.json](../failed-slots-registry.json) active=18）
- [x] H13 ≥3 华语 demo 页 `published`（三体 8 · 琅琊榜 3 · 陈情令 2 · 流浪地球 16 magnet）
- [x] H12 SSH SOCKS 隧道 + DMHy 测试（`test_dmhy_via_socks.sh` · base32 infohash 修复）
- [ ] Git commit 华语代码（不含 `*.local.json`）
