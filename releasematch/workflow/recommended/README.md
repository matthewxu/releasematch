# Recommended Release 评分引擎

> **权威文档：** [docs/IG信息登记册.md §6](../../docs/IG信息登记册.md#六release-group-信誉s-05--a-06--计算逻辑与实现进度)

## 模块

| 文件 | 职责 |
|------|------|
| `scorer.py` | `rank_items()` · 剧集 v1.1 / 电影 v1.2 |
| `groups_registry.py` | `groups.yaml` 查表 · L0~L4 |
| `data/groups.yaml` | 压制组信誉档 |

## 快速参考

```python
from workflow.recommended.scorer import rank_items

# 剧集（默认）
ranked = rank_items(items, media_kind="tv")

# 电影
ranked = rank_items(items, media_kind="movie")
```

## 不重拉重算

```python
from workflow.storage.pipeline import rescore_published_pages

rescore_published_pages(media_kind="movie")
```
