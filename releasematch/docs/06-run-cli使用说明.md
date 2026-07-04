# 06 — workflow.run 总控 CLI 使用说明

> **版本：** v0.3（2026-07-04）  
> **入口文件：** `workflow/run.py`  
> **调用方式：** `python -m workflow.run <子命令> [参数]`  
> **前置：** 在 `releasematch/` 目录下执行；配置见 [05-存储与部署配置.md](./05-存储与部署配置.md)  
> **关联文档：** [12-日常运营执行手册.md](./12-日常运营执行手册.md) · [VPS迁移与部署.md](./VPS迁移与部署.md) · [11-CN华语影视资源方案.md](./11-CN华语影视资源方案.md) · [nyaa-proxy-asia.md](./nyaa-proxy-asia.md) · [worklogs SEO §六](../worklogs/2026-07-03/页面SEO分析与优化方向.md)

---

## 一、基本用法

### 1.1 进入项目目录

```bash
cd releasematch
```

### 1.2 配置环境变量

```bash
cp config.env.example .env
# 编辑 .env，至少设置 RM_RELEASE_MYSQL_USER / RM_RELEASE_MYSQL_PASSWORD
# 批量扩槽建议额外配置 RM_TMDB_API_KEY（见 §五）
```

工作流启动时会**自动读取** `.env`（不覆盖已在 shell 中 `export` 的变量）。

torrent 拉取还需配置 `workflow/torrent_sources/accounts.local.json`（从 `accounts.example.json` 复制，填入 Jackett API Key 等）。

### 1.3 查看帮助

帮助采用 **层级递进**：在「当前要执行的那一层命令」后加 `-h` 或 `--help`。

| 想看什么 | 命令 |
|---------|------|
| 全部顶层子命令 | `python -m workflow.run -h` |
| `db` 子命令列表 | `python -m workflow.run db -h` |
| `db init` 的参数 | `python -m workflow.run db init -h` |
| `pipeline slot` 的参数 | `python -m workflow.run pipeline slot -h` |
| `pipeline batch` 的参数 | `python -m workflow.run pipeline batch -h` |
| `query page` 的参数 | `python -m workflow.run query page -h` |
| `generate all` 的参数 | `python -m workflow.run generate all -h` |
| torrent 模块 CLI | `python -m workflow.torrent_sources.run -h` |
| 测速模块 CLI | `python -m workflow.torrent_sources.speedtest.run -h` |

### 1.4 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 失败（参数错误、数据库不可用、业务逻辑失败、拉取/测速未达标等） |

---

## 二、命令树

### 2.1 总控 `workflow.run`

```
python -m workflow.run
├── status                              # 全局状态（含 tmdb_data_mode）
├── db
│   ├── create                          # 仅建库
│   ├── init [--seed] [--skip-create-db]
│   ├── seed                            # 导入演示数据
│   └── status                          # 库连通性 + 行数
├── run <step>                          # 单步工作流
│   ├── 4c [--test] [--tmdb ...] [--force]       # torrent 单槽拉取
│   └── recommended [--tmdb ...] [--demo] [--force]
├── pipeline
│   ├── slot --tmdb ... [--mode demo|live] [--fetch]
│   └── batch [--slots-json ...] [--fetch|--no-fetch]
├── query
│   └── page [--page-id | --tmdb ...]   # 读取 Jinja2 上下文
├── generate
│   ├── page [--page-id | --path] [--out]
│   └── all [--out]                     # 批量生成 published 页 + 首页
└── serve [--host] [--port]             # 本地开发服（默认 127.0.0.1:8080）
```

### 2.2 独立模块 CLI（非 `workflow.run` 子命令）

```
python -m workflow.torrent_sources.run
├── status                              # Jackett 配置与缓存状态
├── test [--tmdb ...] [--force]         # 单槽拉取（同 run 4c --test）
└── batch [--slots JSON] [--demo]       # 批量拉取（不写 MySQL）

python -m workflow.torrent_sources.speedtest.run
├── status                              # libtorrent 可用性
├── test | speed | full                 # 单 infohash Phase 1/2
├── slot --page-id ... [--write]        # MySQL 槽位 Recommended 测速
└── batch [--all-published] [--write]   # 多槽批量测速（策略 A2）
```

