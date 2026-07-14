-- =============================================================================
-- ReleaseMatch MySQL 本地测试库（与 D1 表结构对齐）
-- =============================================================================
-- 用途：本地开发 / CI 集成测试；验证通过后通过 sync 导出至 Cloudflare D1。
-- 对齐：schema/d1_schema.sql（7 张表，字段语义一致）
--
-- 初始化：
--   python -m workflow.run db init --seed
-- 或分步：db create → db init → db seed
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------------------------
-- 1. release_groups — Release Group 信誉库
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS release_groups (
    name              VARCHAR(64)  NOT NULL PRIMARY KEY COMMENT '压制组 canonical 名',
    aliases           JSON         NULL COMMENT '别名 JSON 数组',
    tier              ENUM('L0','L1','L2','L3','L4') NOT NULL DEFAULT 'L4' COMMENT '信誉档',
    scene_compliant   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'Scene 合规 0/1',
    compliance_rate   DOUBLE       DEFAULT 0.0 COMMENT '合规率 0~1',
    notes             TEXT         COMMENT '运营备注',
    updated_at        DATETIME(3)  NOT NULL COMMENT 'UTC 更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Release Group 信誉库（Recommended Badge）';

CREATE INDEX idx_rg_tier ON release_groups(tier);

-- -----------------------------------------------------------------------------
-- 2. media_catalog — 作品主数据
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_catalog (
    catalog_id              VARCHAR(32)  NOT NULL PRIMARY KEY COMMENT 'tv:1396 | movie:27205',
    tmdb_id                 INT UNSIGNED NOT NULL,
    media_kind              ENUM('tv','movie') NOT NULL,
    slug                    VARCHAR(128) NOT NULL COMMENT 'URL slug',
    title                   VARCHAR(512) NOT NULL,
    overview                TEXT,
    year                    SMALLINT UNSIGNED NULL,
    runtime_minutes         SMALLINT UNSIGNED NULL COMMENT '电影片长（分钟）',
    poster_path             VARCHAR(512) DEFAULT '' COMMENT 'TMDB poster path',
    tmdb_url                VARCHAR(512) DEFAULT '',
    streaming_providers     JSON         NULL COMMENT 'Watch On 列表',
    subtitle_url_pattern    VARCHAR(512) DEFAULT '' COMMENT '字幕站 URL 模板',
    updated_at              DATETIME(3)  NOT NULL,
    UNIQUE KEY uk_catalog_slug (slug),
    KEY idx_catalog_tmdb (tmdb_id, media_kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='作品主数据（Hub / 侧栏）';

-- -----------------------------------------------------------------------------
-- 3. media_pages — 可发布页面槽位
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_pages (
    page_id                 VARCHAR(48)  NOT NULL PRIMARY KEY,
    catalog_id              VARCHAR(32)  NOT NULL,
    page_type               ENUM('episode','movie','show_hub') NOT NULL,
    season                  SMALLINT UNSIGNED NULL,
    episode                 SMALLINT UNSIGNED NULL,
    episode_title           VARCHAR(256) DEFAULT '',
    air_date                DATE NULL,
    overview                TEXT,
    cross_source_count      INT UNSIGNED NOT NULL DEFAULT 0,
    cross_source_total      INT UNSIGNED NOT NULL DEFAULT 3,
    prev_season             SMALLINT UNSIGNED NULL,
    prev_episode            SMALLINT UNSIGNED NULL,
    next_season             SMALLINT UNSIGNED NULL,
    next_episode            SMALLINT UNSIGNED NULL,
    magnet_count            INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '薄页门禁 magnet 条数',
    page_status             ENUM('draft','published','thin') NOT NULL DEFAULT 'draft',
    robots_noindex          TINYINT(1)   NOT NULL DEFAULT 0,
    canonical_path          VARCHAR(256) NOT NULL,
    subtitle_url            VARCHAR(512) DEFAULT '',
    generated_at            DATETIME(3)  NULL,
    updated_at              DATETIME(3)  NOT NULL,
    UNIQUE KEY uk_pages_slot (catalog_id, page_type, season, episode),
    KEY idx_pages_status (page_status),
    KEY idx_pages_canonical (canonical_path),
    CONSTRAINT fk_pages_catalog FOREIGN KEY (catalog_id)
        REFERENCES media_catalog(catalog_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='页面槽位（单集/电影/Hub）';

-- -----------------------------------------------------------------------------
-- 4. download_resources — magnet 清单（Recommended + All Sources）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS download_resources (
    id                      VARCHAR(64)  NOT NULL PRIMARY KEY COMMENT '通常等于 infohash',
    page_id                 VARCHAR(48)  NOT NULL,
    tmdb_id                 INT UNSIGNED NOT NULL,
    media_type              ENUM('tv_episode','movie') NOT NULL,
    season                  SMALLINT UNSIGNED NULL,
    episode                 SMALLINT UNSIGNED NULL,
    infohash                CHAR(40)     NOT NULL,
    title_raw               VARCHAR(1024) NOT NULL,
    release_group           VARCHAR(64)  DEFAULT '',
    source                  VARCHAR(64)  DEFAULT '',
    resolution              VARCHAR(16)  DEFAULT '',
    codec                   VARCHAR(32)  DEFAULT '',
    video_spec              VARCHAR(256) DEFAULT '' COMMENT '卡片 Video 行',
    audio_spec              VARCHAR(256) DEFAULT '' COMMENT '卡片 Audio 行',
    size_bytes              BIGINT UNSIGNED DEFAULT 0,
    seeders                 INT DEFAULT 0,
    peers                   INT DEFAULT 0,
    magnet_uri              TEXT,
    indexer                 VARCHAR(32)  DEFAULT '',
    is_recommended          TINYINT(1)   NOT NULL DEFAULT 0,
    match_score             DOUBLE       DEFAULT 0.0,
    recommend_reason        VARCHAR(512) DEFAULT '',
    group_tier              ENUM('L0','L1','L2','L3','L4') DEFAULT 'L4',
    cross_source_count      INT UNSIGNED DEFAULT 1,
    cross_source_confidence DOUBLE       DEFAULT 0.0,
    indexed_at              DATETIME(3)  NOT NULL,
    expires_at              DATETIME(3)  NOT NULL,
    UNIQUE KEY uk_dl_hash_slot (tmdb_id, media_type, season, episode, infohash),
    KEY idx_dl_page (page_id),
    KEY idx_dl_tmdb_ep (tmdb_id, season, episode),
    KEY idx_dl_recommended (page_id, is_recommended),
    KEY idx_dl_score (page_id, match_score),
    CONSTRAINT fk_dl_page FOREIGN KEY (page_id)
        REFERENCES media_pages(page_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='槽位 magnet 清单';

-- -----------------------------------------------------------------------------
-- 5. slot_speed_summary — 槽位测速摘要（T2）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slot_speed_summary (
    page_id                 VARCHAR(48)  NOT NULL PRIMARY KEY,
    recommended_infohash    CHAR(40)     DEFAULT '',
    recommended_speed       VARCHAR(32)  DEFAULT '' COMMENT '如 4.2 MB/s',
    reachability            VARCHAR(16)  DEFAULT '' COMMENT '高|中|低',
    updated_at              DATETIME(3)  NOT NULL,
    CONSTRAINT fk_speed_page FOREIGN KEY (page_id)
        REFERENCES media_pages(page_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='槽位测速摘要条';

-- -----------------------------------------------------------------------------
-- 6. speedtest_results — 单 magnet 测速明细
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS speedtest_results (
    id                      VARCHAR(64)  NOT NULL PRIMARY KEY,
    infohash                CHAR(40)     NOT NULL,
    page_id                 VARCHAR(48)  NULL,
    phase                   TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '1=连接性 2=片段',
    peers_reachable         INT UNSIGNED DEFAULT 0,
    peers_total             INT UNSIGNED DEFAULT 0,
    avg_kbps                DOUBLE       DEFAULT 0.0,
    max_kbps                DOUBLE       DEFAULT 0.0,
    latency_ms              INT UNSIGNED DEFAULT 0,
    status                  VARCHAR(16)  DEFAULT 'ok',
    tested_at               DATETIME(3)  NOT NULL,
    KEY idx_st_infohash (infohash),
    KEY idx_st_page (page_id, tested_at),
    CONSTRAINT fk_st_page FOREIGN KEY (page_id)
        REFERENCES media_pages(page_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='magnet 测速明细';

-- -----------------------------------------------------------------------------
-- 6b. torrent_metadata — Phase 2 从 swarm 提取的 torrent 结构（等价 .torrent info）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS torrent_metadata (
    infohash                CHAR(40)     NOT NULL PRIMARY KEY,
    page_id                 VARCHAR(48)  NULL,
    torrent_name            VARCHAR(1024) DEFAULT '',
    total_size_bytes        BIGINT UNSIGNED DEFAULT 0,
    file_count              INT UNSIGNED DEFAULT 0,
    piece_length            INT UNSIGNED DEFAULT 0,
    is_private              TINYINT(1)   DEFAULT 0,
    primary_file            VARCHAR(1024) DEFAULT '',
    primary_file_size_bytes BIGINT UNSIGNED DEFAULT 0,
    files_json              JSON         NULL,
    indexer_size_bytes      BIGINT UNSIGNED DEFAULT 0,
    size_match              VARCHAR(16)  DEFAULT 'unknown' COMMENT 'ok|mismatch|unknown',
    size_delta_bytes        BIGINT       DEFAULT 0,
    status                  VARCHAR(16)  DEFAULT 'ok',
    extracted_at            DATETIME(3)  NOT NULL,
    KEY idx_tm_page (page_id),
    CONSTRAINT fk_tm_page FOREIGN KEY (page_id)
        REFERENCES media_pages(page_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='swarm torrent 结构 metadata';

-- -----------------------------------------------------------------------------
-- 7. sync_runs — sync 批次审计
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_runs (
    run_id                  VARCHAR(64)  NOT NULL PRIMARY KEY,
    source                  VARCHAR(32)  NOT NULL COMMENT 'batch|on_demand|speedtest|mysql_to_d1',
    slots_processed         INT UNSIGNED DEFAULT 0,
    resources_upserted      INT UNSIGNED DEFAULT 0,
    pages_published         INT UNSIGNED DEFAULT 0,
    error_message           TEXT,
    started_at              DATETIME(3)  NOT NULL,
    finished_at             DATETIME(3)  NULL,
    KEY idx_sync_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='sync 批次审计';

-- -----------------------------------------------------------------------------
-- 8. download_inventory — 批补中间表（workflow 写入，可选同步至 download_resources）
-- 保留与早期 mysql_download_inventory.sql 兼容；pipeline 可双写或仅作 staging。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS download_inventory (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tmdb_id         INT UNSIGNED NOT NULL,
    media_type      ENUM('movie','tv_episode') NOT NULL,
    season_number   INT NOT NULL DEFAULT 0,
    episode_number  INT NOT NULL DEFAULT 0,
    infohash        CHAR(40) NOT NULL,
    title_raw       VARCHAR(1024) NOT NULL,
    release_group   VARCHAR(64) DEFAULT '',
    source          VARCHAR(32) DEFAULT '',
    resolution      VARCHAR(16) DEFAULT '',
    codec           VARCHAR(16) DEFAULT '',
    size_bytes      BIGINT UNSIGNED DEFAULT 0,
    seeders         INT DEFAULT 0,
    peers           INT DEFAULT 0,
    magnet_uri      TEXT,
    indexer         VARCHAR(32) NOT NULL,
    is_recommended  TINYINT(1) DEFAULT 0,
    match_score     DOUBLE DEFAULT 0,
    recommend_reason VARCHAR(512) DEFAULT '',
    fetched_at      DATETIME(3) NOT NULL,
    expires_at      DATETIME(3) NOT NULL,
    UNIQUE KEY uk_inv_hash_slot (tmdb_id, media_type, season_number, episode_number, infohash),
    KEY idx_inv_slot (tmdb_id, season_number, episode_number),
    KEY idx_inv_recommended (tmdb_id, season_number, episode_number, is_recommended)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='批补 staging 表（torrent_sources 写入）';

-- -----------------------------------------------------------------------------
-- 9. ops_track_batches — Ops 跟踪批次（筛选后贯通生成/上线）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ops_track_batches (
    batch_id                VARCHAR(64)  NOT NULL PRIMARY KEY COMMENT '如 20260714T020334Z-888e9ed0',
    is_active               TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '当前活跃批次 0/1',
    source_json             JSON         NULL COMMENT '清单来源元信息',
    filter_json             JSON         NULL COMMENT '筛选条件元信息',
    seo_status              VARCHAR(16)  NOT NULL DEFAULT 'pending',
    seo_at                  DATETIME(3)  NULL,
    seo_detail              TEXT,
    deploy_status           VARCHAR(16)  NOT NULL DEFAULT 'pending',
    deploy_at               DATETIME(3)  NULL,
    deploy_detail           TEXT,
    slot_count              INT UNSIGNED NOT NULL DEFAULT 0,
    created_at              DATETIME(3)  NOT NULL,
    updated_at              DATETIME(3)  NOT NULL,
    KEY idx_ops_batch_active (is_active),
    KEY idx_ops_batch_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Ops 跟踪批次（生成/上线中间表）';

-- -----------------------------------------------------------------------------
-- 10. ops_track_slots — Ops 跟踪槽位行
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ops_track_slots (
    id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    batch_id                VARCHAR(64)  NOT NULL,
    page_id                 VARCHAR(48)  NOT NULL COMMENT '如 tv:1396:s04e06',
    slot_key                VARCHAR(48)  NOT NULL,
    label                   VARCHAR(256) DEFAULT '',
    tmdb_id                 INT UNSIGNED NOT NULL,
    media_type              VARCHAR(16)  NOT NULL COMMENT 'tv|movie',
    season                  SMALLINT UNSIGNED NULL,
    episode                 SMALLINT UNSIGNED NULL,
    title                   VARCHAR(512) DEFAULT '',
    popularity              DOUBLE       NULL,
    source_tier             VARCHAR(32)  NOT NULL DEFAULT 'unknown' COMMENT 'anchor|curated|pop|file',
    selected                TINYINT(1)   NOT NULL DEFAULT 1,
    pipeline_status         VARCHAR(16)  NOT NULL DEFAULT 'pending',
    pipeline_at             DATETIME(3)  NULL,
    pipeline_detail         TEXT,
    generate_status         VARCHAR(16)  NOT NULL DEFAULT 'pending',
    generate_at             DATETIME(3)  NULL,
    generate_detail         TEXT,
    speedtest_status        VARCHAR(16)  NOT NULL DEFAULT 'pending',
    speedtest_at            DATETIME(3)  NULL,
    speedtest_detail        TEXT,
    magnet_count            INT          NULL,
    has_recommended         TINYINT(1)   NULL,
    page_status             VARCHAR(16)  NULL,
    robots_noindex          TINYINT(1)   NULL,
    indexable               TINYINT(1)   NULL,
    canonical_path          VARCHAR(256) NULL,
    error_message           TEXT,
    created_at              DATETIME(3)  NOT NULL,
    updated_at              DATETIME(3)  NOT NULL,
    UNIQUE KEY uk_ops_slot_batch_page (batch_id, page_id),
    KEY idx_ops_slot_batch (batch_id),
    KEY idx_ops_slot_page (page_id),
    CONSTRAINT fk_ops_slot_batch FOREIGN KEY (batch_id)
        REFERENCES ops_track_batches(batch_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Ops 跟踪槽位（pipeline/generate/speedtest/门禁）';

-- -----------------------------------------------------------------------------
-- 11. tmdb_export_meta — TMDB Daily Export 入库元信息
-- -----------------------------------------------------------------------------
-- 策略：每天全量下载 .json.gz，MySQL 侧增量 UPSERT（ingest_mode=incremental）
CREATE TABLE IF NOT EXISTS tmdb_export_meta (
    id                      TINYINT UNSIGNED NOT NULL PRIMARY KEY DEFAULT 1,
    export_date             DATE         NOT NULL COMMENT '导出日',
    movie_count             INT UNSIGNED NOT NULL DEFAULT 0,
    tv_count                INT UNSIGNED NOT NULL DEFAULT 0,
    movie_gz                VARCHAR(128) DEFAULT '',
    tv_gz                   VARCHAR(128) DEFAULT '',
    status                  VARCHAR(16)  NOT NULL DEFAULT 'ready' COMMENT 'loading|ready',
    ingest_mode             VARCHAR(16)  NOT NULL DEFAULT 'incremental' COMMENT 'incremental|replace',
    last_scanned            INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '最近一次扫描行数',
    last_deleted            INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '最近一次 prune 删除行数',
    loaded_at               DATETIME(3)  NOT NULL,
    updated_at              DATETIME(3)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB 日导出入库元信息（Ops 搜索用）';

-- -----------------------------------------------------------------------------
-- 12. tmdb_export_titles — TMDB Daily Export 标题索引（MySQL）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tmdb_export_titles (
    media_type              ENUM('movie','tv') NOT NULL,
    tmdb_id                 INT UNSIGNED NOT NULL,
    title                   VARCHAR(512) NOT NULL,
    title_lc                VARCHAR(512) NOT NULL COMMENT '小写标题供 LIKE 搜索',
    popularity              DOUBLE       NOT NULL DEFAULT 0,
    adult                   TINYINT(1)   NOT NULL DEFAULT 0,
    video                   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '电影 video 标记',
    export_date             DATE         NOT NULL COMMENT '最近出现于该导出日（用于增量 prune）',
    updated_at              DATETIME(3)  NOT NULL,
    PRIMARY KEY (media_type, tmdb_id),
    KEY idx_tet_media_pop (media_type, popularity),
    KEY idx_tet_title_lc (title_lc(64)),
    KEY idx_tet_export_date (export_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB 日导出标题表：全量下载 + UPSERT 增量入库，Ops UI 搜索筛选';

-- -----------------------------------------------------------------------------
-- 13. tmdb_tv_series — Ops TV 剧集摘要（crawler_tmdb 拉取后入库）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tmdb_tv_series (
    tmdb_id                 INT UNSIGNED NOT NULL PRIMARY KEY,
    name                    VARCHAR(512) NOT NULL DEFAULT '',
    original_name           VARCHAR(512) NOT NULL DEFAULT '',
    number_of_seasons       SMALLINT UNSIGNED NULL,
    number_of_episodes      INT UNSIGNED NULL,
    first_air_date          DATE NULL,
    updated_at              DATETIME(3)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB TV 剧集摘要（Ops 季集选型）';

-- -----------------------------------------------------------------------------
-- 14. tmdb_tv_seasons — Ops TV 季列表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tmdb_tv_seasons (
    tmdb_id                 INT UNSIGNED NOT NULL,
    season_number           SMALLINT NOT NULL COMMENT '0=Specials',
    name                    VARCHAR(256) NOT NULL DEFAULT '',
    episode_count           INT UNSIGNED NOT NULL DEFAULT 0,
    air_date                DATE NULL,
    poster_path             VARCHAR(256) NULL,
    updated_at              DATETIME(3)  NOT NULL,
    PRIMARY KEY (tmdb_id, season_number),
    KEY idx_tts_tmdb (tmdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB TV 季列表';

-- -----------------------------------------------------------------------------
-- 15. tmdb_tv_episodes — Ops TV 分集列表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tmdb_tv_episodes (
    tmdb_id                 INT UNSIGNED NOT NULL,
    season_number           SMALLINT NOT NULL,
    episode_number          SMALLINT UNSIGNED NOT NULL,
    name                    VARCHAR(512) NOT NULL DEFAULT '',
    air_date                DATE NULL,
    runtime                 SMALLINT UNSIGNED NULL,
    overview                VARCHAR(512) NOT NULL DEFAULT '',
    still_path              VARCHAR(256) NULL,
    vote_average            DOUBLE NULL,
    updated_at              DATETIME(3)  NOT NULL,
    PRIMARY KEY (tmdb_id, season_number, episode_number),
    KEY idx_tte_lookup (tmdb_id, season_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='TMDB TV 分集列表';

-- -----------------------------------------------------------------------------
-- 16. tmdb_api_cache — crawler_tmdb 原始 API JSON 缓存（MySQL）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tmdb_api_cache (
    cache_key               VARCHAR(768) NOT NULL PRIMARY KEY,
    api_path                VARCHAR(512) NOT NULL,
    response_json           LONGTEXT     NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_api_path (api_path(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='crawler_tmdb API 原始 JSON 缓存（Ops TV 季集拉取）';

SET FOREIGN_KEY_CHECKS = 1;
