# ReleaseMatch 浏览器扩展（占位）

> **路径：** `releasematch/extension/`  
> **优先级：** T4-3（Stremio T4-1 完成后）  
> **方案文档：** [01-分支定位与流量获取.md §5.4.2](../download-resources/01-分支定位与流量获取.md)

---

## 规划能力

- magnet: 协议拦截 → 转发 qBittorrent Web API
- 下载进度面板
- opt-in 社区测速数据回传 → 本站 D1 API

## 目标结构（R4 创建）

```
extension/
├── manifest.json          # Chrome MV3
├── background.js          # Service Worker
├── popup/
│   └── index.html
├── options/
└── README.md
```

## 与字幕站关系

**无关联。** 扩展仅与 `releasematch.io` 域通信（`host_permissions`）。
