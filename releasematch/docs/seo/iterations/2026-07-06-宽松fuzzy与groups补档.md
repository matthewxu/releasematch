# 宽松 fuzzy 三档 · groups.yaml +12 · 质量向基线刷新

> **日期：** 2026-07-06  
> **Worklog：** [fuzzy-relaxed-and-groups-before-after.json](../../worklogs/2026-07-06/fuzzy-relaxed-and-groups-before-after.json)  
> **关联：** [TRACKER](../TRACKER-E-E-A-T-InfoGain.md)

---

## 背景

严格档 fuzzy（group+resolution+source+codec）在全站重拉后 **improved=0**。质量向 IG 仍 5~7：cross≥2 仅 4/110，L4 Rec 24 页。

---

## 变更

| 模块 | 变更 |
|------|------|
| `cross_source.py` | fuzzy 三档：`strict` → `no_group` → `slot_resolution`；分子钳制 ≤ 本页源族数 |
| `pipeline.py` | fuzzy 重算写回 `cross_source_page_count=after_max`（修复旧值覆盖） |
| `fetch_service.py` | fuzzy 后抬升页面 cross 分子 |
| `release_parser.py` | `[GROUP]` 前缀 · `...Group` 尾缀解析 |
| `groups.yaml` | +12 组（EMBER/HHWEB/HYBRiS/LAZY/NYHD/OFT/GRACE/HiggsBoson/d3g/Hon3y/YG/SuccessfulCrab） |

---

## 前后对比

| 指标 | 前 | 后 |
|------|----|----|
| cross≥2（indexable+Rec） | 4/110 | **8/110** |
| 质量向 7+ 代理 | 3 | **7** |
| L4 Rec | 24 | **12** |
| Debug 8~9 | 109 | 109 |
| fuzzy improved_count | 0（严格档） | **5** |

---

## 误匹配风险（设计取舍）

| 档位 | 风险 |
|------|------|
| `no_group` | 同集同规格不同压制组可能对齐 |
| `slot_resolution` | 可能合并同分辨率 WEB-DL 与 HDTV |

分子已钳制在本页实际源族数内，不会超出真实 indexer 命中数。

---

## 验收

- [x] `recompute_cross_source_fuzzy.py --all-published --rescore-after` → improved=5
- [x] `generate all` dist 重生成
- [x] TRACKER §一基线刷新

---

## 下一步

1. `release_parser` 处理空组名 / 华语无 `-Group` 标题（剩余 12 L4 Rec）
2. indexer 间 release 重叠提升（非纯算法可补）
