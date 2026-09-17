-- 渠道原生透传开关（仅文本模型）
-- 日期：2026-09-18

SET @add_passthrough_enabled = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'channel'
        AND COLUMN_NAME = 'passthrough_enabled'
    ),
    'SELECT 1',
    'ALTER TABLE `channel` ADD COLUMN `passthrough_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT ''文本模型原生透传：1开启，0关闭'' AFTER `enabled`'
  )
);
PREPARE stmt FROM @add_passthrough_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE `channel`
SET `passthrough_enabled` = 0
WHERE `passthrough_enabled` IS NULL;
