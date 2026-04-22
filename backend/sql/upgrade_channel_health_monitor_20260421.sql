-- 渠道健康监控开关升级脚本
-- 日期：2026-04-21

SET @add_health_check_enabled = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'channel'
        AND COLUMN_NAME = 'health_check_enabled'
    ),
    'SELECT 1',
    "ALTER TABLE `channel` ADD COLUMN `health_check_enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否参与健康监控' AFTER `enabled`"
  )
);
PREPARE stmt FROM @add_health_check_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE `channel`
SET `health_check_enabled` = 1
WHERE `health_check_enabled` IS NULL;

UPDATE `channel`
SET `health_check_enabled` = 0
WHERE `protocol_type` = 'google'
  AND (
    `provider_variant` IN ('google-official', 'google-vertex-image')
    OR `provider_variant` IS NULL
    OR `provider_variant` = ''
    OR `provider_variant` = 'default'
  );
