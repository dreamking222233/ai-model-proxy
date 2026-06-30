-- Geek2API gpt-image-2 图片渠道接入
-- 日期：2026-06-30
--
-- 使用方式：
-- 1. 渠道 protocol_type 使用 openai。
-- 2. 渠道 provider_variant 使用 geek2api-image。
-- 3. 渠道 base_url 填 https://www.geek2api.com 或 https://www.geek2api.com/v1。
-- 4. api_key 使用 Geek2API 图片专用密钥，认证头使用 Authorization: Bearer。
-- 5. 模型映射 actual_model_name 配置为 gpt-image-2。
-- 6. 本脚本默认不保存真实 API Key；如需自动创建渠道，把 @geek2api_image_api_key 从 NULL 改成真实密钥后执行。

ALTER TABLE `channel`
    MODIFY COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default'
    COMMENT '渠道子类型: default/openai-image-compatible/openai-image-native-size/openai-image-modelinvoke/geek2api-image/cpa-grok-video/google-official/google-vertex-image';

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`,
    `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('gpt-image-2', 'GPT Image 2', 'image', 'gpt', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 1, 1, 'Geek2API/OpenAI 兼容图片生成模型 GPT Image 2（按图片积分计费）')
ON DUPLICATE KEY UPDATE
    `model_name` = `model_name`;

INSERT INTO `model_image_resolution_rule` (
    `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '1K', 1, 0.500, 1, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gpt-image-2'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '1K'
  );

INSERT INTO `model_image_resolution_rule` (
    `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '2K', 1, 0.700, 0, 20
FROM `unified_model` um
WHERE um.`model_name` = 'gpt-image-2'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '2K'
  );

INSERT INTO `model_image_resolution_rule` (
    `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '4K', 1, 1.200, 0, 30
FROM `unified_model` um
WHERE um.`model_name` = 'gpt-image-2'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '4K'
  );

SET @geek2api_image_api_key = NULL;
SET @geek2api_image_channel_name = 'Geek2API gpt-image-2';
SET @geek2api_image_base_url = 'https://www.geek2api.com';

INSERT INTO `channel` (
    `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
    `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
    @geek2api_image_channel_name, @geek2api_image_base_url, @geek2api_image_api_key,
    'openai', 'geek2api-image', 'authorization',
    10, 1, 0, 1, 100, 0, 'Geek2API 图片生成渠道，固定上游模型 gpt-image-2，支持 1K/2K/4K、n/quality'
FROM DUAL
WHERE @geek2api_image_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel`
    WHERE `protocol_type` = 'openai'
      AND `provider_variant` = 'geek2api-image'
      AND `base_url` = @geek2api_image_base_url
  );

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gpt-image-2', 1
FROM `unified_model` um
JOIN `channel` ch
  ON ch.`protocol_type` = 'openai'
 AND ch.`provider_variant` = 'geek2api-image'
 AND ch.`base_url` = @geek2api_image_base_url
WHERE @geek2api_image_api_key IS NOT NULL
  AND um.`model_name` = 'gpt-image-2'
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

UPDATE `channel`
SET `health_check_enabled` = 0
WHERE `provider_variant` = 'geek2api-image';

SET @geek2api_image_api_key = NULL;
SET @geek2api_image_channel_name = NULL;
SET @geek2api_image_base_url = NULL;
