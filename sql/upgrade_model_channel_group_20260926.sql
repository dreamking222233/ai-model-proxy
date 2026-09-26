-- Model/channel group migration. Safe to execute repeatedly on MySQL 8.
SET @db := DATABASE();

CREATE TABLE IF NOT EXISTS `model_group` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `model_series` VARCHAR(32) NOT NULL,
  `code` VARCHAR(64) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `multiplier` DECIMAL(12,6) NOT NULL DEFAULT 1,
  `enabled` TINYINT NOT NULL DEFAULT 1,
  `is_default` TINYINT NOT NULL DEFAULT 0,
  `sort_order` INT NOT NULL DEFAULT 100,
  `description` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_group_series_code` (`model_series`, `code`),
  KEY `idx_model_group_series_enabled` (`model_series`, `enabled`, `is_default`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型系列渠道分组';

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='model_channel_mapping' AND column_name='group_id')=0,
  'ALTER TABLE model_channel_mapping ADD COLUMN group_id BIGINT UNSIGNED NULL AFTER unified_model_id', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Add each key column independently so a partially applied migration can be retried.
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='user_api_key' AND column_name='group_mode')=0,
  'ALTER TABLE user_api_key ADD COLUMN group_mode VARCHAR(16) NULL DEFAULT NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='user_api_key' AND column_name='group_model_series')=0,
  'ALTER TABLE user_api_key ADD COLUMN group_model_series VARCHAR(32) NULL DEFAULT NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='user_api_key' AND column_name='group_id')=0,
  'ALTER TABLE user_api_key ADD COLUMN group_id BIGINT UNSIGNED NULL DEFAULT NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='request_log' AND column_name='group_id_snapshot')=0,
  'ALTER TABLE request_log ADD COLUMN group_id_snapshot BIGINT UNSIGNED NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='request_log' AND column_name='group_name_snapshot')=0,
  'ALTER TABLE request_log ADD COLUMN group_name_snapshot VARCHAR(128) NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='request_log' AND column_name='group_multiplier_snapshot')=0,
  'ALTER TABLE request_log ADD COLUMN group_multiplier_snapshot DECIMAL(12,6) NULL DEFAULT 1', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='consumption_record' AND column_name='group_id_snapshot')=0,
  'ALTER TABLE consumption_record ADD COLUMN group_id_snapshot BIGINT UNSIGNED NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='consumption_record' AND column_name='group_name_snapshot')=0,
  'ALTER TABLE consumption_record ADD COLUMN group_name_snapshot VARCHAR(128) NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='consumption_record' AND column_name='group_multiplier_snapshot')=0,
  'ALTER TABLE consumption_record ADD COLUMN group_multiplier_snapshot DECIMAL(12,6) NULL DEFAULT 1', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='video_task_billing_snapshot' AND column_name='group_id_snapshot')=0,
  'ALTER TABLE video_task_billing_snapshot ADD COLUMN group_id_snapshot BIGINT UNSIGNED NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='video_task_billing_snapshot' AND column_name='group_name_snapshot')=0,
  'ALTER TABLE video_task_billing_snapshot ADD COLUMN group_name_snapshot VARCHAR(128) NULL', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='video_task_billing_snapshot' AND column_name='group_multiplier_snapshot')=0,
  'ALTER TABLE video_task_billing_snapshot ADD COLUMN group_multiplier_snapshot DECIMAL(12,6) NULL DEFAULT 1', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=@db AND table_name='video_task_billing_snapshot' AND column_name='global_price_multiplier_snapshot')=0,
  'ALTER TABLE video_task_billing_snapshot ADD COLUMN global_price_multiplier_snapshot DECIMAL(12,6) NULL DEFAULT 1 AFTER video_seconds', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Create one stable default group for every existing model series before backfilling mappings.
INSERT INTO model_group (model_series, code, name, multiplier, enabled, is_default, sort_order)
SELECT DISTINCT um.model_series, 'default', CONCAT(UPPER(LEFT(um.model_series, 1)), SUBSTRING(um.model_series, 2), ' 默认'), 1, 1, 1, 100
FROM unified_model um
WHERE NOT EXISTS (SELECT 1 FROM model_group mg WHERE mg.model_series=um.model_series AND mg.code='default');

-- Repair an earlier partial run that created a default row without marking it.
UPDATE model_group mg
LEFT JOIN (
  SELECT model_series
  FROM model_group
  WHERE enabled=1 AND is_default=1
  GROUP BY model_series
) active_default ON active_default.model_series=mg.model_series
SET mg.enabled=1, mg.is_default=1
WHERE mg.code='default' AND active_default.model_series IS NULL;

-- Normalize legacy data so every model series has exactly one enabled default.
CREATE TEMPORARY TABLE IF NOT EXISTS `_model_group_default_keep` (
  `model_series` VARCHAR(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL PRIMARY KEY,
  `group_id` BIGINT UNSIGNED NOT NULL
);
TRUNCATE TABLE `_model_group_default_keep`;
INSERT INTO `_model_group_default_keep` (`model_series`, `group_id`)
SELECT `model_series`, COALESCE(MIN(CASE WHEN `is_default`=1 THEN `id` END), MIN(`id`))
FROM `model_group`
WHERE `enabled`=1
GROUP BY `model_series`;
UPDATE `model_group` SET `is_default`=0 WHERE `enabled`<>1;
UPDATE `model_group` mg
JOIN `_model_group_default_keep` keep ON keep.`model_series`=mg.`model_series`
SET mg.`is_default`=IF(mg.`id`=keep.`group_id`, 1, 0)
WHERE mg.`enabled`=1;
DROP TEMPORARY TABLE `_model_group_default_keep`;

UPDATE model_channel_mapping m
JOIN unified_model um ON um.id=m.unified_model_id
JOIN model_group mg ON mg.model_series=um.model_series AND mg.enabled=1 AND mg.is_default=1
SET m.group_id=mg.id
WHERE m.group_id IS NULL;

SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=@db AND table_name='model_channel_mapping' AND index_name='uk_model_channel')>0,
  'ALTER TABLE model_channel_mapping DROP INDEX uk_model_channel', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=@db AND table_name='model_channel_mapping' AND index_name='uk_model_channel_group')=0,
  'ALTER TABLE model_channel_mapping ADD UNIQUE KEY uk_model_channel_group (unified_model_id, group_id, channel_id)', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=@db AND table_name='model_channel_mapping' AND index_name='idx_model_mapping_group')=0,
  'ALTER TABLE model_channel_mapping ADD KEY idx_model_mapping_group (group_id, enabled)', 'SELECT 1'); PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SELECT 'mapping_null_group_before_not_null' AS check_name, COUNT(*) AS count_value
FROM model_channel_mapping WHERE group_id IS NULL;
-- MySQL rejects this ALTER when any NULL remains, intentionally stopping the
-- migration instead of silently leaving a partially migrated nullable column.
ALTER TABLE model_channel_mapping MODIFY COLUMN group_id BIGINT UNSIGNED NOT NULL;

UPDATE user_api_key SET group_mode='unified' WHERE group_mode IS NULL OR group_mode='';
UPDATE user_api_key SET group_mode=LOWER(TRIM(group_mode));
UPDATE user_api_key SET group_mode='unified', group_model_series=NULL, group_id=NULL WHERE group_mode NOT IN ('unified','special');
UPDATE user_api_key k
LEFT JOIN model_group mg ON mg.id=k.group_id
SET k.group_mode='unified', k.group_model_series=NULL, k.group_id=NULL
WHERE k.group_mode='special'
  AND (k.group_id IS NULL OR k.group_model_series IS NULL OR mg.id IS NULL
    OR mg.enabled<>1 OR mg.model_series<>LOWER(TRIM(k.group_model_series)));

-- Post-migration checks: these result sets are intentionally visible to deployment logs.
SELECT 'model_group_missing_default' AS check_name, model_series
FROM model_group WHERE enabled=1 GROUP BY model_series
HAVING SUM(is_default=1)=0;
SELECT 'model_group_duplicate_default' AS check_name, model_series, COUNT(*) AS count_value
FROM model_group WHERE enabled=1 AND is_default=1 GROUP BY model_series
HAVING COUNT(*)>1;
SELECT 'mapping_missing_group' AS check_name, COUNT(*) AS count_value
FROM model_channel_mapping WHERE group_id IS NULL;