---

## 三、命令详解

### 3.1 `status` — 全局状态

**作用：** 输出 JSON，包含项目路径、存储后端、`tmdb_data_mode`、MySQL/D1 配置、数据源端点、各模块就绪状态；若 MySQL 已配置且可连，附带表行数。

**语法：**

```bash
python -m workflow.run status
```

**示例输出字段：**

- `storage_backend`：`mysql` 或 `d1`
- `tmdb_data_mode`：`standalone` 或 `mysql`
- `release_mysql.host` / `release_mysql.database`
- `endpoints.jackett` / `eztv` / `yts`
- `database.ok`：MySQL 表是否齐全
- `database.row_counts`：各表行数（连通时）

**典型用途：** 首次配置后确认 `.env` 是否生效、库是否已初始化。

---

### 3.2 `db` — 数据库管理

所有 `db` 子命令依赖 `RM_RELEASE_MYSQL_*` 环境变量（见 `.env`）。

#### `db create` — 仅建库

**作用：** 执行 `CREATE DATABASE IF NOT EXISTS`，字符集 `utf8mb4`。

**语法：**

```bash
python -m workflow.run db create
```

**说明：** `db init` 已包含此步骤，一般**无需单独执行**。

---

#### `db init` — 建库 + 建表

**作用：**

1. （默认）创建数据库 `RM_RELEASE_MYSQL_DB`（默认 `releasematch`）
2. 执行 `schema/mysql_schema.sql` 建表
3. （可选）`--seed` 导入演示数据

**语法：**

```bash
python -m workflow.run db init
python -m workflow.run db init --seed
python -m workflow.run db init --skip-create-db      # 库已存在，只建表
python -m workflow.run db init --skip-create-db --seed
```

**参数：**

| 参数 | 说明 |
|------|------|
| `--seed` | 初始化完成后自动执行 `db seed` |
| `--skip-create-db` | 跳过 `CREATE DATABASE` |

**推荐首次使用：**

```bash
python -m workflow.run db init --seed
```

---

#### `db seed` — 导入演示种子

**作用：** 执行 `schema/mysql_seed_demo.sql`（Breaking Bad S04E01~E08、S04E06 资源、Inception 等）。

**语法：**

```bash
python -m workflow.run db seed
```

**前提：** 表结构已存在（先 `db init`）。

---

#### `db status` — 库健康检查

**作用：** 检测 MySQL 连通性、表是否齐全、各表行数。

**语法：**

```bash
python -m workflow.run db status
```

**失败时常见字段：**

- `ping.error`：连接错误信息
- `ping.hint`：如库不存在，会提示执行 `db init`

---

### 3.3 `run` — 单步工作流

#### `run 4c` — torrent 资源拉取测试

**作用：** 调用 `FetchService`，对单个槽位做**多源真实拉取**（EZTV / YTS / Nyaa / Nyaa LA / DMHy / Jackett），含亚洲 `jp` / `kr` / `cn` 路由与跨源统计。成功需 **≥2 条** magnet。

**语法：**

```bash
# 欧美剧集
python -m workflow.run run 4c --test --tmdb 1396 --season 4 --episode 6

# 电影
python -m workflow.run run 4c --test --tmdb 27205 --media-type movie

# 忽略缓存强制重拉
python -m workflow.run run 4c --test --tmdb 1396 --season 4 --episode 6 --force
```

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `4c` | 是 | 步骤 ID；**别名：** `torrent`、`sources` |
| `--test` | 是 | 当前**必须**加；无 `--test` 会报错退出 |
| `--tmdb` | 建议 | TMDB 作品 ID |
| `--media-type` | 否 | `tv`（默认）或 `movie` |
| `--season` | 剧集 | 季号 |
| `--episode` | 剧集 | 集号 |
| `--imdb-id` | 否 | 可选 IMDb ID（缺省则从 TMDB 解析） |
| `--force` | 否 | 忽略 torrent 缓存，强制重拉 |

**等价独立入口：**

