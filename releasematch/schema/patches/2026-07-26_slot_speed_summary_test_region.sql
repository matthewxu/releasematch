-- 为已有库追加测速出口区域字段（新装请直接用 mysql_schema.sql）
-- 用法：mysql -h… -u… -p releasematch < schema/patches/2026-07-26_slot_speed_summary_test_region.sql
-- 若列已存在，ADD COLUMN 会报 Duplicate column，可忽略后继续执行 UPDATE。

ALTER TABLE slot_speed_summary
  ADD COLUMN test_region VARCHAR(32) DEFAULT ''
    COMMENT '测速出口区域 ID，如 jp-osa'
    AFTER reachability;

-- 回填历史行：与当前默认出口一致（可按实际 VPS 修改）
UPDATE slot_speed_summary
SET test_region = 'jp-osa'
WHERE test_region IS NULL OR test_region = '';
