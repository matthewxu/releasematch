# 日韩剧直连源与 SSH SOCKS 隧道

> **Layer 2D：** Nyaa Live Action（`c=4_0`）  
> **隧道：** 本机 `ssh -D` SOCKS5，经日本 VPS 出口访问 Nyaa  
> **日期：** 2026-06-30

---

## 架构

```
本机 FetchService
    │
    ├─ original_language=ko/ja ──► NyaaLiveActionClient (c=4_0)
    │         │                        │
    │         │ 直连 nyaa.si           │
    │         └─ 失败 ──► SOCKS5 ──────┘
    │                    (ssh -D 127.0.0.1:1080)
    └─ Jackett nyaasi / thepiratebay（日韩 indexer 路由）
```

| 组件 | 文件 |
|------|------|
| Live Action 客户端 | `workflow/torrent_sources/nyaa_live_action_client.py` |
| 区域路由 | `workflow/torrent_sources/asia_region.py` |
| 代理回退 | `workflow/torrent_sources/http_fetch.py` |
| 编排 | `workflow/torrent_sources/fetch_service.py` |

**无需在 VPS 上部署 Squid/tinyproxy** — SSH 动态转发即提供 SOCKS5 出口。

---

## 配置（accounts.local.json）

```json
"proxy": {
  "enabled": true,
  "url": "socks5h://127.0.0.1:1080",
  "use_when_direct_fails": true
},
"nyaa_live_action": {
  "enabled": true,
  "category": "4_0"
},
"jackett": {
  "indexers": {
    "kr_tv": ["nyaasi", "thepiratebay"],
    "jp_tv": ["nyaasi", "thepiratebay"]
  }
}
```

环境变量（优先级更高）：

```bash
export TORRENT_PROXY=socks5h://127.0.0.1:1080
```

使用 `socks5h://`（DNS 经 VPS 解析），勿用 `socks5://`。

---

## 本机 SSH SOCKS 隧道

```bash
# 方式 1：脚本
bash scripts/start_ssh_socks_tunnel.sh

# 方式 2：手动
ssh -N -D 127.0.0.1:1080 root@172.238.15.236
export TORRENT_PROXY=socks5h://127.0.0.1:1080
```

依赖：`pip install PySocks`（已在 requirements.txt）。

---

## 测试

```bash
# 先开隧道，再测
bash scripts/start_ssh_socks_tunnel.sh

python -m workflow.torrent_sources.run test --tmdb 93405 --season 1 --episode 1 --force
python -m workflow.torrent_sources.run test --tmdb 94796 --season 1 --episode 1 --force
python -m workflow.torrent_sources.run test --tmdb 110316 --season 1 --episode 1 --force
```

---

## standalone Demo 映射

| TMDB | 作品 | 本地标题 |
|------|------|----------|
| 93405 | Squid Game | `오징어 게임` |
| 94796 | Crash Landing on You | `사랑의 불시착` |
| 110316 | Alice in Borderland | `今際の国のアリス` |

见 `workflow/metadata/external_ids.py` `_STANDALONE_MAP`。

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-30 | 初版：Nyaa LA 直连 + VPS 代理回退 + 日韩路由 |
| 2026-06-30 | 移除 VPS Squid；改本机 SSH `-D` SOCKS5 隧道 |