```bash
python -m workflow.torrent_sources.run test --tmdb 1396 --season 4 --episode 6
```

**华语 / 亚洲路由：** `original_language=zh` 或 `origin_country` 含 CN/HK/TW 时走 `cn` 路由，优先 DMHy + 中文标题搜索，详见 [11-CN华语影视资源方案.md](./11-CN华语影视资源方案.md)。

**前提：** `accounts.local.json` 中 Jackett API Key 有效；国内 Nyaa/DMHy 失败时可配 SOCKS 代理（见 [nyaa-proxy-asia.md](./nyaa-proxy-asia.md)）。

---

#### `run recommended` — Recommended 评分

**作用：** 调用 `workflow/recommended/scorer.py`。默认 **live 拉取 + 排序**；加 `--demo` 则使用内置 Demo 数据。

**语法：**

```bash
# Live：拉取 → 评分 → 输出 JSON（不写 MySQL）
python -m workflow.run run recommended --tmdb 1396 --season 4 --episode 6

# Demo：内置数据
python -m workflow.run run recommended --tmdb 1396 --season 4 --episode 6 --demo
```

**别名：** `rec`

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--tmdb` | 是 | TMDB 作品 ID |
| `--media-type` | 否 | `tv`（默认）或 `movie` |
| `--season` | 剧集 | 季号（live 模式必填） |
| `--episode` | 剧集 | 集号（live 模式必填） |
| `--demo` | 否 | 使用内置 Demo 数据，不拉取 |
| `--force` | 否 | 忽略 torrent 缓存 |

---

### 3.4 `pipeline` — 槽位流水线

#### `pipeline slot` — 单槽：拉取 → 评分 → 写 MySQL

**作用：**

1. 获取槽位 resource 列表（`demo` 或 `live --fetch`）
2. `recommended/scorer` 排序并标记 Recommended
3. 写入 `download_resources`，更新 `media_pages.magnet_count` / 薄页门禁
4. 写入 `sync_runs` 审计记录

**语法：**

```bash
# Demo 模式（内置 Breaking Bad S04E06 数据）
python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6

# 生产路径：真实拉取 → 写库
python -m workflow.run pipeline slot \
  --tmdb 1396 --season 4 --episode 6 --mode live --fetch
```

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--tmdb` | 是 | TMDB 作品 ID |
| `--media-type` | 否 | `tv`（默认）或 `movie` |
| `--season` | 剧集必填 | 季号 |
| `--episode` | 剧集必填 | 集号 |
| `--mode` | 否 | `demo`（默认）或 `live` |
| `--fetch` | live 时 | 调用 `FetchService` 拉取；**失败或 0 条时才回退 demo** |

**前提：** `RM_STORAGE_BACKEND=mysql`，且已 `db init`（建议 `--seed`）。

---

#### `pipeline batch` — 批量扩槽

**作用：** 读取 benchmark slot JSON，逐槽执行 `ensure_slot_page` → 拉取 → 评分 → 写 MySQL。默认跳过已有 ≥2 magnet 的页面；批量前可自动预热 TMDB `external_ids` 缓存。

**语法：**

```bash
python -m workflow.run pipeline batch \
  --slots-json worklogs/2026-07-03/tmdb-benchmark-slots.json \
  --mode live --fetch

# 强制重跑已有页面
python -m workflow.run pipeline batch \
  --slots-json data/failed_slots/failed-slots.json \
  --fetch --no-skip-existing
```

**参数：**

| 参数 | 默认 | 说明 |
|------|------|------|
| `--slots-json` | `worklogs/2026-07-03/tmdb-benchmark-slots.json` | slot 清单 JSON |
| `--mode` | `live` | `demo` 或 `live` |
| `--fetch` / `--no-fetch` | 默认 `--fetch` | 是否拉取 torrent |
| `--no-skip-existing` | — | 不跳过已有 ≥2 magnet 的页面 |

**推荐前置：**

```bash
python scripts/tmdb_warm_external_ids.py --force
```

**等价脚本：** `python scripts/pipeline_batch_slots.py --slots-json ... --fetch`

---

### 3.5 `query` — 读取页面数据

#### `query page` — 输出 Jinja2 上下文 JSON

