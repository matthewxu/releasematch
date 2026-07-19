# ReleaseMatch 方案文档索引

本目录代码的 **产品、SEO、数据源、优先级** 方案文档位于仓库上级 `download-resources/`：

| 文档 | 说明 |
|------|------|
| [01-分支定位与流量获取.md](../../download-resources/01-分支定位与流量获取.md) | 独立域名 SEO、IG、冷启动 |
| [02-数据源技术方案-详细展开.md](../../download-resources/02-数据源技术方案-详细展开.md) | 四层数据源、接口规格 |
| [03-工作流集成与模块规划.md](../../download-resources/03-工作流集成与模块规划.md) | 原规划（已迁移至本目录，见 §隔离说明） |
| [04-方案全景分析与优先级重评.md](../../download-resources/04-方案全景分析与优先级重评.md) | **T0~T5 + C0~C4 双轨（v1.1，当前生效）** |
| [05-存储与部署配置.md](./05-存储与部署配置.md) | **MySQL 本地测试 → D1 生产、环境变量、总控 CLI** |
| [**IG信息登记册.md**](./IG信息登记册.md) | **Information Gain 分级登记册（S/A/B/C + 跨源/Group/测速逻辑）** |
| [05-Jackett详解与安装使用教程.md](./05-Jackett详解与安装使用教程.md) | **Jackett 概念、安装、Torznab API、ReleaseMatch 集成** |
| [06-run-cli使用说明.md](./06-run-cli使用说明.md) | **workflow.run 总控命令完整参考**（含 **`ops serve`** / **`ops tmdb-sync`** / **配置热加载**：`.env` + accounts） |
| [07-部署架构解疑.md](./07-部署架构解疑.md) | **D1 / Pages / Worker generate / CI 部署 FAQ** |
| [jackett-remote-linode.md](./jackett-remote-linode.md) | **海外 VPS 部署 Jackett**（通用流程；当前测试机 `172.236.156.193`） |
| [**VPS迁移与部署.md**](./VPS迁移与部署.md) | **当前测试 VPS** `172.236.156.193` 迁移与验收 |
| [jackett-stability.md](./jackett-stability.md) | **Jackett / 拉取稳定性保障**（配置、healthcheck、验收） |
| [nyaa-proxy-asia.md](./nyaa-proxy-asia.md) | **日韩剧 Nyaa LA 直连 + SSH SOCKS 隧道回退** |
| [09-Stremio插件价值分析.md](./09-Stremio插件价值分析.md) | **Stremio 平台用户规模、竞品缺口、插件差异化与执行路线** |
| [**10-稀缺槽与用户求片通知方案.md**](./10-稀缺槽与用户求片通知方案.md) | **稀缺槽产品化 + 用户求片 / 定时爬取 / 通知（规划稿，暂不开发）** |
| [**11-CN华语影视资源方案.md**](./11-CN华语影视资源方案.md) | **华语影视**：全球市场摘要、DMHy Layer 2F、`cn` 路由、渠道矩阵、PoC |
| [**全球SEO流量定位.md**](./全球SEO流量定位.md) | **全球影视资源视角：意图分层、市场、关键词簇、选槽与流量组合** |
| [11-页面SEO分析与优化方向.md](./11-页面SEO分析与优化方向.md) → [worklog](../worklogs/2026-07-03/页面SEO分析与优化方向.md) | **全站 SEO 审计 + C2 任务清单（2026-07-03 工作日志）** |
| [**12-日常运营执行手册.md**](./12-日常运营执行手册.md) | **日常运维**：巡检、cron、扩槽→生成→SEO 门禁、失败槽、指标看板 |
| [**15-多地多环境开发切换.md**](./15-多地多环境开发切换.md) | **两地 Mac/Windows**：私有仓同步代码+密钥、收工/开工清单 |
| [**checklists/**](../checklists/README.md) | **运营 Checklist**：上线门禁、每日/每周/发版前可勾选清单 |
| [**seo/**](./seo/INDEX.md) | **SEO 迭代专项**：E-E-A-T / Info Gain 评估、跟进看板、历次迭代记录 |
| [**portal/UI国际化方案.md**](./portal/UI国际化方案.md) | **页面 UI 国际化（en/zh）**：配置、架构、dynamic 切换、Trust 生成 |
| [**parallel/大陆站影视资源数据源技术方案.md**](./parallel/大陆站影视资源数据源技术方案.md) | **平行项目 v0.6**：有效覆盖率 · **不限于网盘、优先网盘** · 插件化 · 全自动 |

**隔离说明：** `03` 文档中 `tmdbpy/workflow/torrent_sources/`、`subtitle-portal` 路由等路径已废弃，以 `releasematch/` 为准。
