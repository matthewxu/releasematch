# Stremio 插件 — 价值分析报告

> **版本：** v1.0
> **创建日期：** 2026-07-01
> **关联轨道：** T4-1（Stremio 插件）
> **关联文档：** [01-分支定位与流量获取.md](../download-resources/01-分支定位与流量获取.md)、[08-浏览器磁力插件评估报告.md](./08-浏览器磁力插件评估报告.md)
> **代码目录：** `releasematch/portal/api/`

---

## 目录

| 章节 | 主题 |
|------|------|
| 一 | Stremio 平台概览 |
| 二 | Torrentio 现状与缺口 |
| 三 | ReleaseMatch 插件的核心差异化 |
| 四 | 五大价值维度 |
| 五 | 三大关键局限 |
| 六 | 与浏览器扩展的关系 |
| 七 | 综合定位 |
| 八 | 分阶段执行建议 |

---

## 一、Stremio 平台概览

| 指标 | 数据 | 来源 |
|------|------|------|
| 月访问量 | **15.33M** | Semrush May 2026 |
| 总 Android 下载 | **31M+** | AppBrain |
| 声称总用户 | **30M+** | Smart Code Ltd 官方 |
| 月新增下载 | **~600K** | 同上 |
| 平均会话时长 | **7 分 27 秒** | Semrush（极高粘性） |
| 引用域 | **5,820** | Semrush |
| 热门 addon 数 | 100+ | Stremio Addons 社区 |

Stremio 是目前 **全球最大的开源流媒体壳层**，月活跃用户量级超过很多知名流媒体平台的第三方客户端。核心架构是「媒体播放器壳层 + 社区开发的第三方 addon 插件」——Stremio 本身不持有任何内容，所有数据源来自 addon。

---

## 二、Torrentio 现状与缺口

### 2.1 Torrentio 是什么

Torrentio 是目前 Stremio 上最流行的 torrent 类 addon。它抓取 24 个公开 tracker（YTS、EZTV、1337x、TPB、Nyaa 等），返回 magnet 流列表供用户播放。

### 2.2 Torrentio 的问题

| 问题 | 具体表现 | 用户影响 |
|------|---------|---------|
| **无推荐逻辑** | 每个流仅标注 resolution 和 size，无推荐、无 cross-source 验证、无 Group 信誉 | 用户需从几十个结果中手动选——大部分直接无脑选 seeders 最多的 |
| **稳定性差** | 官方实例频繁掉线 | 社区大量推荐 Comet/MediaFusion 作为备选 |
| **结果排序低效** | 仅按 resolution/seeders 排序 | 好 release 和差 release 混在一起 |
| **无 Debrid 依赖的体验差** | 不加 Debrid 直接播放原始 magnet 速度不稳定 | 新手用户体验差 |

### 2.3 生态缺口

当前 Stremio torrent addon 生态的格局：

```
Torrentio（最流行）
  └─ 抓取 20+ tracker → resolution/size 标注 → 用户自己选

Comet / MediaFusion / Knightcrawler（备选）
  └─ 模式同上，数据源略有差异

结论：整个 Stremio addon 生态里，没有一个 addon 做「release 推荐」。
```

---

## 三、ReleaseMatch 插件的核心差异化

### 3.1 流条目对比

```
Torrentio 返回的流条目：
  ⬜ Breaking.Bad.S04E06.1080p.WEB-DL.GROUP-X   2.4 GB   24 seeders
  ⬜ Breaking.Bad.S04E06.720p.WEB-DL.GROUP-Y     1.1 GB   18 seeders
  （用户自己选——通常无脑选 seeders 最多的）

ReleaseMatch addon 返回的流条目：
  ⭐ Recommended: GROUP-X  1080p WEB-DL  2.4 GB  24 seeders
     理由：Scene 合规；Amazon Prime US WEB-DL；跨源 3/3 验证
     Group badge：A 级 · 测速 4.2 MB/s
  ⬜ GROUP-Y  720p WEB-DL  1.1 GB  18 seeders
  （用户看到推荐 → 直接点 Recommended）
```

### 3.2 差异化汇总

| 维度 | Torrentio | ReleaseMatch addon |
|------|-----------|-------------------|
| 数据源 | 20+ tracker 原始抓取 | 同样 20+ 源，但经 cross-source 验证 |
| 推荐 | ❌ 无 | ✅ 有，scorer 驱动 |
| Group 信誉 | ❌ 无 | ✅ L0~L4 标注 |
| 稳定性 | ⚠️ 有时不可用 | Cloudflare Worker 部署，可控 |
| 结果排序 | 按 resolution/seeders | 按推荐评分（`score_item`） |
| 频道模式 | 目录 + 搜索频道 | 可创新「Recommended Release」频道 |

---

## 四、五大价值维度

