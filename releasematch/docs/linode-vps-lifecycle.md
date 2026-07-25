# Linode VPS 生命周期自动化（购买 / 取 IP / 删除）

> **目录：** [`workflow/torrent_sources/`](../workflow/torrent_sources/)（脚本与配置同目录）  
> **脚本：** [`linode_vps.py`](../workflow/torrent_sources/linode_vps.py)（独立可执行，可供外部程序调用）  
> **依赖：** 仅需 `linode_api4`（见 [`requirements-linode.txt`](../workflow/torrent_sources/requirements-linode.txt)）  
> **前置：** 已开通 Linode 账号并完成支付方式绑定  
> **关联：** Jackett 装机见 [jackett-remote-linode.md](./jackett-remote-linode.md)

---

## 一、能力与边界

| 操作 | 说明 |
|------|------|
| **create** | 创建（购买）一台 Linode Instance，等待 `running` 后返回公网 IPv4 |
| **ip** | 按 `id` 或 `label` 查询公网 IPv4 |
| **list** | 列出账号下全部实例 |
| **delete** | 按 `id` 或 `label` 销毁实例（不可恢复，按小时计费立即停止） |
| **params** | 枚举 create 可用的 `--region` / `--type` / `--image`（API 实时） |

脚本**不**负责：SSH 装机、Jackett 部署、防火墙。创建拿到 IP 后，可再调用本仓库的 `install_jackett_oneclick.sh`；**或直接用一键脚本集成模式**（推荐）：

```bash
# 购买（读 linode.local.json）+ 安装 Jackett + 回写 servers.local.json
bash scripts/install_jackett_oneclick.sh --provision-linode --with-indexers

# 销毁（label 默认取自 linode.local.json → defaults.label）
bash scripts/install_jackett_oneclick.sh --destroy-linode
```

> **ToS 提醒：** Linode 对 BitTorrent 有限制。若 VPS 主要用于 BT/测速，优先评估 Hetzner 等；Jackett 仅做 HTTP 索引抓取时通常可接受，但仍需自行对照 ToS。

---

## 二、一次性准备

### 2.1 创建 API Token

