# GSC 索引复盘 — 2026-08-08

> **复盘日期：** 2026-08-08  
> **GSC 属性：** `https://www.releasematch.com/`  
> **数据来源：** GSC → 网页 → 索引状态（当时快照）  
> **关联策略：** D2 Hub noindex · D3 sitemap ≤30 内容页 · 薄页门禁 `is_indexable()`

---

## 〇、执行摘要

GSC 网页菜单显示：**已编入索引 58 · 未编入 30**。其中 30 个未编入里 **26 个（87%）为站点主动 noindex**，属于 intentional 设计而非 SEO 事故。内容页 indexable 收录率约 **44%**，已超过 C3 目标（>25%）。**www → apex 301 已于 2026-08-08 修复**；**catalog 分页 page≥2 noindex 已于 2026-08-08 落地**（待 deploy 后 GSC 复验）。

**索引层总评：C2 阶段执行到位，健康度 B+。**

---

## 一、GSC 索引数据

| 状态 | 数量 | 占已知 URL 比 | 说明 |
|------|------|---------------|------|
| **已编入索引** | 58 | 65.9% | 含首页、Trust、内容页 |
| **未编入索引** | 30 | 34.1% | 需分类解读 |
| └ 被 noindex 标记排除 | 26 | 29.5% | **符合设计** |
| └ 备用网页（有适当规范标记） | 2 | 2.3% | www/非 www |
| └ 已抓取 - 尚未编入索引 | 2 | 2.3% | 质量门槛 |
| **已知 URL 合计** | 88 | 100% | — |

---

## 二、与站点策略对照

### 2.1 已编入索引：58 — 超出 sitemap，内链有效

| 项 | 数值 | 说明 |
|----|------|------|
| sitemap URL 数 | **37** | 首页 1 + Trust 6 + 内容页 30（D3） |
| GSC 已索引 | **58** | 比 sitemap 多 ~21 页 |
| indexable 内容页（库内估算） | ~117 | `magnet≥2` + 有 Recommended |
| 已索引内容页估算 | ~51 | 58 − 首页 − Trust |
| **内容页收录率** | **~44%** | 超 C3 门槛 25% |

Google 通过首页 catalog、Hub 内链等发现了 sitemap 外的 indexable 页，说明 **内链结构有效**。

**代码依据：**

- sitemap 上限：`portal/generator/sitemap_config.json` → `max_content_urls: 30`
- 收录门禁：`schema/d1_models.py` → `MediaPage.is_indexable()`

### 2.2 noindex 排除：26 — 三门禁生效

| 类型 | 策略 | 实现 |
|------|------|------|
| **剧集 Hub** | D2：`noindex,follow` | `show_hub.html` |
| **薄页** | `magnet_count < 2` | `page_status=thin`, `robots_noindex=1` |
| **无 Recommended** | 无 IG 内容不 index | `robots_noindex=1` |

GSC 正确识别并排除了这些页面，**robots 信号与生成器一致**。

### 2.3 规范备用页：2 — www / 非 www 双活 → **已修复**

| 检测项 | 复盘时 | 2026-08-08 修复后 |
|--------|--------|-------------------|
| `https://www.releasematch.com/` | HTTP 200 | **301** → apex |
| `https://releasematch.com/` | HTTP 200 | HTTP 200 |
| 修复 | — | T-01 Page Rule |

Google 此前爬取 www 变体后因 canonical 指向非 www 标记为「备用页」。**T-01 301 后** www 不再独立返回 200。

### 2.4 已抓取未编入：2 — **T-03：根因 www 重复**

| 项 | 说明 |
|----|------|
| **GSC 数量** | 2 页（与备用页同属 www 重复信号） |
| **T-03 结论** | URL Inspection / 索引归因：**非内容质量 issue**，系 www 与 apex 双 URL + canonical 指向 apex |
| **修复** | T-01 全站 301；无需改页面 IG |
| **复验** | 2026-09 复盘对照 GSC「已抓取未编入」是否归零 |

---

## 三、规模对照

| 来源 | 数量 | 说明 |
|------|------|------|
| 首页 catalog 展示 | 108 entries | 2026-08-08 线上 |
| GSC 已知 URL | 88 | 部分页尚未进入 GSC |
| 库内 indexable | ~117 | 运营手册基线 |
| sitemap 提交 | 37 | D3 冷启动 |

约 **20+ 页面** 可能尚未被 GSC 完整发现或仍在爬取队列。

---

## 四、综合评分（索引层）

| 维度 | 评分 | 说明 |
|------|------|------|
| **技术 SEO** | A- | canonical、Schema、OG、robots 门禁、sitemap 已落地 |
| **索引健康度** | B+ | intentional noindex 占比高；真正异常仅 2 页 |
| **收录扩张** | B | 44% indexable 已收录，超 C3 门槛 |
| **域名规范** | B | T-01 301 已部署；待 GSC 复验 |

---

## 五、索引层问题清单

| # | 问题 | 优先级 | 状态 |
|---|------|--------|------|
| I-01 | www / 非 www 未 301 | P1 | ✅ 2026-08-08 Page Rule |
| I-02 | catalog 分页 `/catalog/page/N/` 可被索引 | P1 | ✅ 2026-08-08 page≥2 noindex |
| I-03 | sitemap 仅 37 URL vs ~117 indexable | P2 | ✅ 策略内（D3） |
| I-04 | 2 页「已抓取未编入」 | P2 | ✅ T-03：www 重复；T-01 301 |

详见 [03-策略与TODO.md](./03-策略与TODO.md)。

---

## 六、关联命令

```bash
# 本地 SEO 门禁
python scripts/seo_c2_checklist.py

# 重算 sitemap
python -m workflow.run generate all

# 查看 indexable 页
python -m workflow.run query page --page-id tv:1396:s04e06
```

---

## 七、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-08-08 | 首次 GSC 索引复盘 |
