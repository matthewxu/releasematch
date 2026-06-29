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

SET FOREIGN_KEY_CHECKS = 1;
