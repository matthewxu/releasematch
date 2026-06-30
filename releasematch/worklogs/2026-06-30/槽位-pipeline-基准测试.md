# 多槽位 Pipeline → 页面生成 基准测试

> **日期：** 2026-06-30（第二轮，最新策略）  
> **命令：** `TORRENT_PROXY=socks5h://127.0.0.1:1080 python scripts/benchmark_slots_pipeline.py --force`  
> **原始数据：** [slot-pipeline-benchmark.json](./slot-pipeline-benchmark.json)

---

## 测试环境

| 项 | 值 |
|----|-----|
| 存储后端 | MySQL `releasematch` @ 127.0.0.1 |
| Jackett | 日本 VPS `http://104.105.140.11:9117` |
| 剧集 indexer | **thepiratebay + nyaasi**（已移除 1337x / torrentgalaxyclone / FlareSolverr） |
| Nyaa 回退 | **SSH SOCKS** `socks5h://127.0.0.1:1080`（`ssh -D`） |
| 模式 | `pipeline slot --mode live --fetch` + `generate page` |
| 缓存 | `--force`（冷拉取） |
| 开始 | 2026-06-30T16:03:35Z |
| 结束 | 2026-06-30T16:12:02Z |
| 总 wall | **507.0s（约 8.5 分钟）** |

---

## 汇总

| 指标 | 本轮 | 上轮（14:31） | 变化 |
|------|------|---------------|------|
| 槽位数 | 7 | 7 | — |
| 成功 | **7** | 7 | — |
| 失败 | 0 | 0 | — |
| 总 wall | **507s** | 807s | **-37%** |
| 剧集平均 pipeline | **~84s / 槽** | ~133s / 槽 | **-37%** |
| 电影 pipeline | **4.5s** | 6.6s | -32% |
| HTML 生成 | ~50ms / 页 | ~35ms / 页 | 可忽略 |

---

## 各槽位明细

| 槽位 | page_id | pipeline | generate | **total** | magnets | 跨源 | 上轮 total |
|------|---------|----------|----------|-----------|---------|------|------------|
| BB S04E01 | tv:1396:s04e01 | 121.9s | 0.06s | **122.0s** | 14 | 1/3 | 131.5s |
| BB S04E02 | tv:1396:s04e02 | 69.9s | 0.05s | **70.0s** | 20 | 1/3 | 142.2s |
| BB S04E04 | tv:1396:s04e04 | 91.1s | 0.05s | **91.1s** | 14 | 2/3 | 131.5s |
| BB S04E06 | tv:1396:s04e06 | 72.0s | 0.05s | **72.1s** | 12 | 1/3 | 130.5s |
| BB S04E07 | tv:1396:s04e07 | 76.1s | 0.05s | **76.2s** | 14 | 1/3 | 132.5s |
| BB S04E08 | tv:1396:s04e08 | 71.1s | 0.05s | **71.2s** | 12 | 1/3 | 132.6s |
| Inception | movie:27205 | 4.5s | 0.03s | **4.5s** | 3 | 1/2 | 6.6s |

**条数对比：** magnet 数量与上轮基本一致（12~20 条/集），说明去掉 CF 源后质量未降。

---

## 结论

1. **最新策略显著提速**：7 槽冷拉取从 **13.5 分钟 → 8.5 分钟**（-37%），主要因移除 1337x/TorrentGalaxy + FlareSolverr 慢路径。
2. **剧集单槽约 70~92s**（首槽 S04E01 仍偏慢 122s，可能含 Nyaa 直连超时 + SOCKS 回退冷启动）。
3. **过滤后条数稳定**：BB 各集 12~20 条，与上轮相当。
4. **电影极快**：Inception 4.5s（YTS 直连）。
5. **批补估算**：6 集 + 1 电影冷拉取 ≈ **8.5 分钟**；命中缓存或无 `--force` 时更快。

---

## 复现

```bash
# 1. 先开 SSH SOCKS 隧道
bash scripts/start_ssh_socks_tunnel.sh

# 2. 跑基准
cd releasematch
export TORRENT_PROXY=socks5h://127.0.0.1:1080
python scripts/benchmark_slots_pipeline.py --force
```

---

## 关联

- 脚本：`scripts/benchmark_slots_pipeline.py`
- 日韩/代理：`docs/nyaa-proxy-asia.md`
- 稳定性：`docs/jackett-stability.md`
