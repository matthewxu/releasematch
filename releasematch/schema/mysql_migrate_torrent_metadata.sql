-- 增量迁移：torrent_metadata 表（已有库执行一次）
-- @file schema/mysql_migrate_torrent_metadata.sql

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
