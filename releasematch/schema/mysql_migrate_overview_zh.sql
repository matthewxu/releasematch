-- 增量迁移：media_catalog / media_pages 增加 overview_zh（已有库执行一次）
-- @file schema/mysql_migrate_overview_zh.sql
-- 用法：python -m workflow.run meta migrate-overview-zh
-- 或在 meta enrich 时自动检测补列

ALTER TABLE media_catalog
    ADD COLUMN overview_zh TEXT NULL COMMENT '简介（zh-CN）' AFTER overview;

ALTER TABLE media_pages
    ADD COLUMN overview_zh TEXT NULL COMMENT '槽位简介（zh-CN）' AFTER overview;
