-- Grok 渠道接入升级脚本
-- 日期：2026-04-22

SET @add_provider_variant = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'channel'
        AND COLUMN_NAME = 'provider_variant'
    ),
    'SELECT 1',
    "ALTER TABLE `channel` ADD COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default' AFTER `protocol_type`"
  )
);
PREPARE stmt FROM @add_provider_variant;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_auth_header_type = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'channel'
        AND COLUMN_NAME = 'auth_header_type'
    ),
    'SELECT 1',
    "ALTER TABLE `channel` ADD COLUMN `auth_header_type` VARCHAR(32) NOT NULL DEFAULT 'x-api-key' AFTER `provider_variant`"
  )
);
PREPARE stmt FROM @add_auth_header_type;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_health_check_enabled = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'channel'
        AND COLUMN_NAME = 'health_check_enabled'
    ),
    'SELECT 1',
    "ALTER TABLE `channel` ADD COLUMN `health_check_enabled` TINYINT NOT NULL DEFAULT 1 AFTER `enabled`"
  )
);
PREPARE stmt FROM @add_health_check_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT INTO `unified_model` (`model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`, `input_price_per_million`, `output_price_per_million`, `enabled`, `description`) VALUES
('grok-4.20-0309-non-reasoning', 'Grok 4.20 0309 Non-Reasoning', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 0309 非推理版（官方定价 2/6）'),
('grok-4.20-0309', 'Grok 4.20 0309', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 0309（按 4.20 主档推断定价 2/6）'),
('grok-4.20-0309-reasoning', 'Grok 4.20 0309 Reasoning', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 0309 推理版（官方定价 2/6）'),
('grok-4.20-fast', 'Grok 4.20 Fast', 'chat', 'openai', 128000, 0.200000, 0.500000, 1, 'xAI Grok 4.20 Fast（参照 4.1 fast 档推断定价 0.2/0.5）'),
('grok-4.20-auto', 'Grok 4.20 Auto', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 Auto（按 4.20 主档推断定价 2/6）'),
('grok-4.20-expert', 'Grok 4.20 Expert', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 Expert（按 4.20 高阶档推断定价 2/6）')
ON DUPLICATE KEY UPDATE
  `display_name` = VALUES(`display_name`),
  `protocol_type` = VALUES(`protocol_type`),
  `max_tokens` = VALUES(`max_tokens`),
  `input_price_per_million` = VALUES(`input_price_per_million`),
  `output_price_per_million` = VALUES(`output_price_per_million`),
  `enabled` = VALUES(`enabled`),
  `description` = VALUES(`description`);

SET @grok_api_key = NULL;
SET @grok_base_url = 'http://167.88.186.145:8000/v1';
SET @grok_openai_channel_name = 'Grok OpenAI';
SET @grok_anthropic_channel_name = 'Grok Anthropic';

INSERT INTO `channel` (`name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`, `priority`, `enabled`, `health_check_enabled`, `description`)
SELECT
  @grok_openai_channel_name,
  @grok_base_url,
  @grok_api_key,
  'openai',
  'default',
  'authorization',
  6,
  1,
  0,
  'Grok 文本渠道（OpenAI Chat / Responses）'
FROM DUAL
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel` WHERE `name` = @grok_openai_channel_name AND `base_url` = @grok_base_url
  );

INSERT INTO `channel` (`name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`, `priority`, `enabled`, `health_check_enabled`, `description`)
SELECT
  @grok_anthropic_channel_name,
  @grok_base_url,
  @grok_api_key,
  'anthropic',
  'default',
  'authorization',
  6,
  1,
  0,
  'Grok 文本渠道（Anthropic Messages）'
FROM DUAL
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel` WHERE `name` = @grok_anthropic_channel_name AND `base_url` = @grok_base_url
  );

UPDATE `channel`
SET
  `api_key` = @grok_api_key,
  `protocol_type` = 'openai',
  `provider_variant` = 'default',
  `auth_header_type` = 'authorization',
  `priority` = 6,
  `enabled` = 1,
  `health_check_enabled` = 0,
  `description` = 'Grok 文本渠道（OpenAI Chat / Responses）'
WHERE @grok_api_key IS NOT NULL
  AND `name` = @grok_openai_channel_name
  AND `base_url` = @grok_base_url;

UPDATE `channel`
SET
  `api_key` = @grok_api_key,
  `protocol_type` = 'anthropic',
  `provider_variant` = 'default',
  `auth_header_type` = 'authorization',
  `priority` = 6,
  `enabled` = 1,
  `health_check_enabled` = 0,
  `description` = 'Grok 文本渠道（Anthropic Messages）'
WHERE @grok_api_key IS NOT NULL
  AND `name` = @grok_anthropic_channel_name
  AND `base_url` = @grok_base_url;

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, grok.model_name, 1
FROM (
  SELECT 'grok-4.20-0309-non-reasoning' AS model_name
  UNION ALL SELECT 'grok-4.20-0309'
  UNION ALL SELECT 'grok-4.20-0309-reasoning'
  UNION ALL SELECT 'grok-4.20-fast'
  UNION ALL SELECT 'grok-4.20-auto'
  UNION ALL SELECT 'grok-4.20-expert'
) grok
JOIN `unified_model` um ON um.`model_name` = grok.`model_name`
JOIN `channel` ch
  ON ch.`base_url` = @grok_base_url
 AND ch.`name` IN (@grok_openai_channel_name, @grok_anthropic_channel_name)
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

SET @grok_api_key = NULL;
SET @grok_base_url = NULL;
SET @grok_openai_channel_name = NULL;
SET @grok_anthropic_channel_name = NULL;
