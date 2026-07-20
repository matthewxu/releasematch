# Swarm 解析验证与 metadata 生成（2026-07-20）

## 做了什么

1. `scripts/torrent_metadata_selftest.py` — **OK**（`compare_torrent_sizes` / `pick_primary_video_file`）
2. 存量 `torrent_metadata` size_match 重算 — **95/95 ok**
3. 缺 metadata 槽 force 回填（20）→ 报告 `swarm-metadata-backfill.json`
4. `python -m workflow.run generate all` — 成功；面板 bake
5. 修复 `speedtest_retest_no_refetch.py --generate-all` 错误模块路径（`portal.generator.run` → `workflow.run`）

## 结果

| 项 | 值 |
|----|----|
| published + Recommended | 112 |
| 已有 torrent_metadata | 95 |
| 仍缺 | 17（多因 timeout / 无 peer / 未拿到 metadata） |
| size_match | 全部 ok（重算一致） |
| dist `rm-torrent-meta` 面板 | 见 acceptance JSON |

## 产物

- `worklogs/2026-07-20/swarm-metadata-backfill.json`
- `worklogs/2026-07-20/swarm-metadata-acceptance.json`
- `worklogs/2026-07-20/generate-all-after-swarm-meta.log`
