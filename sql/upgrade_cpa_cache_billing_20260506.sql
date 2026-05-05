-- CPA/上游真实缓存计费字段
-- 缓存创建只展示不额外计费；缓存读取按输入价格 10% 计费。

SET @db_name = DATABASE();

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `billable_input_tokens` INT DEFAULT 0 AFTER `total_tokens`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'billable_input_tokens'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `cache_read_cost` DECIMAL(12,6) DEFAULT 0 AFTER `quota_cycle_date`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'cache_read_cost'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `billable_cache_read_input_tokens` INT DEFAULT 0 AFTER `upstream_cache_read_input_tokens`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'billable_cache_read_input_tokens'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `input_price_per_million_snapshot` DECIMAL(12,6) DEFAULT 0 AFTER `cache_read_cost`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'input_price_per_million_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `output_price_per_million_snapshot` DECIMAL(12,6) DEFAULT 0 AFTER `input_price_per_million_snapshot`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'output_price_per_million_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `price_multiplier_snapshot` DECIMAL(12,6) DEFAULT 1 AFTER `output_price_per_million_snapshot`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'price_multiplier_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `request_log` ADD COLUMN `token_multiplier_snapshot` DECIMAL(12,6) DEFAULT 1 AFTER `price_multiplier_snapshot`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'token_multiplier_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `billable_input_tokens` INT DEFAULT 0 AFTER `total_tokens`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'billable_input_tokens'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `cache_read_cost` DECIMAL(12,6) DEFAULT 0 AFTER `input_cost`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'cache_read_cost'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `billable_cache_read_input_tokens` INT DEFAULT 0 AFTER `upstream_cache_read_input_tokens`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'billable_cache_read_input_tokens'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `input_price_per_million_snapshot` DECIMAL(12,6) DEFAULT 0 AFTER `total_cost`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'input_price_per_million_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `output_price_per_million_snapshot` DECIMAL(12,6) DEFAULT 0 AFTER `input_price_per_million_snapshot`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'output_price_per_million_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `price_multiplier_snapshot` DECIMAL(12,6) DEFAULT 1 AFTER `output_price_per_million_snapshot`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'price_multiplier_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `consumption_record` ADD COLUMN `token_multiplier_snapshot` DECIMAL(12,6) DEFAULT 1 AFTER `price_multiplier_snapshot`',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'consumption_record' AND COLUMN_NAME = 'token_multiplier_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE `request_log`
SET `billable_input_tokens` = COALESCE(`billable_input_tokens`, `input_tokens`, 0)
WHERE `billable_input_tokens` IS NULL OR `billable_input_tokens` = 0;

UPDATE `consumption_record`
SET `billable_input_tokens` = COALESCE(`billable_input_tokens`, `input_tokens`, 0)
WHERE `billable_input_tokens` IS NULL OR `billable_input_tokens` = 0;

UPDATE `request_log`
SET `billable_cache_read_input_tokens` = COALESCE(`billable_cache_read_input_tokens`, `upstream_cache_read_input_tokens`, 0)
WHERE `billable_cache_read_input_tokens` IS NULL OR `billable_cache_read_input_tokens` = 0;

UPDATE `consumption_record`
SET `billable_cache_read_input_tokens` = COALESCE(`billable_cache_read_input_tokens`, `upstream_cache_read_input_tokens`, 0)
WHERE `billable_cache_read_input_tokens` IS NULL OR `billable_cache_read_input_tokens` = 0;
