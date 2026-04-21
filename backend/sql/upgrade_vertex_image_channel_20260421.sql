-- Vertex 图片渠道接入升级脚本
-- 日期：2026-04-21

SET @add_provider_variant = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'channel'
        AND COLUMN_NAME = 'provider_variant'
    ),
    'SELECT 1',
    "ALTER TABLE `channel` ADD COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default' COMMENT '渠道子类型: default/google-official/google-vertex-image' AFTER `protocol_type`"
  )
);
PREPARE stmt FROM @add_provider_variant;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE `channel`
SET `provider_variant` = 'google-official'
WHERE `protocol_type` = 'google'
  AND (`provider_variant` IS NULL OR `provider_variant` = '' OR `provider_variant` = 'default');

UPDATE `channel`
SET `provider_variant` = 'default'
WHERE `protocol_type` <> 'google'
  AND (`provider_variant` IS NULL OR `provider_variant` = '');

-- 可选：将 @vertex_api_key 改成真实值后执行，可自动创建 Vertex 渠道
SET @vertex_api_key = NULL;
SET @vertex_channel_name = 'Google Vertex Image';
SET @vertex_base_url = 'https://aiplatform.googleapis.com';

INSERT INTO `channel` (
  `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
  `priority`, `enabled`, `is_healthy`, `health_score`, `failure_count`, `health_check_model`, `description`
)
SELECT
  @vertex_channel_name, @vertex_base_url, @vertex_api_key, 'google', 'google-vertex-image', 'x-goog-api-key',
  2, 1, 1, 100, 0, 'gemini-2.5-flash', 'Google Vertex 图片生成渠道'
FROM DUAL
WHERE @vertex_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel`
    WHERE `protocol_type` = 'google'
      AND `provider_variant` = 'google-vertex-image'
      AND `base_url` = @vertex_base_url
  );

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002', 1
FROM `unified_model` um
JOIN `channel` ch
  ON ch.`protocol_type` = 'google'
 AND ch.`provider_variant` = 'google-vertex-image'
 AND ch.`base_url` = @vertex_base_url
WHERE @vertex_api_key IS NOT NULL
  AND um.`model_name` = 'gemini-2.5-flash-image'
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-3.1-flash-image-preview', 1
FROM `unified_model` um
JOIN `channel` ch
  ON ch.`protocol_type` = 'google'
 AND ch.`provider_variant` = 'google-vertex-image'
 AND ch.`base_url` = @vertex_base_url
WHERE @vertex_api_key IS NOT NULL
  AND um.`model_name` = 'gemini-3.1-flash-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-3-pro-image-preview', 1
FROM `unified_model` um
JOIN `channel` ch
  ON ch.`protocol_type` = 'google'
 AND ch.`provider_variant` = 'google-vertex-image'
 AND ch.`base_url` = @vertex_base_url
WHERE @vertex_api_key IS NOT NULL
  AND um.`model_name` = 'gemini-3-pro-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

SET @vertex_api_key = NULL;
SET @vertex_channel_name = NULL;
SET @vertex_base_url = NULL;
