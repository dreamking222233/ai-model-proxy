-- 119337 Grok 视频渠道接入说明：
-- 1. 渠道 protocol_type 使用 openai。
-- 2. 渠道 provider_variant 使用 grok-video-119337。
-- 3. 渠道 base_url 填 https://api.119337.xyz 或 https://api.119337.xyz/v1。
-- 4. api_key 使用 119337 控制台 API Key，认证头使用 Authorization: Bearer。
-- 5. 推荐把现有统一模型 grok-video 映射到 actual_model_name = grok-image-video。
-- 6. 如需单图 1.5 预览模型，可把 grok-imagine-video-1.5-preview 映射到 actual_model_name = grok-video-1.5。
-- 7. 本脚本只补充渠道类型注释和模型元数据，不保存真实 API Key，不自动绑定未知渠道。

ALTER TABLE `channel`
    MODIFY COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default'
    COMMENT '渠道子类型: default/openai-image-compatible/openai-image-native-size/openai-image-modelinvoke/geek2api-image/cpa-grok-video/grok-video-119337/zz1cc-video/google-official/google-vertex-image';

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`,
    `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('grok-video', 'Grok 视频', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'Grok 视频生成模型（可映射到 CPA Grok 或 119337 grok-image-video 渠道）'),
('grok-imagine-video-1.5-preview', 'Grok 视频 1.5 预览', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'Grok 1.5 单图生视频预览模型（可映射到 119337 grok-video-1.5 渠道）')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `model_series` = VALUES(`model_series`),
    `protocol_type` = VALUES(`protocol_type`),
    `billing_type` = VALUES(`billing_type`),
    `request_price` = VALUES(`request_price`),
    `image_credit_multiplier` = VALUES(`image_credit_multiplier`),
    `security_monitor_enabled` = VALUES(`security_monitor_enabled`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

UPDATE `channel`
SET `health_check_enabled` = 0
WHERE `provider_variant` = 'grok-video-119337';

-- 管理员创建 grok-video-119337 渠道后，可按需执行映射示例：
-- INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
-- SELECT um.id, ch.id,
--        CASE
--          WHEN um.`model_name` = 'grok-imagine-video-1.5-preview' THEN 'grok-video-1.5'
--          ELSE 'grok-image-video'
--        END AS actual_model_name,
--        1
-- FROM `unified_model` um
-- JOIN `channel` ch ON ch.`provider_variant` = 'grok-video-119337'
-- WHERE um.`model_name` IN ('grok-video', 'grok-imagine-video-1.5-preview')
--   AND NOT EXISTS (
--     SELECT 1 FROM `model_channel_mapping` m
--     WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
--   );
