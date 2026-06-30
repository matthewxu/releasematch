# ReleaseMatch — Release 导航站独立开发目录

> **版本：** v0.1.0  
> **创建日期：** 2026-06-29  
> **定位：** 影视下载 **Release 导航站** 的独立代码库根目录，与字幕主站（`subtitle-portal`）及字幕工作流（`tmdbpy/workflow/opensubtitles` 等）**完全隔离**  
> **方案文档：** [download-resources/](../download-resources/) · 优先级重评见 [04-方案全景分析与优先级重评.md](../download-resources/04-方案全景分析与优先级重评.md)

---

## 一、为什么独立目录

原规划将下载分支嵌入字幕站工作流（Step 4c、`subtitle-portal` 的 `/download/` 路由、`is_primary` 与字幕 Primary 对齐）。根据 **独立顶级域名 + Google 2026 Site Reputation Abuse 规避** 策略，Release 导航站改为单独开发：

| 原耦合点 | 独立后 |
|---------|--------|
| `tmdbpy/workflow/run.py` Step 4c | `releasematch/workflow/run.py` 自有总控 |
| `subtitle-portal` `/download/*` 路由 | `releasematch/portal/`（独立 CF Pages/Workers） |
| `subtitle_primary_release` 评分对齐 | `recommended/scorer.py` 本站规则引擎 |
| D1 扩展 subtitle-portal 表 | `schema/d1_download_resources.sql` 独立 D1 项目 |
| W002 字幕优先级队列 | `priority/queue_builder.py`（可选只读 TMDB MySQL） |

**字幕站仅保留：** 单集正文 **1 条** 出站链接 → Release 导航域（见 01 文档 §七）。

---

## 二、目录结构

```
releasematch/
├── README.md                          # 本文件
├── requirements.txt                   # Python 依赖
├── .gitignore
├── docs/
│   └── INDEX.md                       # 指向 download-resources 方案文档
├── worklogs/                          # 按日期存放的开发工作日志
│   ├── README.md                      # 命名规范与模板
│   └── YYYY-MM-DD/                    # 单日文件夹
├── schema/
│   ├── mysql_schema.sql               # MySQL 本地测试（与 D1 对齐）
│   ├── mysql_seed_demo.sql            # MySQL 演示种子
│   ├── d1_schema.sql                  # Cloudflare D1 完整线上模型（7 表）
│   ├── d1_seed_demo.sql               # 设计演示页种子数据
│   ├── d1_models.py                   # D1 Python dataclass + 模板上下文
│   ├── d1_download_resources.sql      # 兼容入口（指向 d1_schema.sql）
│   └── mysql_download_inventory.sql   # 兼容入口（指向 mysql_schema.sql）
├── config.env.example                 # 环境变量模板（MySQL / D1 / 数据源）
├── scripts/
│   └── poc_phase0.ps1                 # 四源 PoC 验证（Phase 0）
├── workflow/                          # Python 数据与 IG 管道
│   ├── run.py                         # 总控 CLI（替代 tmdbpy Step 4c）
│   ├── config.py                      # 全局路径与环境变量
│   ├── torrent_sources/               # 多源 magnet 清单（核心）
│   ├── metadata/                      # TMDB external_ids 读取（解耦 W004）
│   ├── recommended/                   # Recommended Release 评分引擎
│   └── priority/                      # 批补优先级队列（解耦 W002）
├── portal/                            # 前端与 CF Workers（独立域）
│   ├── README.md
│   └── generator/                     # T3 页面生成器（待建）
└── extension/                         # 浏览器扩展（T4 阶段，占位）
    └── README.md
```

---

## 三、快速开始

```powershell
# 1. 进入目录并安装依赖
cd releasematch
.\scripts\setup_block_a.ps1
# 或手动：
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. 配置 Jackett Key（编辑 accounts.local.json 或设置 JACKETT_API_KEY）

# 3. Phase 0：验证四源连通性（Python，跨平台）
python scripts/poc_phase0.py
# 逐 Jackett indexer：python scripts/poc_jackett_indexers.py
# 海外 Jackett：见 docs/jackett-remote-linode.md

# 4. 查看工作流状态
python -m workflow.run status

# 5. 测试单集拉取（Breaking Bad S04E06）
python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6
```

