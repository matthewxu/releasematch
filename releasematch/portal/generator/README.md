# 页面生成器（T3）

> **路径：** `releasematch/portal/generator/`  
> **优先级：** **T3**（工具轨 Week 7）— **阻塞 C1 验证集**  
> **方案：** [04-方案全景分析与优先级重评.md](../../download-resources/04-方案全景分析与优先级重评.md) §4.2 T3

---

## 职责

将「槽位 + D1 数据 + IG 引擎输出」转换为一页静态 HTML，供 CF Pages 部署。

```
输入：
  tmdb_id, season?, episode?
  ← workflow/torrent_sources/（magnet 列表）
  ← workflow/recommended/scorer.py（Recommended + reason）
  ← workflow/torrent_sources/speedtest/（测速摘要，T2 后）
  ← Group DB / 编码 P1 / 跨源 badge（T1）

输出：
  portal/dist/breaking-bad/s4e6/index.html
  （magnet ≥ 2 才生成 index 页，否则 skip 或 noindex 占位）
```

---

## 与内容轨的关系

| 阶段 | 动作 |
|------|------|
| T3 完成 | 生成器可对任意槽位出页 |
| **C1** | 生成器 batch 产出 **20 页验证集** + 人工 QA |
| **C2** | 将 C1 产出物提交 sitemap / GSC |
| **C4** | 生成器 batch +100 / +200 规模扩展 |

**页面生成器是工具；验证集与规模页都是它的 batch 运行结果。**

---

## 待实现（R0 脚手架阶段占位）

- [ ] `generate_one.py` — 单槽位 CLI
- [ ] `generate_batch.py` — 读 `priority/queue_builder.py` 队列
- [ ] Jinja2 / 纯字符串模板渲染
- [ ] 薄页门禁与 canonical 注入