入口：[Cloud Manager](https://cloud.linode.com) → 右上角用户名 → **API Tokens** → **Create a Personal Access Token**  
官方说明：[Manage personal access tokens](https://techdocs.akamai.com/cloud-computing/docs/manage-personal-access-tokens) · [API Get started / scopes](https://techdocs.akamai.com/linode-api/reference/get-started)

创建弹窗需填写三项；**Expiry 与各产品 Access 创建后不可改**，只能撤销再新建。

#### 2.1.1 Label / Expiry

| 选项 | 说明 | 建议 |
|------|------|------|
| **Label** | 仅用于识别，如 `releasematch-linode-vps` | 写明用途，便于日后排查/撤销 |
| **Expiry** | 过期时间：Never / 1 / 3 / 6 个月等（以界面为准） | 长期脚本可用 Never；共享/临时环境用短有效期 |

Token 字符串**只在创建成功弹窗显示一次**，关闭后无法再查看，请立刻写入 `linode.local.json` 或密码管理器。

#### 2.1.2 Access 三级权限（每个产品一行）

Cloud Manager 对每个产品/服务提供三档（对应 OAuth scope 的 `*_only` / `*_write`）：

| 界面选项 | 含义 | 对应 scope 形态 |
|----------|------|-----------------|
| **No Access** | 该类别完全不可访问 | （不授予该 scope） |
| **Read Only** | 仅 GET / 列表 / 查询 | `{category}:read_only` |
| **Read/Write** | 查询 + 创建/修改/删除 | `{category}:read_write` |

原则：**只开本脚本需要的最小权限**；不要一键全开 Read/Write。泄露 Token = 拥有同等权限。

#### 2.1.3 本脚本（`linode_vps.py`）推荐勾选

| Cloud Manager 产品行 | 推荐 | 本脚本用途 | 不勾/勾错时的典型现象 |
|----------------------|------|------------|------------------------|
| **Linodes** | **Read/Write** | `create` / `list` / `ip` / `delete`；`params --kind type` | 403；无法创建或删除实例 |
| **Images** | **Read Only** | `params --kind image`；create 选用公开镜像 id | 枚举镜像失败；create 指定镜像可能失败 |
| **Account** | No Access 或 Read Only | 一般不需要；查账单/账号信息才要 | — |
| **IPs** | 默认 No Access | 仅预留/管理独立 IP 时才需 Read/Write | 普通 create 自动分配公网 IP，通常不需要 |
| **Firewalls** | 默认 No Access | 脚本不配防火墙 | — |
| **Volumes / Domains / NodeBalancers / Object Storage / LKE / Databases / Longview / StackScripts / VPC** 等 | **No Access** | 本脚本不使用 | — |

**最低可跑通组合（推荐）：**

- Linodes → **Read/Write**
- Images → **Read Only**
- 其余 → **No Access**

> **Regions：** 区域列表多为公开/账号可读信息，Cloud Manager 未必单独列出 “Regions” 行；`params --kind region` 在已有 Linodes 读权限时一般可用。若枚举区域报权限错误，再给 **Account: Read Only** 试一次。

创建后复制 Token → 写入 §2.2 的 `linode.local.json`。

#### 2.1.4 权限与子命令对照

| 子命令 | 至少需要的 Access |
|--------|-------------------|
| `params --kind region` | 通常无需额外写权限；有 Token + Linodes 读即可 |
| `params --kind type` | Linodes: Read Only（或 Write） |
| `params --kind image` | Images: Read Only |
| `list` / `ip` | Linodes: Read Only |
| `create` | Linodes: **Read/Write**；Images: Read Only（选镜像） |
| `delete` | Linodes: **Read/Write** |

#### 2.1.5 Cloud Manager 产品 ↔ OAuth Scope 全表

界面上的产品名与 API scope 对应关系如下（创建 Token 时按产品选 Access，底层即授予对应 scope）。完整官方表见 [Get started → OAuth scopes](https://techdocs.akamai.com/linode-api/reference/get-started)。

| 产品 / 类别（界面常见名） | Read Only scope | Read/Write scope | 说明 |
|---------------------------|-----------------|------------------|------|
| Account | `account:read_only` | `account:read_write` | 账号信息、用户、计费相关等 |
| Databases（Managed DB） | `databases:read_only` | `databases:read_write` | 托管数据库 |
| Domains（DNS Manager） | `domains:read_only` | `domains:read_write` | DNS 域名 |
| Events | `events:read_only` | `events:read_write` | 账号事件流 |
| Firewalls（Cloud Firewall） | `firewall:read_only` | `firewall:read_write` | 云防火墙 |
| Images | `images:read_only` | `images:read_write` | 系统/自定义镜像 |
| IPs | `ips:read_only` | `ips:read_write` | 公网/预留 IP |
| **Linodes** | `linodes:read_only` | `linodes:read_write` | **VPS 实例（本脚本核心）** |
| Kubernetes（LKE） | `lke:read_only` | `lke:read_write` | LKE 集群 |
| Longview | `longview:read_only` | `longview:read_write` | 监控客户端 |
| NodeBalancers | `nodebalancers:read_only` | `nodebalancers:read_write` | 负载均衡 |
| Object Storage | `object_storage:read_only` | `object_storage:read_write` | 对象存储 |
| StackScripts | `stackscripts:read_only` | `stackscripts:read_write` | 部署脚本 |
| Volumes | `volumes:read_only` | `volumes:read_write` | 块存储卷 |
| VPC | （视界面） | `vpc:read_write` | VPC / 子网 |

> 部分新产品行可能随 Cloud Manager 更新增减；以创建 Token 弹窗实时列表为准。scope 创建后不可追加，只能 **Revoke** 后重建。

#### 2.1.6 安全注意

1. Token ≈ 密码：勿提交 GitHub、勿写入公开文档或聊天记录。
2. 怀疑泄露 → Cloud Manager 对该 Token 点 **Revoke**，再新建并更新 `linode.local.json`。
3. 不要用「全产品 Read/Write」图省事；本脚本只需 Linodes 写 + Images 读。
4. 多环境（本机 / CI）建议各建独立 Token，便于分别撤销。

### 2.2 Token：本地 config（推荐）或环境变量

**推荐：本地 JSON（已加入 `.gitignore`，不会上传 GitHub）**

```bash
cd workflow/torrent_sources
cp linode.example.json linode.local.json
# 编辑 linode.local.json，把 token 换成真实 Personal Access Token
```

`linode.local.json` 示例字段：

```json
{
  "token": "你的真实token",
  "http_timeout": null,
  "defaults": {
    "label": "rm-jackett-jp",
    "region": "jp-osa",
    "type": "g6-nanode-1",
    "image": "linode/debian12",
    "ssh": {
      "user": "root",
      "password": "与 servers.local.json 中 jackett_vps_japan.ssh.password 一致",
      "port": 22
    }
  }
}
```

- `defaults.label`：实例名；`create` / 一键 `--provision-linode` / `--destroy-linode` 未传 CLI 时使用  
- `defaults.ssh.password`：`create` 未传 `--root-pass` 时作为 root 密码  

查看当前生效默认（不调 API）：

```bash
python workflow/torrent_sources/linode_vps.py defaults
python workflow/torrent_sources/linode_vps.py defaults --json
```

**读取优先级（高 → 低）：**

1. 环境变量 `LINODE_TOKEN`（CI / 临时覆盖）
2. `--config /path/to.json`
3. 自动查找：脚本同目录 `linode.local.json` → 当前工作目录 `./linode.local.json`

可选环境变量：

```bash
# 临时覆盖本地 config 中的 token
export LINODE_TOKEN="你的token"
# 可选：HTTP 超时（秒）；也可用 config.http_timeout
# export LINODE_HTTP_TIMEOUT=120
```

| 文件 | 是否入库 |
|------|----------|
| `workflow/torrent_sources/linode_vps.py` | ✅ 控制脚本 |
| `workflow/torrent_sources/requirements-linode.txt` | ✅ 依赖清单 |
| `workflow/torrent_sources/linode.example.json` | ✅ 模板，可提交 |
| `workflow/torrent_sources/linode.local.json` | ❌ `.gitignore` 忽略，勿提交 |

**切勿**把真实 Token 写入 example、文档或其它会提交的文件。

### 2.3 安装依赖

在任意机器（不必在 ReleaseMatch 仓库内）：

```bash
pip install -r workflow/torrent_sources/requirements-linode.txt
# 或：
pip install 'linode_api4>=5.0.0'
```

---

## 三、脚本用法（人工 CLI）

在仓库根目录 `releasematch/` 下，或进入同目录：

```bash
# 创建：日本大阪 Nanode + Debian 12
python workflow/torrent_sources/linode_vps.py create \
  --region jp-osa \
  --type g6-nanode-1 \
  --image linode/debian12 \
  --label jackett-jp

# 查询 IP
python workflow/torrent_sources/linode_vps.py ip --label jackett-jp

# 列出全部
python workflow/torrent_sources/linode_vps.py list

# 删除（需 --yes 确认）
python workflow/torrent_sources/linode_vps.py delete --label jackett-jp --yes
```

也可先 `cd workflow/torrent_sources` 后直接 `python linode_vps.py ...`。

### 3.1 枚举可用参数（推荐先跑）

`create` 的 `--region` / `--type` / `--image` 取值来自 Linode API，用 `params` 实时枚举（首列 `id` 即可传入 create）：

```bash
# 全部：regions + types + images
python workflow/torrent_sources/linode_vps.py params

# 只看区域 / 机型 / 镜像
python workflow/torrent_sources/linode_vps.py params --kind region
python workflow/torrent_sources/linode_vps.py params --kind type
python workflow/torrent_sources/linode_vps.py params --kind image

# 关键字过滤
python workflow/torrent_sources/linode_vps.py params --kind region --region-filter jp
python workflow/torrent_sources/linode_vps.py params --kind type --type-filter nanode
python workflow/torrent_sources/linode_vps.py params --kind image --vendor debian --image-filter 12

# 机器可读（外部调用）
python workflow/torrent_sources/linode_vps.py params --kind type --json | jq '.types[].id'
```

镜像默认只列 **公开且未废弃**；加 `--all-images` 可含私有/废弃镜像。

常用参考值（以 `params` 实时结果为准；**仓库默认**已是日本最低档）：

| 用途 | 参数值 | 说明 |
|------|--------|------|
| **默认机型（约 $5/月）** | `--type g6-nanode-1` | Nanode 1GB：1 vCPU / 1GB / 25GB SSD |
| **默认区域（日本）** | `--region jp-osa` | Osaka |
| **默认镜像** | `--image linode/debian12` | Debian 12 |
| 美国东部 | `--region us-east` | |
| Ubuntu 22.04 | `--image linode/ubuntu22.04` | |

---

## 四、外部程序调用约定

脚本设计为 **无项目内依赖**（不 import `workflow.*`），适合 cron、CI、其他语言子进程调用。

### 4.1 机器可读输出：`--json`

所有子命令支持 `--json`，成功时 stdout **仅一行 JSON**（便于 `jq` / 解析），诊断信息走 stderr。

**create 成功示例：**

```json
{
  "ok": true,
  "action": "create",
  "id": 12345678,
  "label": "jackett-jp",
  "region": "jp-osa",
  "type": "g6-nanode-1",
  "status": "running",
  "ipv4": "203.0.113.10",
  "ipv4_list": ["203.0.113.10"],
  "root_pass": "auto-generated-or-provided",
  "ssh": "ssh root@203.0.113.10"
}
```

**ip / list / delete** 字段同理，均含 `"ok": true|false` 与 `"action"`。

### 4.2 退出码

| 码 | 含义 |
|----|------|
| `0` | 成功 |
| `1` | 业务失败（未找到实例、API 错误、等待超时等） |
| `2` | 参数 / 环境错误（缺 Token、缺 `--id`/`--label`、缺 `--yes`） |

### 4.3 Shell 调用示例

```bash
#!/usr/bin/env bash
set -euo pipefail
export LINODE_TOKEN="..."

OUT=$(python /path/to/linode_vps.py create \
  --region jp-osa --type g6-nanode-1 --label auto-$(date +%s) \
  --json)
IP=$(echo "$OUT" | jq -r .ipv4)
PASS=$(echo "$OUT" | jq -r .root_pass)
ID=$(echo "$OUT" | jq -r .id)

echo "IP=$IP PASS=$PASS"
# 后续：SSH 装机 / Jackett oneclick …
# bash scripts/install_jackett_oneclick.sh --host "$IP" --password "$PASS"

# 用完销毁
python /path/to/linode_vps.py delete --id "$ID" --yes --json
```

### 4.4 Python 子进程示例

```python
import json
import os
import subprocess

env = os.environ.copy()
# env["LINODE_TOKEN"] = "..."  # 或已在环境中

proc = subprocess.run(
    [
        "python",
        "workflow/torrent_sources/linode_vps.py",
        "create",
        "--region", "jp-osa",
        "--type", "g6-nanode-1",
        "--label", "ext-caller",
        "--json",
    ],
    capture_output=True,
    text=True,
    env=env,
    check=False,
)
if proc.returncode != 0:
    raise RuntimeError(proc.stderr or proc.stdout)
data = json.loads(proc.stdout)
print(data["ipv4"], data["root_pass"], data["id"])
```

### 4.5 与 Jackett 一键装机衔接

**推荐（脚本已集成买机/销毁）：**

```bash
bash scripts/install_jackett_oneclick.sh --provision-linode --with-indexers
bash scripts/install_jackett_oneclick.sh --destroy-linode
```

**Ops ⑤ 配置（与脚本模式对齐）：**

| UI | 实际脚本参数 |
|----|----------------|
| 「一键部署 Jackett」+ 填 Host | `--host …`（装/重装，不买机） |
| 「一键部署 Jackett」+ 勾选「先开通 Linode」 | `--provision-linode`（买机+装栈） |
| 「Linode VPS 增删」开通 / 销毁 | `linode_vps.py create\|delete`；开通可勾选顺带 provision |

开通/销毁均为后台任务：Ops 顶部进度条 + 卡片内 `phases[]` 分项表 + 滚动日志；轮询 `GET /api/linode/progress`。销毁走 `POST /api/linode/delete/start`（须 `confirm:true`）。

同 `defaults.label` 已存在时开通会失败，需先销毁。

**分步（等价）：**

```text
linode_vps.py create --json
        │  ipv4 + root_pass
        ▼
install_jackett_oneclick.sh --host <ipv4> --password <root_pass>
        │
        ▼
（可选）linode_vps.py delete --id <id> --yes
```

详见 [jackett-remote-linode.md](./jackett-remote-linode.md) §零。

---

## 五、参数一览

```text
python workflow/torrent_sources/linode_vps.py <subcommand> [options]

子命令：
  create | ip | list | delete | params | defaults

全局：
  --json              stdout 输出单行 JSON
  --config PATH       指定 linode.local.json（默认自动查找）
  LINODE_TOKEN        可选；若设置则覆盖本地 config 中的 token
  linode.local.json   本地 Token / defaults.label / defaults（已 gitignore）

defaults：
  （无额外参数；输出 label/region/type/image，不调 API）

params：
  --kind KIND         all | region | type | image（默认 all）
  --region-filter S   区域关键字
  --type-filter S     机型关键字
  --image-filter S    镜像关键字
  --vendor VENDOR     镜像厂商过滤（debian / ubuntu …）
  --all-images        含私有/已废弃镜像

create：
  --type TYPE         默认 g6-nanode-1
  --region REGION     默认 jp-osa
  --image IMAGE       默认 linode/debian12
  --label LABEL       省略则用 config.defaults.label，再否则 rm-linode-<unix_ts>
  --root-pass PASS    可选；省略则由 API/SDK 生成并写入 JSON
  --ssh-key PUBKEY    可选；注入 authorized_keys
  --wait-seconds N    等待 running 超时，默认 180
  --no-wait           创建后不等待（可能尚未 running）

ip / delete：
  --id ID             实例数字 ID
  --label LABEL       实例标签（与 --id 二选一）
  delete 额外：--yes  必须显式确认

list：
  （无额外参数）
```

---

## 六、纯 curl 对照（不装 SDK 时）

```bash
# 创建
curl -s -X POST https://api.linode.com/v4/linode/instances \
  -H "Authorization: Bearer $LINODE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "g6-nanode-1",
    "region": "jp-osa",
    "image": "linode/debian12",
    "label": "auto-vps",
    "root_pass": "ChangeMe_Complex_Pass1!"
  }'

# 详情 / IP
curl -s -H "Authorization: Bearer $LINODE_TOKEN" \
  "https://api.linode.com/v4/linode/instances/${ID}"

# 删除
curl -s -X DELETE -H "Authorization: Bearer $LINODE_TOKEN" \
  "https://api.linode.com/v4/linode/instances/${ID}"
```

官方文档：[Linode API v4](https://techdocs.akamai.com/linode-api/reference/api) · Python SDK：[linode_api4](https://github.com/linode/linode_api4-python)

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-07-25 | 初版：文档 + 独立脚本 `linode_vps.py`（create/ip/list/delete，`--json` 外部调用） |
| 2026-07-25 | Token 支持本地 `linode.local.json`（`.gitignore`，不上传 GitHub）；env 仍可覆盖 |
| 2026-07-25 | 脚本与配置迁至同目录 `workflow/torrent_sources/` |
| 2026-07-25 | 新增 `params`：枚举 create 可用 region/type/image |
| 2026-07-25 | §2.1 补充 API Token Access 三级权限、本脚本推荐勾选、OAuth scope 全表 |
| 2026-07-25 | `linode.local.json` 增加 `defaults.ssh.password`，与 `servers.local.json` 对齐 |
| 2026-07-25 | `install_jackett_oneclick.sh` 集成 `--provision-linode` / `--destroy-linode` |
| 2026-07-25 | `defaults.label` 写入 linode.local.json；新增 `defaults` 子命令；一键脚本不再写死 label |