**作用：** 从 MySQL 读取单集/电影页数据，组装为模板上下文（与 `schema/d1_models.py` 一致）。

**语法：**

```bash
# 方式 A：page_id
python -m workflow.run query page --page-id tv:1396:s04e06

# 方式 B：TMDB 槽位（自动解析 page_id）
python -m workflow.run query page --tmdb 1396 --season 4 --episode 6
python -m workflow.run query page --tmdb 27205 --media-type movie
```

**参数：**

| 参数 | 说明 |
|------|------|
| `--page-id` | 如 `tv:1396:s04e06`、`movie:27205` |
| `--tmdb` | 与 `--season` / `--episode` 组合使用 |
| `--media-type` | `tv` 或 `movie` |

**成功输出含：** `template_context`（`show_title`、`sources`、`recommended`、`speed_summary`、`group_tier` 等）。

---

### 3.6 `generate` — 静态 HTML 生成

**作用：** 从 MySQL 渲染 Jinja2 模板，写入 `portal/dist/`。`generate all` 还生成 **首页 `index.html`**（published 卡片聚合）。

**语法：**

```bash
# 单页（page_id）
python -m workflow.run generate page --page-id tv:1396:s04e06

# 单页（URL 路径）
python -m workflow.run generate page --path /breaking-bad/s4e6/

# 全量 published（生产 dist 构建 + sitemap.xml）
python -m workflow.run generate all

# 开发：嵌入 IG debug 面板
python -m workflow.run generate all --show-ig-debug
```

**产出（`generate all`）：**

- 各 published 内容页 → `portal/dist/<slug>/.../index.html`
- 首页 → `portal/dist/index.html`
- **sitemap** → `portal/dist/sitemap.xml`（按 SEO 决策 D3：≤30 indexable 内容页 + Trust 4 + 首页）

**参数：**

| 参数 | 说明 |
|------|------|
| `--page-id` | 如 `tv:1396:s04e06`（与 `--path` 二选一） |
| `--path` | URL 路径，如 `/breaking-bad/s4e6/` |
| `--out` | 输出根目录，默认 `portal/dist` |
| `--show-ig-debug` / `--no-ig-debug` | 覆盖环境变量 `RM_SHOW_IG_DEBUG` |

**前提：** 目标页面已在 MySQL 中 published 且 `magnet_count ≥ 2`（`generate all` 仅处理满足门禁的页）。

---

### 3.7 `serve` — 本地开发服

**作用：** 启动 HTTP 服务：`/breaking-bad/s4e6/` 等路径**实时读 MySQL 渲染**；`/static/` 等走 `portal/` 静态文件。

**语法：**

```bash
python -m workflow.run serve
python -m workflow.run serve --host 0.0.0.0 --port 8080
```

**说明：** SEO 验收以 **`generate all` 产出的 `portal/dist/`** 为准，非 `serve` 动态页。部署前可运行 **`scripts/seo_c2_checklist.sh`** 自动化 §6.1～6.3 本地检查（见 §5.8）。

---

### 3.8 C2 SEO 本地检查 — `scripts/seo_c2_checklist`

**作用：** 对 `portal/dist/` 执行 [页面SEO分析与优化方向.md](../worklogs/2026-07-03/页面SEO分析与优化方向.md) **§6.1～6.3** 可本地完成的检查（robots.txt、sitemap 规则、canonical 抽查、404/410、页面 head、MySQL magnet/Recommended 交叉验证等）。**§6.4 GSC** 与 **HTTPS/HSTS** 标记为 SKIP，须上线后在 Google Search Console 验收。

**语法：**

```bash
# 检查已有 dist（须先 generate all 或 deploy --prepare-only）
bash scripts/seo_c2_checklist.sh

# 先生成 dist 再检查（= deploy_cf_pages.sh --prepare-only + 检查）
bash scripts/seo_c2_checklist.sh --prepare

# JSON 报告（CI / 脚本解析）
bash scripts/seo_c2_checklist.sh --json

# 无 MySQL 时跳过 DB 交叉验证
bash scripts/seo_c2_checklist.sh --no-db
```

