-- ChatGPT Image 渠道接入升级脚本
-- 日期：2026-04-22

INSERT INTO `unified_model` (
  `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
  `input_price_per_million`, `output_price_per_million`, `billing_type`, `image_credit_multiplier`, `enabled`, `description`
)
SELECT * FROM (
  SELECT 'gpt-image-2', 'GPT Image 2', 'image', 'openai', NULL, 0, 0, 'image_credit', 0.5, 1,
         'OpenAI 兼容图片生成模型 GPT Image 2（按图片积分计费）'
) AS tmp
WHERE NOT EXISTS (
  SELECT 1 FROM `unified_model` WHERE `model_name` = 'gpt-image-2'
);

UPDATE `unified_model`
SET `protocol_type` = 'openai', `model_type` = 'image', `billing_type` = 'image_credit', `image_credit_multiplier` = 0.5
WHERE `model_name` = 'gpt-image-2';

-- 可选：将下列变量改成真实值后执行，可自动创建 ChatGPT Image 渠道与映射。
SET @chatgpt_image_api_key = NULL;
SET @chatgpt_image_channel_name = 'ChatGPT Image Compatible';
SET @chatgpt_image_base_url = 'http://43.156.153.12:3000';

INSERT INTO `channel` (
  `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
  `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
  @chatgpt_image_channel_name, @chatgpt_image_base_url, @chatgpt_image_api_key,
  'openai', 'openai-image-compatible', 'authorization',
  10, 1, 0, 1, 100, 0, 'OpenAI 兼容图片生成渠道，固定上游模型 gpt-image-2'
FROM DUAL
WHERE @chatgpt_image_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel`
    WHERE `protocol_type` = 'openai'
      AND `provider_variant` = 'openai-image-compatible'
      AND `base_url` = @chatgpt_image_base_url
  );

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gpt-image-2', 1
FROM `unified_model` um
JOIN `channel` ch
  ON ch.`protocol_type` = 'openai'
 AND ch.`provider_variant` = 'openai-image-compatible'
 AND ch.`base_url` = @chatgpt_image_base_url
WHERE @chatgpt_image_api_key IS NOT NULL
  AND um.`model_name` = 'gpt-image-2'
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

SET @chatgpt_image_api_key = NULL;
SET @chatgpt_image_channel_name = NULL;
SET @chatgpt_image_base_url = NULL;
