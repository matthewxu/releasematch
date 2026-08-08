# 基础设施：www → apex 301 重定向

> **版本：** v1.0  
> **落地日期：** 2026-08-08  
> **关联 TODO：** [reviews/2026-08-08/03-策略与TODO.md](./reviews/2026-08-08/03-策略与TODO.md) **T-01**  
> **canonical 权威：** `RM_SITE_ORIGIN` = `https://releasematch.com`（**非 www**）

---

## 一、背景

| 项 | 说明 |
|----|------|
| **问题** | `www.releasematch.com` 与 `releasematch.com` 均返回 200，Google 标记「备用页 / 已抓取未编入」 |
| **站点 canonical** | 生成器、sitemap、robots.txt 均指向 `https://releasematch.com` |
| **修复** | Cloudflare **Page Rule** 全站 301：www → apex |

---

## 二、Cloudflare Page Rule（已部署）

| 字段 | 值 |
|------|-----|
| **如果 URL 匹配** | `www.releasematch.com/*` |
| **然后** | Forwarding URL · **301 Permanent Redirect** |
| **目标** | `https://releasematch.com/$1` |
| **规则顺序** | Page Rules 列表 **最上** |

`$1` 为第一个 `*` 捕获的路径；query string 默认保留。

---

## 三、与代码 / 配置的一致性

| 组件 | 应使用的域名 | 文件 |
|------|--------------|------|
| `RM_SITE_ORIGIN` | `https://releasematch.com` | `.env` · `config.env.example` |
| `<link rel="canonical">` | 同上 + path | 生成器 `base.html` |
| `sitemap.xml` `<loc>` | 同上 | `portal/generator/sitemap.py` |
| `robots.txt` Sitemap | `https://releasematch.com/sitemap.xml` | `portal/static/robots.txt` |
| **公网探针 / curl 验收** | **`https://releasematch.com`**（apex） | 上线检查清单 |
| **GSC 主属性（建议）** | `https://releasematch.com/` | Search Console |

**不要** 将 `RM_SITE_ORIGIN` 改为 www；**不要** 在 dist 内做 host 级 redirect（应在 Cloudflare Zone 层）。

---

## 四、验收命令

```bash
# www 须 301
curl -sI "https://www.releasematch.com/" | grep -iE '^(HTTP|location:)'
curl -sI "https://www.releasematch.com/minions-monsters/" | grep -iE '^(HTTP|location:)'

# apex 须 200
curl -sI "https://releasematch.com/" | head -1

# 可选：脚本门禁（需网络）
python scripts/seo_c2_checklist.py --check-live-www
```

**期望：**

```
HTTP/2 301
location: https://releasematch.com/...
```

---

## 五、GSC 说明

| 项 | 说明 |
|----|------|
| 历史属性 | 曾用 `https://www.releasematch.com/` 验证；导出 CSV 中 URL 为 www 属正常 |
| 301 后 | Google 合并信号到 apex；「备用页」应不再新增 |
| 建议 | 添加 apex 属性并提交 sitemap（见 T-07） |

---

## 六、回滚

删除或禁用 Cloudflare Page Rule `www.releasematch.com/*` → www 恢复 200（不推荐）。

---

## 七、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-08-08 | T-01 Page Rule 落地 + curl 验收 |