### 价值 1：用户覆盖（最高）

这是 Stremio 插件最独特的东西。浏览器扩展需要用户主动搜索、安装、配置 qBittorrent；Stremio 插件的安装门槛是 **点击一个链接 → 自动打开 Stremio → 确认安装**——两步，零配置。

```
用户触达路径对比：

浏览器扩展：
  CWS 搜索 / 本站推荐 → 下载扩展 → 配置 Web UI 地址和密码
  → 配置 qBittorrent → 开始使用
  流失率：每一步都有可能流失 30~50%

Stremio 插件：
  Reddit 推荐 / GitHub → 点击 Install 链接 → 自动弹出 Stremio → 确认
  → 直接在目录和搜索结果中出现
  流失率：远低于扩展
```

Torrentio 已经有数百万用户——说明 Stremio 用户对「安装一个 magnet 类 addon」没有心理障碍。ReleaseMatch addon 不需要教育市场，只需要告诉用户「有一个比 Torrentio 更好的选择」。

### 价值 2：直接曝光（抢占流选择入口）

Stremio 用户在播放器中选流时，面对的是几十个无差别的 magnet。推荐标记直接出现在流选择界面——这是无法跳过的高频触达。

**频道模式的溢出价值：** Stremio addon 支持 Catalog（目录）频道。Torrentio 提供了目录流，ReleaseMatch 可以做 **「本周 Recommended Release」频道**——展示本站评分最高的近期 release。这是纯推广位置，不需要用户主动搜索就能看到。

### 价值 3：外链与品牌建设

```
外链路径：
  ├── GitHub 仓库 README           → dofollow
  ├── Stremio addon 官方列表       → dofollow
  ├── Reddit r/StremioAddons       → nofollow 但高流量 referral
  └── addon 配置页面               → dofollow
```

相比浏览器扩展（CWS dofollow），Stremio addon 的外链价值略低但更分散。更重要的是 Stremio 社区的口碑传播——`r/StremioAddons` 有数十万订阅者，一个 good addon 的推荐帖能带来持续的有机流量。

### 价值 4：对 ReleaseMatch 网站的直接回馈

| 回馈维度 | 强度 | 方式 |
|---------|------|------|
| 直接 UV | **中~高** | 流详情页嵌入「View source on ReleaseMatch.io」链接 |
| 品牌认知 | **高** | 用户每周在 Stremio 里几十次看到「ReleaseMatch」推荐标记 |
| 测速数据 | **低** | Stremio 内置 BT 引擎没有公开 API，无法轮询测速 |
| 推荐引擎验证 | **中** | 通过用户点击率间接验证推荐质量 |

### 价值 5：开发成本极低

Stremio Addon SDK 的要求极简——可以任意语言编写（官方 SDK 是 Node.js，但协议是纯 HTTP），只需实现两个端点：

```
┌─ /manifest.json        → 描述 addon 名称、logo、频道
└─ /stream/{type}/{id}   → 返回给定 TMDB ID 的流列表
```

ReleaseMatch 的 **`/api/v1/sources?tmdb=&s=&e=`** 接口已经存在（T3 已完成 D1 sync Worker）。Stremio addon 本质上就是对这个接口的 HTTP 包装：

```json
// Stremio addon 的 /stream/series/tt... 响应格式
{
  "streams": [
    {
      "url": "magnet:?xt=urn:btih:...",
      "title": "⭐ Recommended: GROUP-X 1080p WEB-DL (跨源 3/3)",
      "infoHash": "...",
      "behaviorHints": {
        "notWebReady": false
      }
    }
  ]
}
```

只需要把 `scorer.py` 的输出映射到 Stremio 的 stream 格式，不需要额外数据管道。**估时 3~5 天**，其中 2 天是 Worker 部署和 Central 发布流程。

**已有基础设施复用：**

| 组件 | 状态 | Stremio addon 是否依赖 |
|------|------|----------------------|
| `/api/v1/sources` Worker | T3 已完成 | ✅ 直接复用 |
| D1 `download_resources` 表 | 已建 | ✅ 数据来源 |
| `scorer.py` 推荐引擎 | 已建 | ✅ 推荐逻辑来源 |
| CF Pages + Workers | 已配置 | ✅ 零额外部署成本 |

---

## 五、三大关键局限

### 局限 1：无 Debrid 集成 = 体验降级

大部分 Stremio 重度用户使用 `Real-Debrid + Torrentio` 组合。如果 ReleaseMatch addon 不支持 Debrid，用户看到的是原始 magnet，需要等 Stremio 内置 BT 下载后才能播放。这比 Debrid 缓存流的「秒开」体验差很多。

