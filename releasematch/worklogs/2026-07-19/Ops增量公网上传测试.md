# Ops 增量公网上传测试 · 2026-07-19

> 目标域：`https://www.releasematch.com`（本机可直连，未使用 SSH 隧道）  
> 方式：Ops API `scope=incremental|upload_only` + `upload=true`

## 结论

| 场景 | 结果 | 证据 |
|------|------|------|
| **更新** | ✅ | Friends/Whiplash 增量 bake + wrangler 上传 2 文件；公网 HTML sha 变化 |
| **新增** | ✅ | canary `/_ops_canary_rm_test/` 上传后 `.com` **200** 且含 marker |
| **删除** | ✅ | dist 去掉 canary 后再 upload；`.com` **404** |

Workers.dev 本机探测超时（与 `.com` 无关）；验收以 `.com` 为准。

## 更新（选中槽）

- 批次：`20260719T091241Z-c2579576`（Friends S01E01 + Whiplash）
- `POST /api/actions/deploy` `{scope:incremental, upload:true}` → wrangler ok
- 上传：`/friends/s1e1/index.html`、`/whiplash/index.html`（2 new，139 already）
- 公网：两页仍 200；内容 hash 已变（`sha_changed: true`）

## 新增 / 删除（canary）

1. 写入 `portal/dist/_ops_canary_rm_test/index.html` → `upload_only` + upload  
2. `https://www.releasematch.com/_ops_canary_rm_test/` → **200** + marker  
3. 删除 dist 目录 → `upload_only` + upload（Version `2f25a0b4-…`）  
4. 同 URL → **404**

说明：首次 canary 探测曾遇 CF 缓存/竞态短暂 404；重试后 `.com` / apex 均 200。

## 原始日志

- `worklogs/2026-07-19/ops-incremental-public-deploy-test.json`（首轮；canary 初检失败后已人工复验通过）
