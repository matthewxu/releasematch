# A4 完成 Jackett 本地服务（Windows）

> **适用：** 本机无 Docker（已检测）或偏好 Windows 原生安装  
> **目标：** `http://127.0.0.1:9117` 可访问 + API Key 写入 `accounts.local.json`  
> **完整手册：** [05-Jackett详解与安装使用教程.md](../../docs/05-Jackett详解与安装使用教程.md)

---

## 当前环境检测结果（2026-06-30）

| 检查项 | 结果 |
|--------|------|
| Docker CLI | 未安装 |
| 端口 9117 | 未监听 |
| Jackett HTTP | 不可达 |

因此 **不要用 Docker 命令**，请走下方 **Windows 安装路径**。

---

## 一键引导（推荐）

在 **PowerShell** 中执行：

```powershell
cd C:\Users\matth\Desktop\trafficforvideo\releasematch\releasematch
.\scripts\setup_jackett_a4.ps1
```

脚本会：

1. 检测 9117 端口  
2. 提示用 **winget** 或 **官方安装包** 安装 Jackett  
3. 打开 Dashboard，引导复制 API Key  
4. 写入 `accounts.local.json`  
5. 跑 Torznab 冒烟测试 + `torrent_sources.run status`

若已有 API Key，可跳过交互：

```powershell
.\scripts\setup_jackett_a4.ps1 -ApiKey "你的Key"
```

---

## 手动步骤（与脚本等价）

### 步骤 1：安装 Jackett

**方式 A — winget（推荐）**

```powershell
winget install --id Jackett.Jackett -e --accept-package-agreements --accept-source-agreements
net start Jackett
```

**方式 B — 官方安装包**

1. 打开 [Jackett Releases](https://github.com/Jackett/Jackett/releases/latest)  
2. 下载 `Jackett.Installer.Windows.exe` 并安装  
3. 安装程序通常会注册 Windows 服务并自动启动  

**验证端口：**

```powershell
Test-NetConnection 127.0.0.1 -Port 9117
# TcpTestSucceeded : True
```

浏览器访问：http://127.0.0.1:9117/UI/Dashboard

---

### 步骤 2：添加 Indexer（首次使用必做）

在 Jackett Dashboard：

1. 点击 **Add indexer**  
2. 至少添加 1~2 个常用源，例如：**1337x**、**EZTV**、**TorrentGalaxy**  
3. 按提示完成配置（部分站需 Cloudflare 或 cookie）  

> 无 indexer 时 Torznab 搜索会返回空结果，PoC 可能「HTTP 200 但无条目」。

---

### 步骤 3：复制 API Key

Dashboard **右上角** → **Copy API Key**（或 **System** → **API Key**）

---

### 步骤 4：写入 ReleaseMatch 配置

编辑 `workflow/torrent_sources/accounts.local.json`：

```json
"jackett": {
  "base_url": "http://127.0.0.1:9117",
  "api_key": "粘贴你的真实Key",
  ...
}
```

或设置环境变量（优先级更高）：

```powershell
$env:JACKETT_API_KEY = "你的Key"
```

---

### 步骤 5：验收 A4

```powershell
cd releasematch
.\.venv\Scripts\Activate.ps1

# 1) 项目状态 — 期望 has_valid_api_key: true, jackett_probe.reachable: true
python -m workflow.torrent_sources.run status

# 2) Torznab 冒烟（BB S04E06）
$env:JACKETT_API_KEY = "你的Key"   # 若已写入 json 可省略
.\scripts\poc_phase0.ps1
# 期望 [1/4] OK status=200（非 SKIPPED）
```

---

## A4 验收标准

| ID | 项 | 通过条件 |
|----|-----|----------|
| A4-1 | 服务 | `TcpTestSucceeded = True` 或 Dashboard 可打开 |
| A4-2 | API Key | `has_valid_api_key: true`（非占位符） |
| A4-3 | HTTP 探测 | `jackett_probe.reachable: true` |
| A4-4 | Torznab | PoC `[1/4]` 显示 `OK status=200` |

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `net start Jackett` 失败 | `services.msc` → 找到 **Jackett** → 启动；或从开始菜单打开 Jackett |
| 9117 被占用 | Jackett 设置中改端口，并同步修改 `accounts.local.json` 的 `base_url` |
| PoC 200 但无结果 | Dashboard 添加 indexer；用 `indexers/1337x/...` 单源测试 |
| 想用 Docker | 先安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，再执行文档中的 `docker run` |

---

## 完成后

- 更新 `今日验收清单.md` 勾选 D-A3 / D-A4  
- 继续 **块 B**：`.\scripts\poc_phase0.ps1`
