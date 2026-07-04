# SEO 迭代记录模板

> **用途：** 复制本文件到 `iterations/YYYY-MM-DD-<主题>.md` 记录单次 SEO 专项迭代  
> **看板：** 完成后更新 [TRACKER-E-E-A-T-InfoGain.md](../TRACKER-E-E-A-T-InfoGain.md) §五迭代日志

---

## 元信息

| 项 | 值 |
|----|-----|
| **日期** | YYYY-MM-DD |
| **阶段** | C2 / C3 / … |
| **作者** | |
| **关联 PR / Commit** | |
| **关联 worklog** | [worklogs/YYYY-MM-DD/…](../../worklogs/) |

---

## 一、背景

<!-- 为什么要做这次 SEO 迭代？触发条件（评估结论、GSC 数据、门禁失败等） -->

---

## 二、变更内容

<!-- 具体改了什么：模板、生成器、Trust 页、scorer、cron 等 -->

| 文件 / 模块 | 变更 |
|-------------|------|
| | |

---

## 三、E-E-A-T 影响

| 要素 | 影响 | 说明 |
|------|------|------|
| Experience | ↑ / → / ↓ | |
| Expertise | ↑ / → / ↓ | |
| Authoritativeness | ↑ / → / ↓ | |
| Trustworthiness | ↑ / → / ↓ | |

---

## 四、Info Gain 影响

| IG-ID | 变更前 | 变更后 | 页面估分变化 |
|-------|--------|--------|-------------|
| | | | |

**抽查页面（RM_SHOW_IG_DEBUG=1）：**

- 槽位 1：
- 槽位 2：

---

## 五、技术 SEO 影响

<!-- sitemap、Schema、robots、lang 等；是否跑过 seo_c2_checklist -->

```bash
python scripts/seo_c2_checklist.py
# 结果：
```

---

## 六、验收

- [ ] 生成器 `generate all` 通过
- [ ] seo_c2_checklist 通过
- [ ] TRACKER 看板已更新
- [ ] （C2 后）GSC URL Inspection

---

## 七、下一步

<!-- 遗留项、下一迭代依赖 -->

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | YYYY-MM-DD | 初稿 |
