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
├── index.html                # 首页（设计演示）
├── 404.html                  # 404 模板
├── breaking-bad/             # 剧集 Hub + 单集演示
├── inception-2010/           # 电影页演示
├── static/
│   ├── css/design-system.css # 设计系统
│   ├── js/site.js            # 轻量交互
│   └── robots.txt
├── trust/                    # C0：About / DMCA / Privacy / How It Works
├── generator/                # T3：页面生成器
│   └── templates/            # Jinja2 模板（base / episode / movie / show_hub）
├── templates/                # （预留）与 generator 同步的静态参考
├── workers/                  # D1 API + sync
└── dist/                     # T3 批量产出目录（生成器写入）
```

---

## 页面设计（v0.1 设计稿）

### 设计原则

| 原则 | 说明 |
|------|------|
| **IG 优先** | 视觉层级：Recommended Release &gt; All Sources &gt; TMDB 侧栏 |
| **深色专业** | 深蓝黑底 + 绿色推荐强调，传达「工具/数据」而非「资源站」 |
| **移动适配** | 表格响应式卡片化、顶栏折叠菜单 |
| **E-E-A-T** | Trust 四页、DMCA、nofollow magnet、不托管声明 |

### 页面类型与演示路径

| 类型 | URL 演示 | Jinja2 模板 |
|------|----------|-------------|
| 首页 | `/index.html` | — |
| 剧集 Hub | `/breaking-bad/` | `show_hub.html` |
| **单集 L3（核心）** | `/breaking-bad/s4e6/` | `episode.html` |
| 电影 | `/inception-2010/` | `movie.html` |
| Trust | `/trust/about/` 等 | 静态 prose |
| 404 | `/404.html` | — |

### 单集页模块顺序（对齐 01 文档 §5.5）

1. 面包屑 + Hero（季集元信息、跨源 badge）
2. 测速摘要条（T2）
3. **Recommended Release 卡片**（最高 IG）
4. All Sources 对比表
5. 集间 Prev/Next 导航
6. 侧栏：TMDB 海报、Watch On、字幕单链

### 本地预览

在 `portal/` 目录启动静态服务器：

```bash
cd releasematch/portal
python -m http.server 8080
```

浏览器打开 `http://localhost:8080/breaking-bad/s4e6/` 查看单集页设计。

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

- [x] 设计系统 `static/css/design-system.css`
- [x] Trust 四页静态 HTML（`trust/*/index.html`）
- [x] 单集 / 电影 / Hub 设计演示页
- [x] robots.txt 占位
- [x] 404 模板
- [ ] CF Pages 项目初始化
- [ ] **不提交 GSC**（等 C2）

## T3 交付清单（阻塞 C1）

- [x] Jinja2 模板骨架（`generator/templates/`）
- [ ] D1 binding + sync Worker
- [ ] `generator/generate_one.py` — 读 D1 + scorer → HTML
- [ ] 薄页门禁：magnet < 2 不生成 index 页
- [ ] 单集页模板 v1 与演示页对齐

---

## 跨站协同（仅 1 链）

字幕站单集页正文 → 链接到 `https://releasematch.io/{slug}/s{s}e{e}/`  
**禁止** sitewide 互链、相同模板换 Logo。
