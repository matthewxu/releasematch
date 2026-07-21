/**
 * Ops 控制台 — 操作旁路说明文档。
 *
 * 为每个主要操作提供：实现流程、脚本路径、完整命令、数据流、存储位置与排障提示，
 * 便于出问题时快速定位。挂载方式：按钮带 ``data-help="<key>"``，本文件注入「说明」按钮并打开抽屉。
 *
 * @file workflow/ops/static/ops-help.js
 */

(function (global) {
  "use strict";

  /**
   * 单条操作说明结构。
   * @typedef {Object} OpsHelpDoc
   * @property {string} title 标题
   * @property {string} [api] HTTP API
   * @property {string[]} flow 实现流程步骤
   * @property {string[]} [scripts] 代码 / 脚本路径（相对 releasematch/）
   * @property {string[]} [commands] 等价完整 CLI 命令
   * @property {string} [dataFlow] 数据流简述
   * @property {string[]} [storage] 读写落盘 / 表
   * @property {string[]} [troubleshoot] 常见问题定位
   */

  /**
   * 操作说明目录：key 对应按钮 ``data-help``。
   * @type {Object.<string, OpsHelpDoc>}
   */
  const HELP_CATALOG = {
    refresh: {
      title: "刷新状态",
      api: "GET /api/state",
      flow: [
        "读取进程内 WORKSPACE 快照（候选 / 筛选结果）",
        "加载活跃批次 load_active_batch() → ops_track_*",
        "附带台账统计 pages_service.inventory_stats()",
      ],
      scripts: [
        "workflow/ops/server.py",
        "workflow/ops/workspace.py",
        "workflow/ops/track_store.py",
        "workflow/ops/pages_service.py",
      ],
      commands: ["# 无直接 CLI；等价于打开 UI 后点「刷新状态」"],
      dataFlow: "MySQL ops_track_* + media_pages 统计 → JSON → 顶栏徽章 / 各段表格",
      storage: [
        "内存：WORKSPACE（重启丢失）",
        "MySQL：ops_track_batches / ops_track_slots",
        "MySQL：media_pages（统计）",
      ],
      troubleshoot: [
        "顶栏无活跃批次 → 先在②导入跟踪表或⓪加入跟踪批",
        "统计为 0 → 检查 .env 中 RM_RELEASE_MYSQL_* 与 db status",
      ],
    },

    inv_search: {
      title: "搜索台账",
      api: "GET /api/pages?q=&status=&page_type=&limit=&offset=",
      flow: [
        "pages_service.list_inventory() 查 MySQL media_pages",
        "可选附带最近 ops_track_slots 工单快照",
        "前端分页：offset = (page-1)*pageSize",
      ],
      scripts: ["workflow/ops/pages_service.py", "workflow/ops/server.py"],
      commands: [
        "# 无专用 list CLI；库内核对：",
        "python -m workflow.run db status",
      ],
      dataFlow: "查询参数 → media_pages → 表格行（含 magnet / Rec / path）",
      storage: [
        "真源：MySQL media_pages / download_resources",
        "静态路径字段指向 portal/dist/…",
        "工单快照：ops_track_slots（非统管）",
      ],
      troubleshoot: [
        "搜不到 → 确认搜的是已入库页，不是①的 TMDB 候选",
        "status/path 不对 → 看 media_pages.status 与 generated 路径是否一致",
      ],
    },

    inv_unpublish: {
      title: "下线勾选（改库+删 dist）",
      api: 'POST /api/pages/unpublish  body: {page_ids, upload:false, target_status:"draft"}',
      flow: [
        "media_pages 状态改为 draft（或指定 target_status）",
        "删除 portal/dist 对应静态文件",
        "重写首页 write_home_page + sitemap write_sitemap",
        "不上公网（upload=false）",
      ],
      scripts: [
        "workflow/ops/pages_service.py → unpublish_pages()",
        "workflow/generate/（home / sitemap 写入）",
      ],
      commands: ["# UI 专用；核对：ls portal/dist/... 与 SELECT status FROM media_pages"],
      dataFlow: "勾选 page_ids → 改库 → 删 dist → 刷新 home/sitemap",
      storage: [
        "MySQL：media_pages.status",
        "磁盘：portal/dist/（删除对应页）",
        "home / sitemap 同步更新",
      ],
      troubleshoot: [
        "公网仍可见 → 本操作不上传；需「下线并正式上传」或④ upload_only",
        "dist 删了但库仍 published → 查 unpublish 返回 error / 事务失败",
      ],
    },

    inv_unpublish_upload: {
      title: "下线并正式上传",
      api: "POST /api/pages/unpublish  body: {page_ids, upload:true}",
      flow: [
        "同「下线勾选」：改库 + 删 dist + home/sitemap",
        "再调 actions._run_wrangler_upload() → wrangler deploy",
        "公网对账删除已不在 dist 的文件",
      ],
      scripts: [
        "workflow/ops/pages_service.py",
        "workflow/ops/actions.py → _run_wrangler_upload()",
      ],
      commands: [
        "cd releasematch && wrangler deploy   # 在 PROJECT_ROOT 执行",
      ],
      dataFlow: "改库/删 dist → wrangler deploy → Cloudflare Pages",
      storage: [
        "本地：portal/dist/",
        "远程：Cloudflare Pages（正式上传）",
        "MySQL：media_pages",
      ],
      troubleshoot: [
        "wrangler 失败 → 检查 CF 登录 / wrangler.toml / 网络",
        "部分 URL 残留 → 确认 dist 缺文件后 upload 才会对账删",
      ],
    },

    inv_add_track: {
      title: "加入当前跟踪批",
      api: "POST /api/pages/add-to-track  body: {page_ids, create_new_batch?}",
      flow: [
        "从 media_pages 取勾选页",
        "create_new_batch=true → create_batch()；否则 append 到活跃批",
        "写入 ops_track_slots，供③④重跑 pipeline/generate",
      ],
      scripts: [
        "workflow/ops/pages_service.py → add_inventory_to_track()",
        "workflow/ops/track_store.py",
      ],
      commands: ["# UI 专用；批次在 MySQL ops_track_batches"],
      dataFlow: "media_pages 行 → ops_track_slots 工单行",
      storage: [
        "MySQL：ops_track_batches / ops_track_slots",
        "不改变 media_pages 统管状态（除非后续 pipeline）",
      ],
      troubleshoot: [
        "无活跃批且未勾选新建 → 勾选「新建批次」或先②导入",
        "槽已在批内 → 看返回 skipped / duplicate 信息",
      ],
    },

    build_tmdb: {
      title: "生成清单并载入工作区",
      api: "POST /api/source/build-tmdb  body: {total, movies?, tv?, download}",
      flow: [
        "source_service.build_from_tmdb_export()",
        "底层 tmdb_export_slots：锚点 + curated + pop 填充",
        "写 worklogs/YYYY-MM-DD/tmdb-benchmark-slots.json",
        "载入内存 WORKSPACE.candidates",
      ],
      scripts: [
        "workflow/ops/source_service.py",
        "workflow/metadata/tmdb_export_slots.py",
        "scripts/tmdb_select_benchmark_slots.py",
      ],
      commands: [
        "python scripts/tmdb_select_benchmark_slots.py --total 20",
      ],
      dataFlow: "data/tmdb_exports/*.json.gz → 选槽算法 → slots JSON → WORKSPACE",
      storage: [
        "导出文件：data/tmdb_exports/",
        "清单：worklogs/YYYY-MM-DD/tmdb-benchmark-slots.json",
        "内存：WORKSPACE.candidates",
      ],
      troubleshoot: [
        "下载失败 → 检查网络 / TMDB export URL；可先取消「下载日导出」用本地文件",
        "候选为空 → 看 sourceLogic 与导出文件是否存在",
      ],
    },

    load_path: {
      title: "加载已有 slots JSON",
      api: "POST /api/source/load  body: {path}",
      flow: [
        "相对项目根解析 path",
        "source_service.load_slots_json() 解析 slots",
        "写入 WORKSPACE.candidates（覆盖）",
      ],
      scripts: ["workflow/ops/source_service.py", "workflow/ops/workspace.py"],
      commands: [
        "# 文件列表示例扫描：worklogs/**、data/failed_slots/**、data/ops/** 下 *slots*.json",
      ],
      dataFlow: "磁盘 JSON → WORKSPACE.candidates → ①候选表",
      storage: [
        "输入：worklogs/…/…slots….json 等",
        "内存：WORKSPACE（不写 ops_track，直至②导入）",
      ],
      troubleshoot: [
        "404/找不到 → path 须相对 releasematch 项目根",
        "格式错 → 需含 page_id / media 等槽字段",
      ],
    },

    ensure_export: {
      title: "① 全量下载 · 增量入库",
      api: "POST /api/source/export/ensure + GET /api/source/export/progress",
      flow: [
        "异步 start_export_index_load() → ensure_export_index()",
        "下载 TMDB Daily Export → data/tmdb_exports/",
        "增量 UPSERT 入 MySQL tmdb_export_titles",
        "轮询 progress 直至完成",
      ],
      scripts: [
        "workflow/ops/source_service.py",
        "workflow/metadata/tmdb_export_store.py",
      ],
      commands: [
        "python -m workflow.run ops tmdb-sync",
        "python -m workflow.run ops tmdb-sync --full-reload   # 等同勾选强制全量重建",
      ],
      dataFlow: "TMDB 日导出文件 → gzip JSON → UPSERT tmdb_export_titles",
      storage: [
        "文件：data/tmdb_exports/*.json.gz",
        "MySQL：tmdb_export_titles",
      ],
      troubleshoot: [
        "进度卡住 → 看底部日志与 progress API 的 message/error",
        "强制全量重建会 TRUNCATE → 确认后再勾 exportForceReload",
        "日同步幂等跳过 → 需「强制重下」或日同步按钮",
      ],
    },

    daily_sync_export: {
      title: "日同步（强制重下）",
      api: "POST /api/source/export/ensure  body: {daily:true, …}",
      flow: [
        "强制重新下载 Daily Export",
        "增量 UPSERT（除非再勾强制全量重建）",
        "与 cron：python -m workflow.run ops tmdb-sync 对齐",
      ],
      scripts: ["workflow/ops/source_service.py", "workflow/ops/daily_service.py（巡检新鲜度）"],
      commands: ["python -m workflow.run ops tmdb-sync"],
      dataFlow: "强制下载 → UPSERT → 徽章「已入库」",
      storage: ["data/tmdb_exports/", "MySQL tmdb_export_titles"],
      troubleshoot: [
        "⑥ 巡检报 TMDB 不新鲜 → 先跑本操作或 cron tmdb-sync",
        "表空 → 试 --full-reload / 勾选强制全量重建",
      ],
    },

    search_export: {
      title: "② 从 MySQL 搜索",
      api: "POST /api/source/export/search",
      flow: [
        "source_service.search_tmdb_export()",
        "按 q / media_types / pop / adult·video 过滤",
        "结果进 exportHitTable；TV 可再拉季集",
      ],
      scripts: ["workflow/ops/source_service.py", "workflow/metadata/tmdb_export_store.py"],
      commands: ["# 库内：SELECT … FROM tmdb_export_titles WHERE title LIKE …"],
      dataFlow: "表单条件 → MySQL 查询 → 前端勾选表",
      storage: ["只读：tmdb_export_titles", "TV 扩展：tmdb_tv_* / tmdb_api_cache"],
      troubleshoot: [
        "无结果 → 先跑「全量下载·增量入库」；确认关键词/pop 范围",
        "这是候选库，不是 media_pages 台账",
      ],
    },

    add_export_append: {
      title: "③ 勾选 → 追加工作区",
      api: 'POST /api/source/export/add  body: {selections[], mode:"append"}',
      flow: [
        "slots_from_manual_selections()（含 TV 多集）",
        "WORKSPACE.add_slots(mode=append)",
        "更新①候选表",
      ],
      scripts: ["workflow/ops/source_service.py", "workflow/ops/workspace.py"],
      commands: ["# 无 CLI；结果在内存，导入前可再筛选"],
      dataFlow: "勾选行 (+ TV 分集) → slot 对象 → WORKSPACE.candidates 追加",
      storage: ["内存 WORKSPACE", "TV 缓存表 tmdb_tv_series/seasons/episodes"],
      troubleshoot: [
        "TV 无分集 → 先点「季集」拉取",
        "未进入③④ → 还需②筛选并「导入跟踪表」",
      ],
    },

    add_export_replace: {
      title: "③ 勾选 → 覆盖工作区",
      api: 'POST /api/source/export/add  body: {selections[], mode:"replace"}',
      flow: [
        "同追加，但 mode=replace 清空后写入",
        "覆盖当前 WORKSPACE.candidates",
      ],
      scripts: ["workflow/ops/source_service.py", "workflow/ops/workspace.py"],
      commands: ["# 无 CLI"],
      dataFlow: "勾选 → 替换整个候选清单",
      storage: ["内存 WORKSPACE.candidates"],
      troubleshoot: ["误覆盖 → 可重新 load JSON 或再搜索追加"],
    },

    apply_filter: {
      title: "应用筛选",
      api: "POST /api/filter",
      flow: [
        "WORKSPACE.apply_filter() → filter_service",
        "对照 media_pages published（≥2 magnet）与失败登记册",
        "结果写入 WORKSPACE.filtered",
      ],
      scripts: [
        "workflow/ops/filter_service.py",
        "workflow/ops/workspace.py",
      ],
      commands: ["# 失败册：data/failed_slots/registry.json"],
      dataFlow: "candidates + 筛选条件 + published/失败册 → filtered[]",
      storage: [
        "内存：WORKSPACE.filtered",
        "对照：MySQL media_pages",
        "对照：data/failed_slots/registry.json",
      ],
      troubleshoot: [
        "全被排除 → 关掉「排除已 published」或检查失败册",
        "候选为空 → 回①载入清单",
      ],
    },

    import_track: {
      title: "导入跟踪表 → ③④",
      api: "POST /api/track/import",
      flow: [
        "WORKSPACE.import_to_track()",
        "创建/更新 ops_track_batches + ops_track_slots",
        "与 published 重叠时需 confirm_published",
        "导入后切到③使用跟踪表",
      ],
      scripts: [
        "workflow/ops/workspace.py",
        "workflow/ops/track_store.py",
      ],
      commands: ["# 工单真源在 MySQL，非 worklogs"],
      dataFlow: "filtered 勾选 → ops_track_* 工单 → ③④动作输入",
      storage: [
        "MySQL：ops_track_batches / ops_track_slots",
        "统管 media_pages 此时未必改（pipeline 才写源）",
      ],
      troubleshoot: [
        "published 重叠警告 → 确认后 confirm 或取消勾选",
        "导入后③空表 → 点刷新；检查活跃批次徽章",
      ],
    },

    run_generation_flow: {
      title: "一键跑生成流程",
      api: "串联 POST /api/actions/pipeline → /generate → /speedtest",
      flow: [
        "1) pipeline（Jackett 拉源，含门禁刷新）",
        "2) generate 选中页 → portal/dist",
        "3) speedtest write → slot_speed_summary，成功后自动 regenerate",
        "skipExisting 仅影响步骤 1",
      ],
      scripts: [
        "workflow/ops/static/ops.js（前端串联）",
        "workflow/ops/actions.py",
        "workflow/storage/pipeline.py",
      ],
      commands: [
        "python -m workflow.run pipeline batch …",
        "python -m workflow.run generate page --page-id …",
        "python -m workflow.torrent_sources.speedtest.run batch --page-ids '…' --write --report worklogs/ops/speedtest-<batch_id>.json",
      ],
      dataFlow: "ops_track_slots → Jackett/magnet → media_pages → dist → 测速表 → 再 bake",
      storage: [
        "MySQL：media_pages / download_resources / slot_speed_summary / ops_track_*",
        "磁盘：portal/dist/",
        "报告：worklogs/ops/speedtest-*.json",
      ],
      troubleshoot: [
        "中断在某步 → 看底部日志哪次 API 失败，再单独点对应按钮",
        "Jackett 失败 → ⑤ accounts.local.json / Dashboard",
        "测速失败 → 看 report JSON 与 indexer/proxy",
      ],
    },

    pipeline: {
      title: "跑 Pipeline（Jackett 拉源）",
      api: "POST /api/actions/pipeline  body: {fetch:true, skip_existing, mode:\"live\"}",
      flow: [
        "actions.run_pipeline() → run_batch_slot_pipeline()",
        "经 Jackett/Torznab 拉 torrent/magnet",
        "写入 media_pages / download_resources",
        "自动 refresh_gates 回写跟踪表 magnet/Rec",
      ],
      scripts: [
        "workflow/ops/actions.py → run_pipeline()",
        "workflow/storage/pipeline.py",
        "workflow/torrent_sources/（accounts.local.json）",
      ],
      commands: [
        "python -m workflow.run pipeline batch …",
      ],
      dataFlow: "跟踪槽 → Jackett 搜索 → DB 资源行 → 门禁字段",
      storage: [
        "MySQL：media_pages、download_resources、ops_track_slots",
        "配置：workflow/torrent_sources/accounts.local.json",
      ],
      troubleshoot: [
        "0 magnet → Jackett Key/URL、indexer、FlareSolverr、代理",
        "skip_existing 跳过过多 → 取消勾选「跳过已有 ≥2 magnet」",
      ],
    },

    refresh_gates: {
      title: "刷新门禁",
      api: "POST /api/track/refresh-gates",
      flow: [
        "从 media_pages 读 magnet 数 / Rec / indexable",
        "回写 ops_track_slots 门禁列，供 UI 与后续步骤判断",
      ],
      scripts: ["workflow/ops/actions.py → refresh_gates()", "workflow/ops/track_store.py"],
      commands: ["# UI/API；pipeline 成功后会自动调用"],
      dataFlow: "media_pages → ops_track_slots 门禁快照",
      storage: ["MySQL：ops_track_slots（门禁列）", "真源仍是 media_pages"],
      troubleshoot: [
        "门禁与库不一致 → 再点刷新；确认活跃批次正确",
      ],
    },

    generate_pages: {
      title: "Generate 选中页",
      api: "POST /api/actions/generate  body: {generate_all:false}",
      flow: [
        "actions.run_generate(generate_all=false)",
        "write_page_html() bake 选中槽",
        "TV 自动 ensure_show_hub_page + hub generate",
      ],
      scripts: [
        "workflow/ops/actions.py → run_generate()",
        "workflow/generate/（页面模板写入）",
      ],
      commands: [
        "python -m workflow.run generate page --page-id <page_id>",
      ],
      dataFlow: "media_pages 内容 → HTML → portal/dist/…",
      storage: [
        "磁盘：portal/dist/",
        "MySQL：media_pages.generated_at 等",
      ],
      troubleshoot: [
        "空白页 → 先 pipeline 保证有内容/magnet",
        "缺 hub → 看 TV 是否自动 ensure_show_hub",
      ],
    },

    generate_all: {
      title: "Generate all",
      api: "POST /api/actions/generate  body: {generate_all:true}",
      flow: [
        "write_all_published() 全站 bake",
        "用于模板/CSS/全局变更后的全量 regenerate",
      ],
      scripts: ["workflow/ops/actions.py", "workflow/generate/"],
      commands: ["python -m workflow.run generate all"],
      dataFlow: "全部 published（及策略内页面）→ portal/dist 全量",
      storage: ["portal/dist/", "media_pages"],
      troubleshoot: [
        "耗时长属正常；失败看返回 error 与某 page_id",
        "仅单批上线用「Generate 选中页」或④增量即可",
      ],
    },

    speedtest: {
      title: "测速 write",
      api: "POST /api/actions/speedtest",
      flow: [
        "子进程调用 speedtest.run batch --write",
        "写 MySQL slot_speed_summary",
        "报告 worklogs/ops/speedtest-{batch_id}.json",
        "成功后自动 regenerate 选中页（Grab/测速面板）",
      ],
      scripts: [
        "workflow/ops/actions.py → run_speedtest()",
        "workflow/torrent_sources/speedtest/run.py",
        "scripts/speedtest_batch_worker.py（回退）",
      ],
      commands: [
        "python -m workflow.torrent_sources.speedtest.run batch \\",
        "  --page-ids \"tv:1396:s04e06,movie:603\" \\",
        "  --write --report worklogs/ops/speedtest-<batch_id>.json",
      ],
      dataFlow: "选中 page_ids → 测速 worker → slot_speed_summary → 再 generate",
      storage: [
        "MySQL：slot_speed_summary",
        "报告：worklogs/ops/speedtest-*.json",
        "cron 日志（VPS）：/var/log/releasematch/speedtest-cron.log",
      ],
      troubleshoot: [
        "无 Rec 槽测不出 → 先 pipeline 出推荐源",
        "报告 ok=false → 打开 JSON 看各 page 错误",
        "面板数字旧 → 确认测速后自动 regenerate 是否成功",
      ],
    },

    seo: {
      title: "跑 seo_c2_checklist",
      api: "POST /api/actions/seo",
      flow: [
        "actions.run_seo_c2()",
        "优先 bash scripts/seo_c2_checklist.sh，否则 .py",
        "回写批次步骤 seo_c2 状态",
      ],
      scripts: [
        "workflow/ops/actions.py → run_seo_c2()",
        "scripts/seo_c2_checklist.sh",
        "scripts/seo_c2_checklist.py",
      ],
      commands: ["bash scripts/seo_c2_checklist.sh"],
      dataFlow: "本地检查脚本 stdout → ops_track_batches.seo_c2",
      storage: ["批次步骤状态：ops_track_batches", "脚本输出见底部日志"],
      troubleshoot: [
        "找不到脚本 → 确认 scripts/seo_c2_checklist.* 存在",
        "检查失败 → 读日志 detail，对照 checklist 项修 dist/元数据",
      ],
    },

    deploy: {
      title: "执行 Deploy",
      api: 'POST /api/actions/deploy  body: {scope, upload}',
      flow: [
        "incremental：bake 选中槽 + home/sitemap/壳",
        "full：write_all_published()",
        "upload_only：跳过 prepare，只 wrangler",
        "upload=true 时 _run_wrangler_upload()",
      ],
      scripts: [
        "workflow/ops/actions.py → run_deploy() / _prepare_dist_* / _run_wrangler_upload()",
      ],
      commands: [
        "# prepare 后：",
        "cd releasematch && wrangler deploy",
      ],
      dataFlow: "跟踪选中/全站 → portal/dist →（可选）Cloudflare Pages",
      storage: [
        "本地：portal/dist/",
        "远程：CF Pages（仅 upload=true）",
        "批次：ops_track deploy 步骤",
      ],
      troubleshoot: [
        "忘勾「正式上传」→ 只改本地 dist",
        "增量漏页 → 确认跟踪表勾选；或改 full",
        "公网旧文件 → upload_only 对账或下线并上传",
      ],
    },

    config_load: {
      title: "从磁盘加载配置",
      api: "GET /api/config",
      flow: [
        "config_service.get_config_bundle()",
        "读 .env + accounts.local.json 填表单",
      ],
      scripts: ["workflow/ops/config_service.py"],
      commands: ["# 直接 cat .env / accounts.local.json"],
      dataFlow: "磁盘配置文件 → UI 表单/文本框",
      storage: [
        ".env",
        "workflow/torrent_sources/accounts.local.json",
      ],
      troubleshoot: ["文件缺失 → 点「从模板初始化」"],
    },

    config_init: {
      title: "从模板初始化缺失文件",
      api: 'POST /api/config/init  body: {which:"both"}',
      flow: [
        "ensure_env_file_from_example()",
        "ensure_accounts_local_from_example()",
        "仅创建缺失文件，不覆盖已有",
      ],
      scripts: ["workflow/ops/config_service.py"],
      commands: [
        "cp config.env.example .env   # 若尚无",
        "cp workflow/torrent_sources/accounts.example.json workflow/torrent_sources/accounts.local.json",
      ],
      dataFlow: "example → 本地私密文件",
      storage: [".env", "accounts.local.json", "模板：*.example*"],
      troubleshoot: ["已存在不会覆盖 → 需手改或删后重建"],
    },

    config_reload: {
      title: "仅加载到进程（不写盘）",
      api: "POST /api/config/reload",
      flow: [
        "apply_runtime_reload()：把当前磁盘值载入进程 env/内存",
        "不修改磁盘文件",
      ],
      scripts: ["workflow/ops/config_service.py"],
      commands: ["# 改完磁盘文件后可用；或保存按钮已带 reload"],
      dataFlow: "磁盘 → 当前 ops serve 进程",
      storage: ["无写盘；重启进程也会再读盘"],
      troubleshoot: ["改了表单未保存就 reload → 仍是旧磁盘值"],
    },

    config_save_env: {
      title: "保存 .env 并加载",
      api: "POST /api/config/env  body: {values|raw, reload:true}",
      flow: [
        "save_env_values() 或 save_env_raw()",
        "写入项目根 .env 并热加载",
      ],
      scripts: ["workflow/ops/config_service.py"],
      commands: ["# 编辑 releasematch/.env 后 reload"],
      dataFlow: "表单/全文 → .env → 进程环境",
      storage: [".env（含 MySQL / RM_OPS_* / TMDB 等）"],
      troubleshoot: [
        "勿在 .env 写 JACKETT_*（数据源在 accounts.local.json）",
        "MySQL 连不上 → 核对 RM_RELEASE_MYSQL_*",
      ],
    },

    config_save_accounts: {
      title: "保存 accounts 并加载",
      api: "POST /api/config/accounts",
      flow: [
        "save_accounts_data() 写 accounts.local.json",
        "热加载为 Jackett/proxy/indexer 真源",
      ],
      scripts: [
        "workflow/ops/config_service.py",
        "workflow/torrent_sources/accounts.local.json",
      ],
      commands: ["# 编辑 accounts.local.json 后点保存或 reload"],
      dataFlow: "JSON 文本 → accounts.local.json → 拉源/测速读此文件",
      storage: ["workflow/torrent_sources/accounts.local.json（勿提交密钥）"],
      troubleshoot: [
        "pipeline 仍用旧 Key → 确认保存成功且 reload",
        "JSON 语法错 → 保存会失败，看返回 error",
      ],
    },

    jackett_deploy: {
      title: "Jackett 一键部署",
      api: "POST /api/jackett/deploy/start + GET …/progress",
      flow: [
        "jackett_deploy_service.start_deploy()",
        "SSH 到 VPS 跑 scripts/install_jackett_oneclick.sh",
        "可选写 indexer、sync API Key → accounts.local.json",
      ],
      scripts: [
        "workflow/ops/jackett_deploy_service.py",
        "scripts/install_jackett_oneclick.sh",
        "workflow/torrent_sources/servers.local.json",
      ],
      commands: [
        "bash scripts/install_jackett_oneclick.sh \\",
        "  --host <IP> --password '<密码>' \\",
        "  --with-indexers --indexer-profile all",
      ],
      dataFlow: "表单/SSH → VPS Docker(jackett+flaresolverr) → 可选回写 accounts",
      storage: [
        "VPS：Docker 容器 jackett / flaresolverr",
        "本机：accounts.local.json（若 sync Key）",
        "SSH 凭据：servers.local.json（不回显密码）",
      ],
      troubleshoot: [
        "SSH 失败 → host/端口/密码或 servers.local.json",
        "Dashboard HTTP 400（curl）属 Jackett UI 行为，用浏览器",
        "docs：docs/jackett-remote-linode.md / docs/VPS迁移与部署.md",
      ],
    },

    jackett_defaults: {
      title: "从 servers.local.json 预填",
      api: "GET /api/jackett/deploy/defaults",
      flow: [
        "load_defaults() 读 host/user/port",
        "密码不回传 UI，部署时 use_servers_password",
      ],
      scripts: [
        "workflow/ops/jackett_deploy_service.py",
        "workflow/torrent_sources/servers.local.json",
      ],
      commands: ["# 编辑 servers.local.json 后点预填"],
      dataFlow: "servers.local.json → 表单字段（无密码明文）",
      storage: ["servers.local.json（勿提交）"],
      troubleshoot: ["预填空 → 文件不存在或字段名不匹配"],
    },

    daily_refresh: {
      title: "刷新巡检",
      api: "GET /api/daily/status",
      flow: [
        "daily_service.collect_daily_patrol()",
        "组合：torrent_sources 状态、db 快照、测速覆盖、TMDB 新鲜度、失败槽、cron 证据",
        "渲染 checks[] 与各 detail 块",
      ],
      scripts: [
        "workflow/ops/daily_service.py",
        "checklists/daily/每日巡检检查清单.md",
        "docs/12-日常运营执行手册.md §四",
      ],
      commands: [
        "python -m workflow.torrent_sources.run status",
        "python -m workflow.run db status",
        "tail -50 /var/log/releasematch/speedtest-cron.log",
      ],
      dataFlow: "多源探测 → checks PASS/FAIL → ⑥ UI",
      storage: [
        "证据：worklogs/**/speedtest*.json",
        "失败册：data/failed_slots/registry.json",
        "VPS 日志：/var/log/releasematch/*",
        "表：slot_speed_summary、tmdb_export_titles",
      ],
      troubleshoot: [
        "某 check FAIL → 展开 detail，对应该段脚本/表",
        "cron 无证据 → 确认本机/VPS crontab 与日志路径",
      ],
    },

    daily_tmdb_sync: {
      title: "TMDB 日同步（日常）",
      api: "POST /api/source/export/ensure  body: {daily:true}",
      flow: [
        "与①「日同步」相同：强制重下 + UPSERT",
        "对齐手册日更与 cron tmdb-sync",
      ],
      scripts: ["workflow/ops/source_service.py"],
      commands: ["python -m workflow.run ops tmdb-sync"],
      dataFlow: "Daily Export → tmdb_export_titles",
      storage: ["data/tmdb_exports/", "MySQL tmdb_export_titles"],
      troubleshoot: ["巡检 TMDB 项 FAIL → 跑本按钮后「刷新巡检」"],
    },

    daily_speed_gap: {
      title: "测速缺口补测",
      api: "POST /api/daily/speedtest-gap  body: {limit:20, workers:3}",
      flow: [
        "查出有 Rec 但缺 slot_speed_summary 的 page_id",
        "daily_service.run_speedtest_gap_fill() batch write",
        "报告 worklogs/ops/speedtest-gap-{stamp}.json",
      ],
      scripts: [
        "workflow/ops/daily_service.py",
        "workflow/torrent_sources/speedtest/run.py",
      ],
      commands: [
        "python -m workflow.torrent_sources.speedtest.run batch \\",
        "  --page-ids \"<comma-separated>\" \\",
        "  --write --report worklogs/ops/speedtest-gap-<stamp>.json",
      ],
      dataFlow: "缺口 page_ids → 测速 write → slot_speed_summary",
      storage: [
        "MySQL：slot_speed_summary",
        "报告：worklogs/ops/speedtest-gap-*.json",
        "列表 API：GET /api/daily/speed-gaps",
      ],
      troubleshoot: [
        "缺口仍在 → 看报告失败原因；确认 Rec 源可连",
        "limit 默认 20 → 多次补测或加大 limit",
      ],
    },
  };

  /**
   * 将说明文档渲染为 HTML 片段。
   * @param {OpsHelpDoc} doc 文档
   * @returns {string} HTML
   */
  function renderHelpHtml(doc) {
    const esc = (s) =>
      String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");

    /** @param {string} title @param {string[]} items */
    function listBlock(title, items) {
      if (!items || !items.length) return "";
      return (
        `<section class="ops-help-section"><h4>${esc(title)}</h4><ol>` +
        items.map((x) => `<li>${esc(x)}</li>`).join("") +
        `</ol></section>`
      );
    }

    /** @param {string} title @param {string[]} lines */
    function codeBlock(title, lines) {
      if (!lines || !lines.length) return "";
      return (
        `<section class="ops-help-section"><h4>${esc(title)}</h4>` +
        `<pre class="ops-help-code">${lines.map(esc).join("\n")}</pre></section>`
      );
    }

    let html = `<h3 class="ops-help-title">${esc(doc.title)}</h3>`;
    if (doc.api) {
      html += `<section class="ops-help-section"><h4>API</h4><pre class="ops-help-code">${esc(doc.api)}</pre></section>`;
    }
    html += listBlock("实现流程", doc.flow);
    html += codeBlock("脚本 / 代码路径", doc.scripts || []);
    html += codeBlock("完整命令", doc.commands || []);
    if (doc.dataFlow) {
      html += `<section class="ops-help-section"><h4>数据流</h4><p class="ops-help-flow">${esc(doc.dataFlow)}</p></section>`;
    }
    html += listBlock("数据存储位置", doc.storage || []);
    html += listBlock("排障定位", doc.troubleshoot || []);
    html +=
      `<p class="ops-help-foot">文档索引：docs/06-run-cli使用说明.md §5.4b · docs/12-日常运营执行手册.md · docs/INDEX.md</p>`;
    return html;
  }

  /**
   * 打开帮助抽屉。
   * @param {string} key 目录 key
   */
  function openHelp(key) {
    const doc = HELP_CATALOG[key];
    const drawer = document.getElementById("opsHelpDrawer");
    const body = document.getElementById("opsHelpBody");
    const backdrop = document.getElementById("opsHelpBackdrop");
    if (!drawer || !body) return;
    if (!doc) {
      body.innerHTML = `<p class="lead">未找到说明：<code>${String(key)}</code></p>`;
    } else {
      body.innerHTML = renderHelpHtml(doc);
    }
    drawer.hidden = false;
    if (backdrop) backdrop.hidden = false;
    drawer.setAttribute("aria-hidden", "false");
    const closeBtn = document.getElementById("opsHelpClose");
    if (closeBtn) closeBtn.focus();
  }

  /** 关闭帮助抽屉。 */
  function closeHelp() {
    const drawer = document.getElementById("opsHelpDrawer");
    const backdrop = document.getElementById("opsHelpBackdrop");
    if (drawer) {
      drawer.hidden = true;
      drawer.setAttribute("aria-hidden", "true");
    }
    if (backdrop) backdrop.hidden = true;
  }

  /**
   * 为带 ``data-help`` 的控件注入「说明」按钮。
   */
  function mountHelpButtons() {
    document.querySelectorAll("[data-help]").forEach((el) => {
      const key = el.getAttribute("data-help");
      if (!key || !HELP_CATALOG[key]) return;
      if (el.parentElement && el.parentElement.classList.contains("ops-help-wrap")) {
        return;
      }
      const wrap = document.createElement("span");
      wrap.className = "ops-help-wrap";
      el.parentNode.insertBefore(wrap, el);
      wrap.appendChild(el);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ops-help-btn";
      btn.setAttribute("aria-label", `说明：${HELP_CATALOG[key].title}`);
      btn.title = `说明：${HELP_CATALOG[key].title}`;
      btn.textContent = "?";
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        openHelp(key);
      });
      wrap.appendChild(btn);
    });
  }

  /** 绑定抽屉关闭与 Esc。 */
  function bindDrawerChrome() {
    const closeBtn = document.getElementById("opsHelpClose");
    const backdrop = document.getElementById("opsHelpBackdrop");
    if (closeBtn) closeBtn.addEventListener("click", closeHelp);
    if (backdrop) backdrop.addEventListener("click", closeHelp);
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") closeHelp();
    });
  }

  /**
   * 初始化帮助系统。
   */
  function initOpsHelp() {
    bindDrawerChrome();
    mountHelpButtons();
  }

  global.OpsHelp = {
    HELP_CATALOG,
    openHelp,
    closeHelp,
    initOpsHelp,
    mountHelpButtons,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOpsHelp);
  } else {
    initOpsHelp();
  }
})(window);
