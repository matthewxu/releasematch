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
├── 404.html                  # 404 模板
├── 410.html                  # DMCA 410 Gone
├── static/
│   ├── css/design-system.css # 设计系统
│   ├── js/site.js            # 轻量交互
│   └── robots.txt
├── trust/                    # C0：About / Contact / DMCA / Privacy / How It Works
├── generator/                # T3：页面生成器
│   └── templates/            # Jinja2 模板（base / episode / movie / show_hub）
├── workers/                  # D1 API + sync
└── dist/                     # T3 批量产出（generate all 写入；部署唯一内容源）
```

> **勿在 `portal/` 根下维护手写内容页**（如旧版 `breaking-bad/s4e6/index.html`）。预览用 `serve` 或 `dist/`。

---

## 页面设计（v0.1 设计稿）

### 设计原则

| 原则 | 说明 |
|------|------|
| **IG 优先** | 视觉层级：Recommended Release &gt; All Sources &gt; TMDB 侧栏 |
| **深色专业** | 深蓝黑底 + 绿色推荐强调，传达「工具/数据」而非「资源站」 |
| **移动适配** | 表格响应式卡片化、顶栏折叠菜单 |
| **E-E-A-T** | Trust 四页、DMCA、nofollow magnet、不托管声明 |

### 页面类型与路径

| 类型 | URL 示例 | 来源 |
|------|----------|------|
| 首页 | `/` | `generate all` → `dist/index.html` 或 `serve`（MySQL） |
| 剧集 Hub | `/breaking-bad/` | 生成器 `show_hub.html` |
| **单集 L3（核心）** | `/breaking-bad/s4e6/` | 生成器 `episode.html` |
| 电影 | `/inception-2010/` | 生成器 `movie.html` |
| Trust | `/trust/about/`、`/trust/speed-and-grab/` 等 | `generate all` → `dist/trust/*/index.html` |
| 404 / 410 | `/404.html` | 静态壳 |

### 单集页模块顺序（对齐 01 文档 §5.5）

1. 面包屑 + Hero（季集元信息、跨源 badge）
2. 测速摘要条（T2）
3. **Recommended Release 卡片**（最高 IG）
4. All Sources 对比表
5. 集间 Prev/Next 导航
6. 侧栏：TMDB 海报、Watch On、字幕单链

### 本地预览

**方式 A — 开发服（推荐，实时读 MySQL）：**

```bash
cd releasematch
source .venv/bin/activate   # 或 pip install -r requirements.txt
python -m workflow.run db init --seed   # 首次
python -m workflow.run serve --port 8080
```

浏览器打开：

- `http://127.0.0.1:8080/breaking-bad/s4e6/` — 单集（读 `download_resources`）
- `http://127.0.0.1:8080/breaking-bad/` — Hub
- `http://127.0.0.1:8080/inception-2010/` — 电影

**方式 B — 生成静态 HTML 到 `portal/dist/`（部署同源）：**

```bash
# 开启双语切换时建议显式设置（默认 false 为固定英文）
RM_SITE_I18N_ENABLED=true python -m workflow.run generate all

# 推荐：自动同步 static 壳 + 内联 i18n bootstrap
python -m workflow.run serve-static --port 8080
```

`generate all` 末尾会调用 `static_shell.sync_static_shell()`，将 `portal/static/`、`404.html`、`410.html` 复制到 `dist/`。  
若直接用 `cd portal/dist && python -m http.server`，须确认 `dist/static/` 已存在；否则 `/static/js/site.js` 404，顶栏 EN/中文 按钮无效（HTML 内已含内联 bootstrap 时可切换，但样式与增强交互仍依赖 static）。

**方式 B 验收双语：** 浏览器打开 `http://127.0.0.1:8080/breaking-bad/s4e6/`，点击顶栏「中文」，导航、Hero、Footer 应切换；Trust 说明页 `/trust/speed-and-grab/` 正文亦随切换变化。

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
- [x] Trust 五页静态 HTML（`trust/*/index.html`）
- [x] 单集 / 电影 / Hub — **仅经生成器产出**（T-10 已清理手写 demo）
- [x] robots.txt 占位
- [x] 404 模板
- [ ] CF Pages 项目初始化
- [ ] **不提交 GSC**（等 C2）

## T3 交付清单（阻塞 C1）

- [x] Jinja2 模板骨架（`generator/templates/`）
- [ ] D1 binding + sync Worker（schema 见 `../../schema/d1_schema.sql`）
- [ ] `generator/generate_one.py` — 读 D1 + scorer → HTML
- [ ] 薄页门禁：magnet < 2 不生成 index 页
- [ ] 单集页模板 v1 与演示页对齐

---

## 跨站协同（仅 1 链）

字幕站单集页正文 → 链接到 `https://releasematch.io/{slug}/s{s}e{e}/`  
**禁止** sitewide 互链、相同模板换 Logo。
