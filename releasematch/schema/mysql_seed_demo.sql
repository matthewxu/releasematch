-- =============================================================================
-- ReleaseMatch MySQL 演示种子数据
-- =============================================================================
-- 对齐 portal 设计演示页；依赖 mysql_schema.sql
-- =============================================================================

SET NAMES utf8mb4;

INSERT INTO release_groups (name, aliases, tier, scene_compliant, compliance_rate, notes, updated_at) VALUES
('NTb', '["NITROUS"]', 'L0', 1, 0.98, '顶级 P2P 组，WEB-DL 质量标杆', '2026-06-29 00:00:00.000'),
('HiFi', '[]', 'L1', 1, 0.92, '主流 WEB-DL 组', '2026-06-29 00:00:00.000'),
('SPARKS', '[]', 'L1', 1, 0.95, 'Scene BluRay 组', '2026-06-29 00:00:00.000'),
('YIFY', '["YTS","YTS.MX"]', 'L3', 0, 0.40, '低码率高压缩', '2026-06-29 00:00:00.000')
ON DUPLICATE KEY UPDATE
    tier=VALUES(tier), scene_compliant=VALUES(scene_compliant),
    compliance_rate=VALUES(compliance_rate), notes=VALUES(notes), updated_at=VALUES(updated_at);

INSERT INTO media_catalog (
    catalog_id, tmdb_id, media_kind, slug, title, overview, year,
    runtime_minutes, poster_path, tmdb_url, streaming_providers,
    subtitle_url_pattern, updated_at
) VALUES
(
    'tv:1396', 1396, 'tv', 'breaking-bad', 'Breaking Bad',
    '高中化学老师 Walter White 踏入制毒之路。以下为验证集演示：第 4 季部分集数。',
    2008, NULL,
    '/t/p/w300/ggFHVNu6YYI5L9pCfOacjizRGh.jpg',
    'https://www.themoviedb.org/tv/1396',
    '["Netflix","AMC+"]',
    'https://subtitleportal.com/subtitle/breaking-bad/s{s}e{e}/',
    '2026-06-29 00:00:00.000'
),
(
    'movie:27205', 27205, 'movie', 'inception-2010', 'Inception',
    '电影页侧重多版本画质、音轨与体积分档对比。',
    2010, 148,
    '/t/p/w300/9gk7adcrE0ForQLDz3i0hHaI2v.jpg',
    'https://www.themoviedb.org/movie/27205',
    '[]',
    '',
    '2026-06-29 00:00:00.000'
)
ON DUPLICATE KEY UPDATE
    title=VALUES(title), overview=VALUES(overview), year=VALUES(year),
    runtime_minutes=VALUES(runtime_minutes), poster_path=VALUES(poster_path),
    tmdb_url=VALUES(tmdb_url), streaming_providers=VALUES(streaming_providers),
    subtitle_url_pattern=VALUES(subtitle_url_pattern), updated_at=VALUES(updated_at);

INSERT INTO media_pages (
    page_id, catalog_id, page_type, season, episode, episode_title, air_date, overview,
    cross_source_count, cross_source_total,
    prev_season, prev_episode, next_season, next_episode,
    magnet_count, page_status, robots_noindex, canonical_path, subtitle_url,
    generated_at, updated_at
) VALUES
('tv:1396:hub', 'tv:1396', 'show_hub', NULL, NULL, '', NULL, '', 0, 3, NULL, NULL, NULL, NULL, 0, 'published', 0, '/breaking-bad/', '', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e01', 'tv:1396', 'episode', 4, 1, '', '2011-07-17', '', 2, 3, NULL, NULL, 4, 2, 4, 'published', 0, '/breaking-bad/s4e1/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e1/', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e02', 'tv:1396', 'episode', 4, 2, '', '2011-07-24', '', 2, 3, 4, 1, 4, 3, 4, 'published', 0, '/breaking-bad/s4e2/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e2/', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e03', 'tv:1396', 'episode', 4, 3, '', '2011-07-31', '', 2, 3, 4, 2, 4, 4, 4, 'published', 0, '/breaking-bad/s4e3/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e3/', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e04', 'tv:1396', 'episode', 4, 4, '', '2011-08-07', '', 2, 3, 4, 3, 4, 5, 4, 'published', 0, '/breaking-bad/s4e4/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e4/', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e05', 'tv:1396', 'episode', 4, 5, '', '2011-08-14', '', 2, 3, 4, 4, 4, 6, 4, 'published', 0, '/breaking-bad/s4e5/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e5/', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e06', 'tv:1396', 'episode', 4, 6, 'Cornered', '2011-08-14', 'Skyler 开始怀疑 Walter 的真实身份，夫妻之间的紧张关系达到新高度。', 3, 3, 4, 5, 4, 7, 8, 'published', 0, '/breaking-bad/s4e6/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e6/', NULL, '2026-06-28 12:00:00.000'),
('tv:1396:s04e07', 'tv:1396', 'episode', 4, 7, '', '2011-08-21', '', 2, 3, 4, 6, 4, 8, 4, 'published', 0, '/breaking-bad/s4e7/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e7/', NULL, '2026-06-29 00:00:00.000'),
('tv:1396:s04e08', 'tv:1396', 'episode', 4, 8, '', '2011-08-28', '', 2, 3, 4, 7, NULL, NULL, 4, 'published', 0, '/breaking-bad/s4e8/', 'https://subtitleportal.com/subtitle/breaking-bad/s4e8/', NULL, '2026-06-29 00:00:00.000'),
('movie:27205', 'movie:27205', 'movie', NULL, NULL, '', NULL, '', 2, 3, NULL, NULL, NULL, NULL, 5, 'published', 0, '/inception-2010/', '', NULL, '2026-06-29 00:00:00.000')
ON DUPLICATE KEY UPDATE
    cross_source_count=VALUES(cross_source_count), magnet_count=VALUES(magnet_count),
    page_status=VALUES(page_status), overview=VALUES(overview),
    episode_title=VALUES(episode_title), updated_at=VALUES(updated_at);

