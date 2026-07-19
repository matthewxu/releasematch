-- =============================================================================
-- ReleaseMatch Cloudflare D1 线上数据库模型（v0.2）
-- =============================================================================
-- 用途：独立 D1 项目，供 T3 页面生成器与 sync Worker 读写。
-- 对齐：portal/generator/templates/* 与 portal/breaking-bad/s4e6/ 设计演示页。
--
-- UI 模块 → 表映射：
--   Hero 面包屑 / 侧栏 TMDB     → media_catalog + media_pages
--   跨源 badge                  → media_pages.cross_source_*
--   测速摘要条（T2）            → slot_speed_summary
--   Recommended Release 卡片    → download_resources (is_recommended=1)
--   All Sources 对比表          → download_resources (按 match_score 排序)
--   集间 Prev/Next              → media_pages.prev_* / next_*
--   Watch On / 字幕链           → media_catalog.streaming_providers / subtitle_url_pattern
--   Show Hub 季集芯片           → media_pages (page_type=episode) + show_hub 页
--   Group L0~L4 Badge           → release_groups.tier（或 download_resources.group_tier 冗余）
--
-- 部署：
--   wrangler d1 execute releasematch --file=schema/d1_schema.sql
--   wrangler d1 execute releasematch --file=schema/d1_seed_demo.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. release_groups — Release Group 信誉库（Recommended 卡片 Group Badge）
-- UI: rm-badge--tier-l0 ~ l4；scorer.py infer_group_tier()
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS release_groups (
    name              TEXT PRIMARY KEY,           -- 压制组 canonical 名，如 NTb
    aliases           TEXT DEFAULT '[]',          -- JSON 数组，别名列表
    tier              TEXT NOT NULL DEFAULT 'L4'  -- L0|L1|L2|L3|L4
                      CHECK (tier IN ('L0','L1','L2','L3','L4')),
    scene_compliant   INTEGER NOT NULL DEFAULT 0, -- 是否 Scene 合规（0/1）
    compliance_rate   REAL DEFAULT 0.0,           -- 合规率 0~1
    notes             TEXT DEFAULT '',            -- 备注，供运营维护
    updated_at        TEXT NOT NULL               -- ISO8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_rg_tier ON release_groups(tier);

-- -----------------------------------------------------------------------------
-- 2. media_catalog — 作品主数据（Show / Movie 共用，Hub 与侧栏海报）
-- UI: show_title, movie_title, poster_url, tmdb_url, show_overview
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_catalog (
    catalog_id              TEXT PRIMARY KEY,     -- tv:1396 | movie:27205
    tmdb_id                 INTEGER NOT NULL,
    media_kind              TEXT NOT NULL         -- tv | movie
                            CHECK (media_kind IN ('tv','movie')),
    slug                    TEXT NOT NULL UNIQUE, -- URL slug：breaking-bad, inception-2010
    title                   TEXT NOT NULL,        -- 作品主标题
    overview                TEXT DEFAULT '',      -- 剧集/电影简介 en-US（Hub Hero 副标题）
    overview_zh             TEXT DEFAULT '',      -- 剧集/电影简介 zh-CN
    year                    INTEGER,              -- 上映/首播年
    runtime_minutes         INTEGER,              -- 电影片长（分钟）；剧集可为 NULL
    poster_path             TEXT DEFAULT '',      -- TMDB poster path，渲染时拼 w300 URL
    tmdb_url                TEXT DEFAULT '',      -- 外链 TMDB
    streaming_providers     TEXT DEFAULT '[]',    -- JSON 数组：["Netflix","AMC+"]
    subtitle_url_pattern    TEXT DEFAULT '',      -- 字幕站 URL 模板，如 https://subtitleportal.com/subtitle/{slug}/s{s}e{e}/
    updated_at              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_catalog_tmdb ON media_catalog(tmdb_id, media_kind);
CREATE INDEX IF NOT EXISTS idx_catalog_slug ON media_catalog(slug);

-- -----------------------------------------------------------------------------
-- 3. media_pages — 可发布页面槽位（单集 / 电影 / Show Hub）
-- UI: episode.html / movie.html / show_hub.html 上下文根对象
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_pages (
    page_id                 TEXT PRIMARY KEY,     -- tv:1396:s04e06 | movie:27205 | tv:1396:hub
    catalog_id              TEXT NOT NULL,        -- FK → media_catalog.catalog_id
    page_type               TEXT NOT NULL         -- episode | movie | show_hub
                            CHECK (page_type IN ('episode','movie','show_hub')),
    season                  INTEGER,              -- 季号；电影/hub 为 NULL
    episode                 INTEGER,              -- 集号；电影/hub 为 NULL
    episode_title           TEXT DEFAULT '',      -- 单集名，如 Cornered
    air_date                TEXT DEFAULT '',      -- 播出日 YYYY-MM-DD
    overview                TEXT DEFAULT '',      -- 槽位级简介 en-US（可覆盖 catalog）
    overview_zh             TEXT DEFAULT '',      -- 槽位级简介 zh-CN
    cross_source_count      INTEGER NOT NULL DEFAULT 0,  -- Hero badge 分子
    cross_source_total      INTEGER NOT NULL DEFAULT 3,  -- Hero badge 分母
    prev_season             INTEGER,              -- 集间导航上一集
    prev_episode            INTEGER,
    next_season             INTEGER,              -- 集间导航下一集
    next_episode            INTEGER,
    magnet_count            INTEGER NOT NULL DEFAULT 0,  -- 薄页门禁：≥2 才 index
    page_status             TEXT NOT NULL DEFAULT 'draft'
                            CHECK (page_status IN ('draft','published','thin')),
    robots_noindex          INTEGER NOT NULL DEFAULT 0,  -- 1=noindex（薄页占位）
    canonical_path          TEXT NOT NULL,        -- 如 /breaking-bad/s4e6/
    subtitle_url            TEXT DEFAULT '',      -- 渲染后完整字幕外链（可覆盖 pattern）
    generated_at            TEXT,                 -- 最近静态页生成时间
    updated_at              TEXT NOT NULL,
    FOREIGN KEY (catalog_id) REFERENCES media_catalog(catalog_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pages_slot
    ON media_pages(catalog_id, page_type, season, episode);
CREATE INDEX IF NOT EXISTS idx_pages_status ON media_pages(page_status);
CREATE INDEX IF NOT EXISTS idx_pages_canonical ON media_pages(canonical_path);

-- -----------------------------------------------------------------------------
-- 4. download_resources — 槽位内 magnet 清单（Recommended + All Sources）
-- UI: recommended_block.html + All Sources 表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS download_resources (
    id                      TEXT PRIMARY KEY,     -- infohash 或 uuid
    page_id                 TEXT NOT NULL,        -- FK → media_pages.page_id
    tmdb_id                 INTEGER NOT NULL,     -- 冗余，便于 API 按 tmdb 查询
    media_type              TEXT NOT NULL         -- tv_episode | movie
                            CHECK (media_type IN ('tv_episode','movie')),
    season                  INTEGER,              -- 季号（电影 NULL）
    episode                 INTEGER,              -- 集号（电影 NULL）
    infohash                TEXT NOT NULL,        -- 40 字符小写 infohash
    title_raw               TEXT NOT NULL,        -- Release 完整标题
    release_group           TEXT DEFAULT '',
    source                  TEXT DEFAULT '',      -- WEB-DL / BluRay 等
    resolution              TEXT DEFAULT '',      -- 1080p / 720p
    codec                   TEXT DEFAULT '',      -- H.264 / HEVC
    video_spec              TEXT DEFAULT '',      -- 卡片 Video 行，如 H.264 1080p ~8 Mbps
    audio_spec              TEXT DEFAULT '',      -- 卡片 Audio 行，如 DDP5.1 @ 640 kbps
    size_bytes              INTEGER DEFAULT 0,
    seeders                 INTEGER DEFAULT 0,
    peers                   INTEGER DEFAULT 0,
    magnet_uri              TEXT DEFAULT '',
    indexer                 TEXT DEFAULT '',      -- jackett / eztv / yts / nyaa
    is_recommended          INTEGER NOT NULL DEFAULT 0,  -- 1=本站 Recommended
    match_score             REAL DEFAULT 0.0,     -- scorer 排序分
    recommend_reason        TEXT DEFAULT '',      -- 推荐理由 IG 文本
    group_tier              TEXT DEFAULT 'L4',    -- L0~L4，冗余加速渲染
    cross_source_count      INTEGER DEFAULT 1,    -- 该 release 跨源命中数
    cross_source_confidence REAL DEFAULT 0.0,     -- cross_count / total_sources
    indexed_at              TEXT NOT NULL,
    expires_at              TEXT NOT NULL,
    FOREIGN KEY (page_id) REFERENCES media_pages(page_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dl_hash_slot
    ON download_resources(tmdb_id, media_type, season, episode, infohash);
CREATE INDEX IF NOT EXISTS idx_dl_page ON download_resources(page_id);
CREATE INDEX IF NOT EXISTS idx_dl_tmdb_ep ON download_resources(tmdb_id, season, episode);
CREATE INDEX IF NOT EXISTS idx_dl_recommended
    ON download_resources(page_id, is_recommended);
CREATE INDEX IF NOT EXISTS idx_dl_score ON download_resources(page_id, match_score DESC);

-- -----------------------------------------------------------------------------
-- 5. slot_speed_summary — 槽位测速摘要条（T2 Phase 1+）
-- UI: rm-speed-bar（recommended_speed / reachability / updated_at）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slot_speed_summary (
    page_id                 TEXT PRIMARY KEY,     -- FK → media_pages.page_id
    recommended_infohash    TEXT DEFAULT '',      -- 对应 Recommended release
    recommended_speed       TEXT DEFAULT '',      -- 展示文本，如 4.2 MB/s
    reachability            TEXT DEFAULT '',      -- 高 | 中 | 低
    updated_at              TEXT NOT NULL,
    FOREIGN KEY (page_id) REFERENCES media_pages(page_id)
);

-- -----------------------------------------------------------------------------
-- 6. speedtest_results — 单条 magnet 测速明细（T2 Worker 写入）
-- UI: 间接供给 slot_speed_summary；未来扩展 per-release 测速 badge
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS speedtest_results (
    id                      TEXT PRIMARY KEY,     -- uuid
    infohash                TEXT NOT NULL,
    page_id                 TEXT,                 -- 可选 FK
    phase                   INTEGER NOT NULL DEFAULT 1,  -- 1=连接性 2=片段测速
    peers_reachable         INTEGER DEFAULT 0,
    peers_total             INTEGER DEFAULT 0,
    avg_kbps                REAL DEFAULT 0.0,
    max_kbps                REAL DEFAULT 0.0,
    latency_ms              INTEGER DEFAULT 0,
    status                  TEXT DEFAULT 'ok',    -- ok | timeout | error
    tested_at               TEXT NOT NULL,
    FOREIGN KEY (page_id) REFERENCES media_pages(page_id)
);

CREATE INDEX IF NOT EXISTS idx_st_infohash ON speedtest_results(infohash);
CREATE INDEX IF NOT EXISTS idx_st_page ON speedtest_results(page_id, tested_at DESC);

-- -----------------------------------------------------------------------------
-- 6b. torrent_metadata — Phase 2 swarm 结构（等价 .torrent info）
-- UI: Recommended 卡片「Torrent structure」折叠面板
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS torrent_metadata (
    infohash                TEXT PRIMARY KEY,
    page_id                 TEXT,
    torrent_name            TEXT DEFAULT '',
    total_size_bytes        INTEGER DEFAULT 0,
    file_count              INTEGER DEFAULT 0,
    piece_length            INTEGER DEFAULT 0,
    is_private              INTEGER DEFAULT 0,
    primary_file            TEXT DEFAULT '',
    primary_file_size_bytes INTEGER DEFAULT 0,
    files_json              TEXT DEFAULT '[]',
    indexer_size_bytes      INTEGER DEFAULT 0,
    size_match              TEXT DEFAULT 'unknown',
    size_delta_bytes        INTEGER DEFAULT 0,
    status                  TEXT DEFAULT 'ok',
    extracted_at            TEXT NOT NULL,
    FOREIGN KEY (page_id) REFERENCES media_pages(page_id)
);

CREATE INDEX IF NOT EXISTS idx_tm_page ON torrent_metadata(page_id);

-- -----------------------------------------------------------------------------
-- 7. sync_runs — sync Worker 批次审计（可选，便于排查上线问题）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_runs (
    run_id                  TEXT PRIMARY KEY,
    source                  TEXT NOT NULL,        -- batch | on_demand | speedtest
    slots_processed         INTEGER DEFAULT 0,
    resources_upserted      INTEGER DEFAULT 0,
    pages_published         INTEGER DEFAULT 0,
    error_message           TEXT DEFAULT '',
    started_at              TEXT NOT NULL,
    finished_at             TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_started ON sync_runs(started_at DESC);
