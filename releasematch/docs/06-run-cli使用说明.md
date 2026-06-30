# 06 — workflow.run 总控 CLI 使用说明

> **入口文件：** `workflow/run.py`  
> **调用方式：** `python -m workflow.run <子命令> [参数]`  
> **前置：** 在 `releasematch/` 目录下执行；配置见 [05-存储与部署配置.md](./05-存储与部署配置.md)

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
```

工作流启动时会**自动读取** `.env`（不覆盖已在 shell 中 `export` 的变量）。

### 1.3 查看帮助

帮助采用 **层级递进**：在「当前要执行的那一层命令」后加 `-h` 或 `--help`。

| 想看什么 | 命令 |
|---------|------|
| 全部顶层子命令 | `python -m workflow.run -h` |
| `db` 子命令列表 | `python -m workflow.run db -h` |
| `db init` 的参数 | `python -m workflow.run db init -h` |
| `pipeline slot` 的参数 | `python -m workflow.run pipeline slot -h` |
| `query page` 的参数 | `python -m workflow.run query page -h` |

### 1.4 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 失败（参数错误、数据库不可用、业务逻辑失败等） |

---

## 二、命令树

```
python -m workflow.run
├── status                          # 全局状态
├── db
│   ├── create                      # 仅建库
│   ├── init [--seed] [--skip-create-db]
│   ├── seed                        # 导入演示数据
│   └── status                      # 库连通性 + 行数
├── run <step>                      # 单步工作流
│   ├── 4c [--test] [--tmdb ...]    # torrent_sources 测试
│   └── recommended [--tmdb ...]    # 评分引擎 Demo
├── pipeline
│   └── slot --tmdb ...             # 单槽 pipeline
└── query
    └── page [--page-id ...]        # 读取 Jinja2 上下文
```

---

## 三、命令详解

### 3.1 `status` — 全局状态

**作用：** 输出 JSON，包含项目路径、存储后端、MySQL/D1 配置、数据源端点、各模块就绪状态；若 MySQL 已配置且可连，附带表行数。

**语法：**

```bash
python -m workflow.run status
```

**示例输出字段：**

- `storage_backend`：`mysql` 或 `d1`
- `release_mysql.host` / `release_mysql.database`
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

**作用：** 调用 `workflow/torrent_sources`，对单个槽位做四源拉取测试。

**语法：**

```bash
python -m workflow.run run 4c --test --tmdb 1396 --season 4 --episode 6
python -m workflow.run run 4c --test --tmdb 27205 --media-type movie
```

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `4c` | 是 | 步骤 ID（别名：`torrent`、`sources` 尚未在 CLI 暴露为 step 名，请用 `4c`） |
| `--test` | 是 | 当前**必须**加；无 `--test` 会报错退出 |
| `--tmdb` | 建议 | TMDB 作品 ID |
| `--media-type` | 否 | `tv`（默认）或 `movie` |
| `--season` | 剧集 | 季号 |
| `--episode` | 剧集 | 集号 |
| `--imdb-id` | 否 | 可选 IMDb ID |

**说明：** 完整 batch/on-demand 编排尚未接入总控，见 R1 路线图。

---

#### `run recommended` — Recommended 评分 Demo

**作用：** 调用 `workflow/recommended/scorer.py`，对 Demo 数据排序并输出 JSON。

**语法：**

```bash
python -m workflow.run run recommended --tmdb 1396 --season 4 --episode 6
```

**别名：** `rec`

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--tmdb` | 是 | TMDB 作品 ID |
| `--season` | 否 | 季号 |
| `--episode` | 否 | 集号 |

---

### 3.4 `pipeline` — 槽位流水线

#### `pipeline slot` — 单槽：评分 → 写 MySQL

**作用：**

1. 获取槽位 resource 列表（demo 或 `--fetch`）
2. `recommended/scorer` 排序并标记 Recommended
3. 写入 `download_resources`，更新 `media_pages.magnet_count` / 薄页门禁
4. 写入 `sync_runs` 审计记录

**语法：**

