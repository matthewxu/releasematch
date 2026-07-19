# Ops UI 功能测试报告 · 2026-07-19

> 方式：本机 `ops serve :8090` + API 镜像 UI 动作；登录页浏览器目视。  
> 未执行：正式 wrangler 公网上传（勾选「正式上传」）。

## 环境

- Ops：`http://127.0.0.1:8090/`（`.venv`）
- 活跃批次：`20260719T091241Z-c2579576`（Friends + Whiplash，2 槽）
- 修复：`workflow.run ops serve` 缺少 `serve_ops` 别名 → 已补 `serve_ops = run_ops_server`

## 结果摘要

**12 / 12 PASS**（见 `ops-ui-smoke-test.json`）

| 段 | 测项 | 结果 |
|----|------|------|
| 登录 | `/login.html` 表单；错密 401；正密 Cookie | ✅ |
| 门禁 | 未登录 API → 401 | ✅ |
| ① | `/api/source/files` | ✅ |
| 状态 | `/api/state` 批次 2 槽均选中 | ✅ |
| ③ | Generate 选中槽 → ok=2 · Hub `tv:1668:hub` | ✅ |
| ③ | refresh-gates | ✅ |
| ④ UI | 增量/全量/仅上传 + `btnDeployRun` + 正式上传勾选 | ✅ |
| ④ | 增量 deploy `upload=false` | ✅ |
| ④ | 非法 scope 拒绝 | ✅ |
| ④ | `upload_only` + 不上传 | ✅ |
| ⑤ | `/api/config` | ✅ |
| JS | deploy 确认文案 / scope | ✅ |

## 浏览器

- 登录页截图确认：标题、密码框、「登录」、会话说明正常。
- 因会话 Cookie 为 HttpOnly，自动化未在浏览器内填密进入控制台（避免密码进工具日志）；控制台 DOM/API 已由登录后请求验证。

## 未测（刻意）

- [ ] 正式 wrangler deploy（公网）
- [ ] 全量 `generate all` prepare（耗时长）
- [ ] 一键 pipeline live fetch
- [ ] seo_c2 全量门禁（可另跑）

## 建议手工点一次

1. 打开 http://127.0.0.1:8090/login.html 登录  
2. ④ 上线：确认三档 radio 默认「增量」  
3. 不勾选「正式上传」→ 执行 Deploy → 日志 `scope=incremental upload=false`  
4. （可选）勾选正式上传再执行（会 confirm）