**等价 Python 入口：**

```bash
python scripts/seo_c2_checklist.py [--dist portal/dist] [--site-origin URL] [--prepare] [--no-db] [--json]
```

**参数：**

| 参数 | 说明 |
|------|------|
| `--dist` | dist 目录，默认 `portal/dist` |
| `--site-origin` | 期望 canonical origin，默认 `RM_SITE_ORIGIN` |
| `--prepare` | 检查前执行 `bash scripts/deploy_cf_pages.sh --prepare-only` |
| `--no-db` | 跳过 MySQL 交叉验证（无库环境） |
| `--json` | 输出 JSON 报告 |

**退出码：**

| 退出码 | 含义 |
|--------|------|
| `0` | 无 FAIL 项 |
| `1` | 存在 FAIL（如 OG/favicon 未实现、Trust privacy 缺 description） |
| `2` | `--prepare` 失败 |

**典型输出：** 按 §6.1 / §6.2 / §6.3 分组，每项标记 ✅ pass / ❌ fail / ⚠️ warn / ⏭️ skip。

**说明：** 生产部署完整流程为 `generate all` → `seo_c2_checklist.sh` → `bash scripts/deploy_cf_pages.sh`（见 §5.8）。

---

## 四、独立模块 CLI

### 4.1 `workflow.torrent_sources.run`

torrent 拉取模块的独立入口，逻辑与 `workflow.run run 4c --test` 相同，另含批量拉取（**不写 MySQL**）。

```bash
python -m workflow.torrent_sources.run status

python -m workflow.torrent_sources.run test \
  --tmdb 1396 --season 4 --episode 6 [--force]

python -m workflow.torrent_sources.run batch \
  --slots worklogs/2026-07-03/tmdb-benchmark-slots.json [--force]
```

| 子命令 | 说明 |
|--------|------|
| `status` | 缓存条目数、Jackett 配置与 HTTP 探测 |
| `test` | 单槽拉取，成功需 ≥2 条 |
| `batch` | 读 slots JSON 批量拉取；`--demo` 使用内置队列 |

**全局参数：** `--accounts` 指定 `accounts.local.json` 路径。

---

### 4.2 `workflow.torrent_sources.speedtest.run`

磁力测速 Phase 1（连通性）+ Phase 2（片段下载，S-06 `avg_kbps`），可选写入 `speedtest_results` / `slot_speed_summary`。

```bash
python -m workflow.torrent_sources.speedtest.run status

# 单槽 Recommended 测速 + 写 MySQL
python -m workflow.torrent_sources.speedtest.run slot \
  --page-id tv:1396:s04e06 --write

# 全 published 批量
python -m workflow.torrent_sources.speedtest.run batch \
  --all-published --write --workers 5 \
  --report worklogs/2026-07-03/speedtest-all-published-benchmark.json
```

| 子命令 | 说明 |
|--------|------|
| `test` | 单 infohash Phase 1（`--infohash`） |
| `speed` | 单 infohash Phase 2 |
| `full` | Phase 1 + Phase 2；`--write` 写 MySQL |
| `slot` | MySQL 槽位 Recommended magnet 测速 |
| `batch` | 多 `page_id` / `--slots-json` / `--all-published` |

**常用 batch 参数：**

| 参数 | 说明 |
|------|------|
| `--write` | 写入 MySQL |
| `--workers` | 并发进程数（cron 推荐 5） |
| `--force` | 忽略 TTL 强制重测 |
| `--ttl-hours` | TTL 内跳过已测 hash |
| `--dry-run` | 不联网，仅校验 infohash 格式 |

**生产 cron：** 推荐使用 `scripts/speedtest_batch_worker.py`，详见 [VPS迁移与部署.md](./VPS迁移与部署.md)。

**依赖：** Phase 2 真实测速需安装 `libtorrent`；未安装时仅 `dry_run`。

---

## 五、常用工作流（复制即用）

### 5.1 从零开始本地环境

```bash
cd releasematch
cp config.env.example .env          # 编辑 MySQL 账号
cp workflow/torrent_sources/accounts.example.json \
   workflow/torrent_sources/accounts.local.json   # 编辑 Jackett API Key
pip install -r requirements.txt
python -m workflow.run db init --seed
python -m workflow.run status
```

