-- Media workbench channel alignment
-- Date: 2026-06-20
--
-- Purpose:
-- 1. Ensure the ChatGPT Image Compatible channel uses the verified 1K endpoint.
-- 2. Ensure gpt-image-2 has 1K/2K/4K media-credit rules.
-- 3. Keep the compatible mapping enabled so 1K requests can prefer this channel.

SET @gpt_image_model = CONVERT('gpt-image-2' USING utf8mb4) COLLATE utf8mb4_unicode_ci;
SET @chatgpt_image_channel_name = CONVERT('ChatGPT Image Compatible' USING utf8mb4) COLLATE utf8mb4_unicode_ci;
SET @chatgpt_image_base_url = CONVERT('http://43.128.147.93:3000' USING utf8mb4) COLLATE utf8mb4_unicode_ci;
-- Set this variable before executing in production if the stored API key also needs to be refreshed.
-- Example: SET @chatgpt_image_api_key = 'your-compatible-api-key';
SET @chatgpt_image_api_key = NULL;

INSERT INTO `unified_model` (
  `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
  `input_price_per_million`, `output_price_per_million`, `billing_type`,
  `image_credit_multiplier`, `enabled`, `description`
)
SELECT
  @gpt_image_model,
  'GPT Image 2',
  'image',
  'openai',
  NULL,
  0,
  0,
  'image_credit',
  0.5,
  1,
  'OpenAI 兼容图片生成模型 GPT Image 2（按图片积分计费）'
WHERE NOT EXISTS (
  SELECT 1 FROM `unified_model` WHERE `model_name` = @gpt_image_model
);

UPDATE `unified_model`
SET
  `protocol_type` = 'openai',
  `model_type` = 'image',
  `billing_type` = 'image_credit',
  `image_credit_multiplier` = 0.5,
  `enabled` = 1
WHERE `model_name` = @gpt_image_model;

INSERT INTO `channel` (
  `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
  `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
  @chatgpt_image_channel_name,
  @chatgpt_image_base_url,
  @chatgpt_image_api_key,
  'openai',
  'openai-image-compatible',
  'authorization',
  10,
  1,
  0,
  1,
  100,
  0,
  'OpenAI 兼容图片生成渠道，固定上游模型 gpt-image-2'
FROM DUAL
WHERE @chatgpt_image_api_key IS NOT NULL
  AND NOT EXISTS (
  SELECT 1 FROM `channel` WHERE `name` = @chatgpt_image_channel_name
);

UPDATE `channel`
SET
  `base_url` = @chatgpt_image_base_url,
  `api_key` = COALESCE(@chatgpt_image_api_key, `api_key`),
  `protocol_type` = 'openai',
  `provider_variant` = 'openai-image-compatible',
  `auth_header_type` = 'authorization',
  `priority` = 10,
  `enabled` = 1,
  `health_check_enabled` = 0,
  `is_healthy` = 1,
  `health_score` = 100,
  `failure_count` = 0,
  `circuit_breaker_until` = NULL,
  `description` = 'OpenAI 兼容图片生成渠道，固定上游模型 gpt-image-2'
WHERE `name` = @chatgpt_image_channel_name;

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, @gpt_image_model, 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @chatgpt_image_channel_name
WHERE um.`model_name` = @gpt_image_model
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

UPDATE `model_channel_mapping` m
JOIN `unified_model` um ON um.id = m.unified_model_id
JOIN `channel` ch ON ch.id = m.channel_id
SET
  m.`actual_model_name` = @gpt_image_model,
  m.`enabled` = 1
WHERE um.`model_name` = @gpt_image_model
  AND ch.`name` = @chatgpt_image_channel_name;

INSERT INTO `model_image_resolution_rule` (
  `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '1K', 1, 0.500, 1, 10
FROM `unified_model` um
WHERE um.`model_name` = @gpt_image_model
ON DUPLICATE KEY UPDATE
  `enabled` = VALUES(`enabled`),
  `credit_cost` = VALUES(`credit_cost`),
  `is_default` = VALUES(`is_default`),
  `sort_order` = VALUES(`sort_order`);

INSERT INTO `model_image_resolution_rule` (
  `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '2K', 1, 0.700, 0, 20
FROM `unified_model` um
WHERE um.`model_name` = @gpt_image_model
ON DUPLICATE KEY UPDATE
  `enabled` = VALUES(`enabled`),
  `credit_cost` = VALUES(`credit_cost`),
  `is_default` = VALUES(`is_default`),
  `sort_order` = VALUES(`sort_order`);

INSERT INTO `model_image_resolution_rule` (
  `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '4K', 1, 1.200, 0, 30
FROM `unified_model` um
WHERE um.`model_name` = @gpt_image_model
ON DUPLICATE KEY UPDATE
  `enabled` = VALUES(`enabled`),
  `credit_cost` = VALUES(`credit_cost`),
  `is_default` = VALUES(`is_default`),
  `sort_order` = VALUES(`sort_order`);

SET @gpt_image_model = NULL;
SET @chatgpt_image_channel_name = NULL;
SET @chatgpt_image_base_url = NULL;
SET @chatgpt_image_api_key = NULL;