| Debrid 服务 | 月费 | 用户量级 |
|------------|------|---------|
| Real-Debrid | ~€4.99 | 最大 |
| AllDebrid | ~€4.10 | 中 |
| Premiumize | ~€9.99 | 小 |
| TorBox | ~$5.00 | 中 |

**应对策略：**

- v1 不做 Debrid 集成，在 addon 描述里明确标注「Debrid integration coming soon」
- v2 增加用户配置项（API Key 作为用户设置），流选择时优先返回 Debrid 缓存流
- Debrid 集成本身不复杂——用用户提供的 API Key 调 Debrid API 添加 magnet，改写 `url` 为 Debrid 直链

### 局限 2：无法收集测速数据

浏览器扩展最大的回馈——测速——在 Stremio 场景下不可行。Stremio addon 是纯数据提供器，不运行在用户本地，无法轮询 Stremio 内置 BT 引擎的速度。

| 数据来源 | 浏览器扩展 | Stremio 插件 |
|---------|-----------|-------------|
| 测速数据 | ✅ 核心能力 | ❌ 不可行 |
| 品牌曝光 | 中（安装后） | ✅ 高（播放器中高频出现） |
| 推荐引擎反馈 | ✅ 可测量 | ✅ 可测量 |

**应对策略：** Stremio addon 的目标是品牌曝光和推荐验证，测速交给扩展。

### 局限 3：依赖 Stremio 平台政策

Stremio 官方随时可能调整 addon 审核策略。但目前 addon 生态是开放的，无审核门槛，发布到 Central 只需调用 `publishToCentral` CLI。

**风险等级：低。**

---

## 六、与浏览器扩展的关系

### 6.1 战略价值对比

```
                      Stremio 插件          浏览器扩展
                      ────────────          ────────────
开发时间              3~5 天                11 天
用户触达门槛          低（点击即装）          中（需配置 qB）
目标用户规模          30M Stremio 用户        170M P2P 用户
差异化展示            直接在流列表中           弹窗 + 页面
测速数据回馈           ❌ 不可行               ✅ 核心能力
外链价值              中~高（GitHub + 社区）   高（CWS dofollow）
品牌曝光              高（每周几十次看到）      中（安装后才看到）
安装量天花板          高（Torrentio 级别）     中（CWS 搜索流量有限）
推荐引擎验证           ✅ 可测量点击率          ✅ 可测量
发布维护成本          低（Worker 即可）        中（CWS 审核 + 多浏览器）
```

### 6.2 不是替代关系，是互补关系

```
Stremio 插件 → 先发，5 天出效果
  目的：品牌曝光 + 推荐引擎验证
  数据：不依赖测速
  分发：Stremio Central + Reddit + GitHub

浏览器扩展 → 后发，11 天
  目的：测速数据回传 + CWS 外链
  数据：核心依赖测速
  分发：Chrome Web Store + Firefox Add-ons + 本站

共享层：
  └─ /api/v1/sources    （数据接口）
  └─ scorer.py           （推荐逻辑）
  └─ D1 download_resources（存储）
```

两者共用同一套后端数据和推荐引擎，不存在重复开发。

---

## 七、综合定位

### 7.1 一句话定位

> Stremio 插件是 **用户触达最快、安装门槛最低** 的渠道，能在 5 天内让 ReleaseMatch 的推荐出现在 30M Stremio 用户的播放器中。它不是测速数据的来源，但它是品牌曝光和推荐引擎验证的最优路径。

### 7.2 发布顺序建议

```
W7~8    T3 生成器收尾 → 确认 /api/v1/sources 接口稳定
        └─ 花 1 天写 Stremio addon Worker（~50 行核心逻辑）

W9~10   Stremio addon 发布
        ├── 发布到 GitHub（开源 MIT）
        ├── publishToCentral → 出现在 Stremio addon 目录
        ├── Reddit r/StremioAddons 发布帖
        └── 开始收集用户点击数据

W10~12  C3 沙盒期（不增 SEO 页）
        └─ 观察 addon 使用数据，迭代推荐逻辑

W12+    启动浏览器扩展开发（11 天）
        Stremio addon 的 API 与扩展共享
```

**Stremio 先于浏览器扩展**——不是因为扩展不重要，而是因为 Stremio 可以 5 天出效果，扩展需要 11 天，且两者不冲突。

### 7.3 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Torrentio 加推荐功能 | **低** | 中 | 数据管道（四源 + scorer）深度不低，持续迭代 |
| Stremio 官方调整 addon 策略 | **低** | 中 | 开源 + Worker 部署可控，不依赖官方分发 |
| Debrid 不集成导致体验差 | **中** | 中 | v1 明确标注，v2 快速跟进 |
| 用户量不足 | **低** | 低 | 1 天发布到 Central，零成本试水 |

---

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-01 | 初版：平台数据、竞品分析、五维价值评估、与浏览器扩展对比 |