### 5.2 验证演示页数据

```bash
python -m workflow.run db status
python -m workflow.run query page --page-id tv:1396:s04e06
python -m workflow.run generate page --page-id tv:1396:s04e06
python -m workflow.run serve          # 浏览器打开 http://127.0.0.1:8080/
```

### 5.3 跑通单槽 pipeline 并复查

```bash
python -m workflow.run pipeline slot \
  --tmdb 1396 --season 4 --episode 6 --mode live --fetch
python -m workflow.run query page --tmdb 1396 --season 4 --episode 6
```

### 5.4 生产扩槽 → 静态页 → 测速（标准路径）

```bash
# 1. 预热 TMDB external_ids（需 RM_TMDB_API_KEY）
python scripts/tmdb_warm_external_ids.py --force

# 2. 批量 pipeline
python -m workflow.run pipeline batch \
  --slots-json worklogs/2026-07-03/tmdb-benchmark-slots.json --fetch

# 3. 生成静态站 + sitemap
python -m workflow.run generate all

# 4. C2 SEO 本地检查（§6.1～6.3）
bash scripts/seo_c2_checklist.sh

# 5. 全量测速（cron 推荐 worker + workers=5）
python scripts/speedtest_batch_worker.py \
  --all-published --write --workers 5 \
  --report worklogs/$(date +%Y-%m-%d)/speedtest-all-published-benchmark.json
```

### 5.5 测试评分与 torrent 拉取

```bash
python -m workflow.run run recommended --tmdb 1396 --season 4 --episode 6
python -m workflow.run run 4c --test --tmdb 1396 --season 4 --episode 6
```

### 5.6 仅重置演示数据（保留表结构）

```bash
python -m workflow.run db seed
```

### 5.7 失败 slot 重试

```bash
python scripts/failed_slots_merge_reports.py --list-active
python -m workflow.run pipeline batch \
  --slots-json data/failed_slots/failed-slots.json \
  --fetch --no-skip-existing
```

### 5.8 C2 SEO 本地验收（GSC 提交前）

```bash
# 方式 A：已有 dist
python -m workflow.run generate all
bash scripts/seo_c2_checklist.sh

# 方式 B：一键 prepare + 检查
bash scripts/seo_c2_checklist.sh --prepare

# 仅 JSON（供 CI）
bash scripts/seo_c2_checklist.sh --json | jq '.summary'
```

**通过标准：** 退出码 `0`（无 FAIL）。常见 FAIL 来自尚未实现的 P1 项（Open Graph、favicon、Trust privacy description），修复后重跑即可。

**上线后（不可本地替代）：** Cloudflare Pages 部署 → 生产 URL 验证 HTTPS/410 HTTP 状态 → GSC 属性验证与 sitemap 提交（§6.4）。

---

## 六、相关环境变量（摘要）

完整说明见 [05-存储与部署配置.md](./05-存储与部署配置.md)。

| 变量 | 影响命令 | 默认 / 说明 |
|------|---------|------------|
| `RM_STORAGE_BACKEND` | `pipeline`、`query`、`generate` | `mysql` |
| `RM_RELEASE_MYSQL_*` | 所有 `db`、`pipeline`、`query`、`generate` | 见 `config.env.example` |
| `RM_SITE_ORIGIN` | `query page`、`generate` 的 canonical URL | `https://releasematch.io` |
| `RM_SHOW_IG_DEBUG` | `generate`、`serve` | `0`；CLI 可用 `--show-ig-debug` 覆盖 |
| `RM_TMDB_DATA_MODE` | metadata 解析 | `standalone` |
| `RM_TMDB_API_KEY` | `pipeline batch` 预热、`tmdb_warm_external_ids.py` | 可选，批量扩槽推荐 |
| `RM_TMDB_CORS_PROXY` | 国内 TMDB API 代理 | 可选 |
| `accounts.local.json` | `run 4c`、`pipeline --fetch` | Jackett / Nyaa / **DMHy** / 代理配置 |

---

## 七、辅助脚本索引

