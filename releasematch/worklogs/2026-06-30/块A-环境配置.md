# 块 A — 环境与配置

> **日期：** 2026-06-30  
> **状态：** 自动化部分已完成；**需你本地手填 Jackett Key 并启动服务（A4）**

---

## 已完成

| ID | 项 | 结果 |
|----|-----|------|
| A1 | Python 虚拟环境 | `.venv/` 已创建 |
| A1 | 依赖安装 | `requests 2.34.2`、`PyMySQL 1.2.0`、`PyYAML 6.0.3` |
| A2 | Jackett 配置 | `workflow/torrent_sources/accounts.local.json` 已从 example 复制 |
| A3 | 环境变量模板 | `.env.example` 已添加（`.env` 需自行复制） |
| A5 | 状态基线 | `python -m workflow.run status` / `torrent_sources.run status` 可运行 |

### 附带修复

- `requirements.txt` 中文注释改为 ASCII，避免 Windows GBK 下 `pip install` 失败
- `torrent_sources.run status` 增加：
  - `has_valid_api_key`（识别 `YOUR_JACKETT_API_KEY` 占位符）
  - `jackett_probe`（HTTP 探测 Jackett 是否可达）
  - `accounts_config` 路径
- 新增一键脚本：`scripts/setup_block_a.ps1`

---

## 待你本地完成（A3 / A4）

> **环境检测：** 本机未安装 Docker，9117 端口未监听 → 请用 **Windows 原生 Jackett**。  
> **详细引导：** [A4-Jackett安装引导.md](./A4-Jackett安装引导.md)

### 一键完成 A4

```powershell
cd releasematch
.\scripts\setup_jackett_a4.ps1
```

### 手动：填入 Jackett API Key（二选一）

**方式 A — 编辑 JSON：**

```
workflow/torrent_sources/accounts.local.json
→ jackett.api_key 改为 Jackett Dashboard 中的 API Key
```

**方式 B — 环境变量：**

```powershell
$env:JACKETT_API_KEY = "你的真实Key"
```

### 手动：启动 Jackett（A4）

见 [A4-Jackett安装引导.md](./A4-Jackett安装引导.md)。简要：

```powershell
winget install --id Jackett.Jackett -e
net start Jackett
# 浏览器 http://127.0.0.1:9117/UI/Dashboard → Copy API Key
.\scripts\setup_jackett_a4.ps1
```

```powershell
cd releasematch
.\scripts\setup_block_a.ps1
# 或手动：
.\.venv\Scripts\Activate.ps1
python -m workflow.torrent_sources.run status
```

**期望 JSON 片段：**

```json
{
  "has_valid_api_key": true,
  "jackett_probe": {
    "reachable": true,
    "status_code": 200
  }
}
```

---

## 验收对照

| 验收 ID | 状态 | 说明 |
|---------|------|------|
| D-A1 | ✅ | imports OK |
| D-A2 | ✅ | `has_valid_api_key: true` |
| D-A3 | ✅ | Torznab HTTP 200（indexer 待补全时可无结果） |
| D-A4 | ✅ | `jackett_probe.reachable: true`, status=200 |
| D-A5 | ✅ | status 基线已记录 |

**块 A 已于 2026-06-30 验收通过。**

---

## status 基线快照（2026-06-30）

```json
{
  "project_root": ".../releasematch",
  "tmdb_data_mode": "standalone",
  "modules": {
    "torrent_sources": "scaffold",
    "recommended": "scaffold",
    "metadata": "scaffold",
    "priority": "scaffold"
  },
  "portal": "not_started"
}
```
