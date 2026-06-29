-- ReleaseMatch 可选 MySQL 批补清单表
-- 独立于字幕站表结构；is_recommended 替代原 is_primary（不再与字幕 Primary 对齐）

CREATE TABLE IF NOT EXISTS download_inventory (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tmdb_id         INT UNSIGNED NOT NULL,
    media_type      ENUM('movie','tv_episode') NOT NULL,
    season_number   INT NOT NULL DEFAULT 0,
    episode_number  INT NOT NULL DEFAULT 0,
    infohash        CHAR(40) NOT NULL,
    title_raw       VARCHAR(1024) NOT NULL,
    release_group   VARCHAR(64) DEFAULT '',
    source          VARCHAR(32) DEFAULT '' COMMENT 'WEB-DL/BluRay/HDTV',
    resolution      VARCHAR(16) DEFAULT '',
    codec           VARCHAR(16) DEFAULT '',
    size_bytes      BIGINT UNSIGNED DEFAULT 0,
    seeders         INT DEFAULT 0,
    peers           INT DEFAULT 0,
    magnet_uri      TEXT,
    indexer         VARCHAR(32) NOT NULL COMMENT 'jackett/eztv/yts/nyaa',
    is_recommended  TINYINT(1) DEFAULT 0 COMMENT '本站 Recommended Release 标记',
    match_score     FLOAT DEFAULT 0,
    recommend_reason VARCHAR(512) DEFAULT '',
    fetched_at      DATETIME NOT NULL,
    expires_at      DATETIME NOT NULL,
    UNIQUE KEY uk_hash_slot (tmdb_id, media_type, season_number, episode_number, infohash),
    INDEX idx_slot (tmdb_id, season_number, episode_number),
    INDEX idx_recommended (tmdb_id, season_number, episode_number, is_recommended)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