| 脚本 | 用途 |
|------|------|
| `scripts/pipeline_batch_slots.py` | 等价 `pipeline batch`，额外日志选项 |
| `scripts/speedtest_batch_worker.py` | 生产 cron 批量测速（多 worker） |
| `scripts/tmdb_warm_external_ids.py` | pipeline batch 前预热 imdb/tvdb 缓存 |
| `scripts/tmdb_select_benchmark_slots.py` | TMDB 日导出 → benchmark slot JSON |
| `scripts/failed_slots_merge_reports.py` | 合并 pipeline 失败报告 → 登记册 |
| `scripts/seo_c2_checklist.sh` | C2 SEO 本地检查（§6.1～6.3）；等价 `seo_c2_checklist.py` |
| `scripts/deploy_cf_pages.sh` | `generate all` + 同步静态壳 + wrangler 部署 CF Pages |

---

## 八、故障排查

| 现象 | 处理 |
|------|------|
| `RM_RELEASE_MYSQL_USER 未设置` | 配置 `.env` 或 `export RM_RELEASE_MYSQL_USER` |
| `Unknown database` / 1049 | `python -m workflow.run db init` |
| `tables_missing` | `python -m workflow.run db init` |
| `query page` 页面不存在 | 先 `db seed` 或跑 `pipeline slot`；检查 `page_id` 格式 |
| `pipeline slot` 无 items | Demo 仅内置 1396 S04E06；其他槽位需 `--mode live --fetch` |
| `run 4c` 要求 `--test` | 必须加 `--test` 参数 |
| `run 4c` 返回 1、items < 2 | 检查 Jackett / 代理；华语槽位见 [11-CN华语影视资源方案.md](./11-CN华语影视资源方案.md) |
| `recommended 步骤需要 --tmdb` | 补充 `--tmdb` |
| `generate all` 页数少于预期 | 仅生成 `published` 且 `magnet_count ≥ 2` 的页 |
| 测速全为 `dry_run` | 安装 `libtorrent`（见 worklogs speedtest 文档） |
| Nyaa/DMHy 国内超时 | 配置 SSH SOCKS 隧道，见 [nyaa-proxy-asia.md](./nyaa-proxy-asia.md) |
| `seo_c2_checklist` FAIL：缺 OG / favicon | T-SEO-05 未实现；见 worklogs SEO 文档 P1 任务 |
| `seo_c2_checklist` FAIL：privacy 缺 description | T-SEO-07；补 `portal/trust/privacy/index.html` meta |
| `seo_c2_checklist`：dist 不存在 | 先 `generate all` 或加 `--prepare` |

---

## 九、与代码模块对应关系

| CLI 命令 | 代码模块 |
|---------|---------|
| `db *` | `workflow/storage/mysql_store.py` |
| `run 4c` | `workflow/torrent_sources/run.py` → `fetch_service.py` |
| `run recommended` | `workflow/recommended/scorer.py` |
| `pipeline slot` / `batch` | `workflow/storage/pipeline.py` |
| `query page` | `workflow/storage/pipeline.py` + `schema/d1_models.py` |
| `generate *` | `portal/generator/generate_one.py`、`render.py`、`sitemap.py` |
| `seo_c2_checklist` | `scripts/seo_c2_checklist.py` |
| `serve` | `portal/generator/dev_server.py` |
| `torrent_sources.run *` | `workflow/torrent_sources/run.py` |
| `speedtest.run *` | `workflow/torrent_sources/speedtest/` |
| 配置读取 | `workflow/config.py` |
| 亚洲路由 / DMHy | `asia_region.py`、`dmhy_client.py` |

---

## 十、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-06-29 | 初版：status / db / run / pipeline slot / query |
| v0.2 | 2026-07-03 | 新增 `generate`、`serve`、`pipeline batch`；独立 CLI（torrent_sources、speedtest）；修正 live/fetch 与 recommended；DMHy/cn 路由；生产工作流、脚本索引与故障排查 |
| v0.3 | 2026-07-04 | `generate all` 产出 sitemap；新增 §3.8 / §5.8 `seo_c2_checklist` C2 SEO 本地检查用法 |