```bash
# Demo 模式（内置 Breaking Bad S04E06 数据）
python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6

# 指定模式
python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6 --mode demo
python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6 --mode live --fetch
```

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--tmdb` | 是 | TMDB 作品 ID |
| `--media-type` | 否 | `tv`（默认）或 `movie` |
| `--season` | 剧集必填 | 季号 |
| `--episode` | 剧集必填 | 集号 |
| `--mode` | 否 | `demo`（默认）或 `live` |
| `--fetch` | 否 | 调用 torrent_sources（R1；当前回退 demo） |

**前提：** `RM_STORAGE_BACKEND=mysql`，且已 `db init`（建议 `--seed`）。

---

### 3.5 `query` — 读取页面数据

#### `query page` — 输出 Jinja2 上下文 JSON

**作用：** 从 MySQL 读取单集页数据，组装为 `episode.html` 模板上下文（与 `schema/d1_models.py` 一致）。

**语法：**

```bash
# 方式 A：page_id
python -m workflow.run query page --page-id tv:1396:s04e06

# 方式 B：TMDB 槽位（自动解析 page_id）
python -m workflow.run query page --tmdb 1396 --season 4 --episode 6
```

**参数：**

| 参数 | 说明 |
|------|------|
| `--page-id` | 如 `tv:1396:s04e06`、`movie:27205` |
| `--tmdb` | 与 `--season` / `--episode` 组合使用 |
| `--media-type` | `tv` 或 `movie` |

**成功输出含：** `template_context`（`show_title`、`sources`、`recommended`、`speed_summary` 等）。

---

## 四、常用工作流（复制即用）

### 4.1 从零开始本地环境

```bash
cd releasematch
cp config.env.example .env          # 编辑 MySQL 账号
pip install -r requirements.txt
python -m workflow.run db init --seed
python -m workflow.run status
```

### 4.2 验证演示页数据

```bash
python -m workflow.run db status
python -m workflow.run query page --page-id tv:1396:s04e06
```

### 4.3 跑通 pipeline 并复查

```bash
python -m workflow.run pipeline slot --tmdb 1396 --season 4 --episode 6
python -m workflow.run query page --tmdb 1396 --season 4 --episode 6
```

### 4.4 仅重置演示数据（保留表结构）

```bash
python -m workflow.run db seed
```

### 4.5 测试评分与 torrent 拉取

```bash
python -m workflow.run run recommended --tmdb 1396 --season 4 --episode 6
python -m workflow.run run 4c --test --tmdb 1396 --season 4 --episode 6
```

---

## 五、相关环境变量（摘要）

完整说明见 [05-存储与部署配置.md](./05-存储与部署配置.md)。

| 变量 | 影响命令 | 默认 |
|------|---------|------|
| `RM_STORAGE_BACKEND` | `pipeline`、`query` | `mysql` |
| `RM_RELEASE_MYSQL_HOST` | 所有 `db`、`pipeline`、`query` | `127.0.0.1` |
| `RM_RELEASE_MYSQL_PORT` | 同上 | `3306` |
| `RM_RELEASE_MYSQL_DB` | 同上 | `releasematch` |
| `RM_RELEASE_MYSQL_USER` | 同上 | （空，必填） |
| `RM_RELEASE_MYSQL_PASSWORD` | 同上 | （空） |
| `RM_SITE_ORIGIN` | `query page` 的 canonical URL | `https://releasematch.io` |
| `JACKETT_*` / `EZTV_*` 等 | `run 4c --test` | 见 `config.env.example` |

---

## 六、故障排查

| 现象 | 处理 |
|------|------|
| `RM_RELEASE_MYSQL_USER 未设置` | 配置 `.env` 或 `export RM_RELEASE_MYSQL_USER` |
| `Unknown database` / 1049 | `python -m workflow.run db init` |
| `tables_missing` | `python -m workflow.run db init` |
| `query page` 页面不存在 | 先 `db seed`，或检查 `page_id` 格式 |
| `pipeline slot` 无 items | Demo 内置槽位为 1396 S04E06；其他槽位需 `db seed` |
| `run 4c` 要求 `--test` | 必须加 `--test` 参数 |
| `recommended 步骤需要 --tmdb` | 补充 `--tmdb` |

---

## 七、与代码模块对应关系

| CLI 命令 | 代码模块 |
|---------|---------|
| `db *` | `workflow/storage/mysql_store.py` |
| `run 4c` | `workflow/torrent_sources/run.py` |
| `run recommended` | `workflow/recommended/scorer.py` |
| `pipeline slot` | `workflow/storage/pipeline.py` |
| `query page` | `workflow/storage/pipeline.py` + `schema/d1_models.py` |
| 配置读取 | `workflow/config.py` |

---

## 八、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-06-29 | 初版：status / db / run / pipeline / query 全命令说明 |
