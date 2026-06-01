-- 模型渠道映射默认推理强度
-- 日期：2026-06-01

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'model_channel_mapping'
    AND COLUMN_NAME = 'default_reasoning_effort'
);

SET @ddl := IF(
  @column_exists = 0,
  'ALTER TABLE `model_channel_mapping` ADD COLUMN `default_reasoning_effort` VARCHAR(16) DEFAULT NULL COMMENT ''默认推理强度: minimal/low/medium/high/xhigh'' AFTER `actual_model_name`',
  'SELECT ''model_channel_mapping.default_reasoning_effort already exists'''
);

PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