---

## 四、开发优先级（T0~T5 工具轨 + C0~C4 内容轨）

> **策略：先工具、后内容。** 详见 [04-方案全景分析与优先级重评.md v1.1](../download-resources/04-方案全景分析与优先级重评.md)

### 工具轨 T（先做）

| 阶段 | 核心交付 | 目录 | 周期 |
|------|---------|------|------|
| **T0** | torrent_sources MVP + external_ids + PoC | `workflow/torrent_sources/`、`workflow/metadata/` | W1~2 |
| **T1** | Recommended Release + Group DB + 编码 P1 + 跨源验证 | `workflow/recommended/`、`workflow/torrent_sources/` | W3~5 |
| **T2** | 磁力测速 Phase 1 + seeders cron + D1 测速 API | `workflow/torrent_sources/speedtest/`（待建） | W6 |
| **T3** | D1 sync + **页面生成器** | `portal/generator/`（待建）、`schema/` | W7 |
| **T4** | Stremio 插件 → 浏览器扩展 | `extension/`、`portal/api/` | W10~ |
| **T5** | 测速 P2 + 编码 P2 + 日韩/趋势/API | — | M4+ |

### 内容轨 C（工具就绪后）

| 阶段 | 核心交付 | 说明 | 周期 |
|------|---------|------|------|
| **C0** | 域名 + Trust 四页 | 不提交 GSC | W7~8（与 T3 并行） |
| **C1** | 验证集 **20 页** | 生成器首次 batch + 人工 QA | W8~9 |
| **C2** | GSC + sitemap + URL Inspection | 前提：T1~T3 验收通过 | W9~10 |
| **C3** | 沙盒观察 | 不增页；可并行 T4 | M2~3 |
| **C4** | 规模扩展 | 收录率 ≥25% 后 +100/+200 批 | M4+ |

### 1 人全栈串行（摘要）

```
W1~2  T0    W3~5  T1    W6  T2    W7  T3 + C0
W8~9  C1    W9~10 C2    M2~3 C3 + T4    M4+ C4 + T5
```

**工具链闭环点：** T3 页面生成器完成 → 才开始 C1 验证集。

---

## 五、与字幕站的可选数据桥接

Release 导航站 **不依赖** 字幕站运行，但可 **只读** 复用 TMDB 元数据：

| 环境变量 | 说明 | 默认 |
|---------|------|------|
| `RM_MYSQL_HOST` | TMDB MySQL 主机 | `127.0.0.1` |
| `RM_MYSQL_DB` | 数据库名 | `test` |
| `RM_MYSQL_USER` | 用户名 | — |
| `RM_MYSQL_PASSWORD` | 密码 | — |
| `RM_TMDB_DATA_MODE` | `mysql` 或 `standalone` | `standalone` |

`standalone` 模式下使用 JSON 静态作品清单，无需连接字幕站数据库。

### Release 业务存储（MySQL 测试 → D1 生产）

| 环境变量 | 说明 | 默认 |
|---------|------|------|
| `RM_STORAGE_BACKEND` | `mysql`（本地）或 `d1`（生产） | `mysql` |
| `RM_RELEASE_MYSQL_DB` | Release 专用库 | `releasematch` |
| `RM_RELEASE_MYSQL_USER` | Release 库用户名 | — |

Quick Start 与总控 CLI 见 [docs/05-存储与部署配置.md](docs/05-存储与部署配置.md)；**命令详解**见 [docs/06-run-cli使用说明.md](docs/06-run-cli使用说明.md)；**部署 FAQ（D1 / Pages / Worker）**见 [docs/07-部署架构解疑.md](docs/07-部署架构解疑.md)。

```bash
cd releasematch
cp config.env.example .env   # 配置 RM_RELEASE_MYSQL_*
python -m workflow.run db init --seed
python -m workflow.run query page --page-id tv:1396:s04e06
```

---

## 六、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1.0 | 2026-06-29 | 初版：从字幕站解耦，建立独立目录与脚手架 |
| v0.2.0 | 2026-06-29 | 优先级改为 T0~T5 + C0~C4 双轨（先工具后内容） |