INSERT INTO slot_speed_summary (page_id, recommended_infohash, recommended_speed, reachability, updated_at) VALUES
('tv:1396:s04e06', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '4.2 MB/s', '高', '2026-06-28 12:00:00.000')
ON DUPLICATE KEY UPDATE
    recommended_infohash=VALUES(recommended_infohash),
    recommended_speed=VALUES(recommended_speed),
    reachability=VALUES(reachability),
    updated_at=VALUES(updated_at);

INSERT INTO download_resources (
    id, page_id, tmdb_id, media_type, season, episode, infohash,
    title_raw, release_group, source, resolution, codec,
    video_spec, audio_spec, size_bytes, seeders, peers, magnet_uri, indexer,
    is_recommended, match_score, recommend_reason, group_tier,
    cross_source_count, cross_source_confidence, indexed_at, expires_at
) VALUES
(
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'tv:1396:s04e06', 1396, 'tv_episode', 4, 6,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'Breaking.Bad.S04E06.1080p.WEB-DL.DDP5.1.H.264-NTb', 'NTb', 'WEB-DL（Amazon Prime US）', '1080p', 'H.264',
    'H.264 1080p ~8 Mbps', 'DDP5.1 @ 640 kbps', 2576980378, 24, 30,
    'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=Breaking.Bad.S04E06.1080p.WEB-DL-NTb',
    'jackett', 1, 92.5,
    'Verified Group NTb（L0 档信誉）；来源 WEB-DL（Amazon Prime US）；DDP5.1 经校验无音轨延迟；跨 3 个数据源交叉验证；当前 24 seeders',
    'L0', 3, 1.0, '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
),
(
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'tv:1396:s04e06', 1396, 'tv_episode', 4, 6,
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'Breaking.Bad.S04E06.1080p.WEB-DL.H.264-HiFi', 'HiFi', 'WEB-DL', '1080p', 'H.264',
    'H.264 1080p', 'DDP5.1', 2469606195, 18, 22,
    'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'eztv', 0, 78.0, '', 'L1', 2, 0.67,
    '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
),
(
    'cccccccccccccccccccccccccccccccccccccccc', 'tv:1396:s04e06', 1396, 'tv_episode', 4, 6,
    'cccccccccccccccccccccccccccccccccccccccc',
    'Breaking.Bad.S04E06.720p.WEB-DL.H.264-BTN', 'BTN', 'WEB-DL', '720p', 'H.264',
    'H.264 720p', 'DDP5.1', 1181116006, 31, 35,
    'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc', 'jackett', 0, 72.0, '', 'L2', 2, 0.67,
    '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
),
(
    'dddddddddddddddddddddddddddddddddddddddd', 'tv:1396:s04e06', 1396, 'tv_episode', 4, 6,
    'dddddddddddddddddddddddddddddddddddddddd',
    'Breaking.Bad.S04E06.1080p.BluRay.x264-ROVERS', 'ROVERS', 'BluRay', '1080p', 'x264',
    'x264 1080p', 'DTS-HD MA 5.1', 4402341478, 9, 12,
    'magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd', 'jackett', 0, 65.0, '', 'L1', 1, 0.33,
    '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
),
(
    'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'movie:27205', 27205, 'movie', NULL, NULL,
    'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
    'Inception.2010.1080p.BluRay.x264-SPARKS', 'SPARKS', 'BluRay', '1080p', 'x264',
    'x264 1080p', 'DTS-HD MA 5.1', 12992243712, 15, 18,
    'magnet:?xt=urn:btih:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'jackett', 1, 88.0,
    'Scene 合规 BluRay 压制；DTS-HD MA 音轨完整；体积与码率平衡最佳', 'L1', 2, 0.67,
    '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
),
(
    'ffffffffffffffffffffffffffffffffffffffff', 'movie:27205', 27205, 'movie', NULL, NULL,
    'ffffffffffffffffffffffffffffffffffffffff',
    'Inception.2010.2160p.UHD.BluRay.x265-HDR', 'HDR', 'BluRay', '2160p', 'HEVC',
    'HEVC 2160p HDR', 'DTS-HD MA 7.1', 30480530637, 6, 8,
    'magnet:?xt=urn:btih:ffffffffffffffffffffffffffffffffffffffff', 'jackett', 0, 70.0, '', 'L2', 1, 0.33,
    '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
),
(
    '1111111111111111111111111111111111111111', 'movie:27205', 27205, 'movie', NULL, NULL,
    '1111111111111111111111111111111111111111',
    'Inception.2010.720p.BluRay.x264-YIFY', 'YIFY', 'BluRay', '720p', 'x264',
    'x264 720p', 'AAC 2.0', 943718400, 42, 50,
    'magnet:?xt=urn:btih:1111111111111111111111111111111111111111', 'yts', 0, 45.0, '', 'L3', 1, 0.33,
    '2026-06-28 10:00:00.000', '2026-07-05 10:00:00.000'
)
ON DUPLICATE KEY UPDATE
    title_raw=VALUES(title_raw), seeders=VALUES(seeders), is_recommended=VALUES(is_recommended),
    match_score=VALUES(match_score), recommend_reason=VALUES(recommend_reason),
    indexed_at=VALUES(indexed_at), expires_at=VALUES(expires_at);
