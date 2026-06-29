# ReleaseMatch 方案文档索引

本目录代码的 **产品、SEO、数据源、优先级** 方案文档位于仓库上级 `download-resources/`：

| 文档 | 说明 |
|------|------|
| [01-分支定位与流量获取.md](../../download-resources/01-分支定位与流量获取.md) | 独立域名 SEO、IG、冷启动 |
| [02-数据源技术方案-详细展开.md](../../download-resources/02-数据源技术方案-详细展开.md) | 四层数据源、接口规格 |
| [03-工作流集成与模块规划.md](../../download-resources/03-工作流集成与模块规划.md) | 原规划（已迁移至本目录，见 §隔离说明） |
| [04-方案全景分析与优先级重评.md](../../download-resources/04-方案全景分析与优先级重评.md) | **T0~T5 + C0~C4 双轨（v1.1，当前生效）** |
| [05-存储与部署配置.md](./05-存储与部署配置.md) | **MySQL 本地测试 → D1 生产、环境变量、总控 CLI** |
| [06-run-cli使用说明.md](./06-run-cli使用说明.md) | **workflow.run 总控命令完整参考** |

**隔离说明：** `03` 文档中 `tmdbpy/workflow/torrent_sources/`、`subtitle-portal` 路由等路径已废弃，以 `releasematch/` 为准。
