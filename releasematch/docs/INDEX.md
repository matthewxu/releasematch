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
| [06-run-cli使用说明.md](./06-run-cli使用说明.md) | **workflow.run 总控命令完整参考** |
| [07-部署架构解疑.md](./07-部署架构解疑.md) | **D1 / Pages / Worker generate / CI 部署 FAQ** |
| [jackett-remote-linode.md](./jackett-remote-linode.md) | **海外 VPS 部署 Jackett**（通用流程；历史 IP `104.105.140.11`） |
| [**VPS迁移与部署.md**](./VPS迁移与部署.md) | **当前生产 VPS** `172.238.15.236` 迁移与验收 |
| [jackett-stability.md](./jackett-stability.md) | **Jackett / 拉取稳定性保障**（配置、healthcheck、验收） |
| [nyaa-proxy-asia.md](./nyaa-proxy-asia.md) | **日韩剧 Nyaa LA 直连 + SSH SOCKS 隧道回退** |
| [09-Stremio插件价值分析.md](./09-Stremio插件价值分析.md) | **Stremio 平台用户规模、竞品缺口、插件差异化与执行路线** |
| [**10-稀缺槽与用户求片通知方案.md**](./10-稀缺槽与用户求片通知方案.md) | **稀缺槽产品化 + 用户求片 / 定时爬取 / 通知（规划稿，暂不开发）** |
| [**全球SEO流量定位.md**](./全球SEO流量定位.md) | **全球影视资源视角：意图分层、市场、关键词簇、选槽与流量组合** |
| [**11-页面SEO分析与优化方向.md**](./11-页面SEO分析与优化方向.md) → [worklog](../worklogs/2026-07-03/页面SEO分析与优化方向.md) | **全站 SEO 审计 + C2 任务清单（2026-07-03 工作日志）** |

**隔离说明：** `03` 文档中 `tmdbpy/workflow/torrent_sources/`、`subtitle-portal` 路由等路径已废弃，以 `releasematch/` 为准。
