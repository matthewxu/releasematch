-- ReleaseMatch Cloudflare D1 上线表
-- 独立 D1 数据库，不与 subtitle-portal 共享

CREATE TABLE IF NOT EXISTS download_resources (
    id            TEXT PRIMARY KEY,
    tmdb_id       INTEGER NOT NULL,
    media_type    TEXT NOT NULL,
    season        INTEGER,
    episode       INTEGER,
    title_raw     TEXT NOT NULL,
    release_group TEXT,
    source        TEXT,
    resolution    TEXT,
    codec         TEXT,
    size_bytes    INTEGER,
    seeders       INTEGER,
    magnet_uri    TEXT,
    is_recommended INTEGER DEFAULT 0,
    recommend_reason TEXT,
    cross_source_confidence REAL DEFAULT 0,
    indexed_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dl_tmdb_ep ON download_resources(tmdb_id, season, episode);
CREATE INDEX IF NOT EXISTS idx_dl_recommended ON download_resources(tmdb_id, season, episode, is_recommended);
