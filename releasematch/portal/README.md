# ReleaseMatch Portal — 独立域名前端

> **路径：** `releasematch/portal/`  
> **部署：** Cloudflare Pages + Workers（**独立 CF 项目**，不与 subtitle-portal 共享）  
> **域名示例：** `releasematch.io`  
> **优先级：** C0（Trust 壳）→ **T3（页面生成器）** → C1（验证集 20 页）

---

## 双轨中的位置

| 轨道 | 阶段 | 本目录交付物 |
|------|------|-------------|
| **工具轨 T3** | Week 7 | `generator/` 槽位 → 静态 HTML |
| **工具轨 T3** | Week 7 | D1 sync Workers API |
| **内容轨 C0** | Week 7~8 | Trust 四页静态 HTML |
| **内容轨 C1** | Week 8~9 | 生成器首次 batch（20 页验证集） |
| **内容轨 C2** | Week 9~10 | sitemap + GSC（**工具就绪后才提交**） |

**原则：先完成 T3 生成器，再用 C1 跑验证集；禁止手工堆 50 页后再补 IG。**

---

## 目标目录结构

```
portal/
├── README.md                 # 本文件
├── generator/                # T3：页面生成器（待建）
│   └── README.md
├── trust/                    # C0：About / DMCA / Privacy / How It Works
├── templates/                # 单集页 / 电影页 HTML 模板
├── workers/                  # D1 API + sync
└── static/                   # robots.txt、sitemap 骨架
```

---

## 目标 URL 结构

```
releasematch.io/                              首页
releasematch.io/breaking-bad/                 剧集 hub
releasematch.io/breaking-bad/s4e6/            单集（L3）
releasematch.io/inception-2010/               电影页
releasematch.io/how-matching-works/           Trust / 链接诱饵（T4-2）
releasematch.io/dmca/                         DMCA
releasematch.io/about/                        About
/api/v1/sources?tmdb=&s=&e=                   Stremio API（T4）
```

---

## C0 交付清单（可与 T3 并行）

- [ ] CF Pages 项目初始化
- [ ] Trust 四页静态 HTML
- [ ] robots.txt / 404/410 模板
- [ ] **不提交 GSC**（等 C2）

## T3 交付清单（阻塞 C1）

- [ ] D1 binding + sync Worker
- [ ] `generator/`：读 D1 + recommended + 测速 → 静态 HTML
- [ ] 薄页门禁：magnet < 2 不生成 index 页
- [ ] 单集页模板 v1（Recommended + All Sources + 测速摘要）

---

## 跨站协同（仅 1 链）

字幕站单集页正文 → 链接到 `https://releasematch.io/{slug}/s{s}e{e}/`  
**禁止** sitewide 互链、相同模板换 Logo。
