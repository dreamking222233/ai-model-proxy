-- 119337 Grok 视频工作台增强。
-- 本脚本不写入 API Key，不覆盖渠道 Base URL，也不自动停用其他渠道。

ALTER TABLE `channel`
    MODIFY COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default'
    COMMENT '渠道子类型: default/openai-image-compatible/openai-image-native-size/openai-image-modelinvoke/geek2api-image/cpa-grok-video/grok-video-119337/zz1cc-video/google-official/google-vertex-image';

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`,
    `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('grok-video', 'Grok 视频', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1,
 '119337 grok-image-video 通用视频模型：文生最长 15 秒，上传参考图最长 10 秒，最多 7 张参考图'),
('grok-imagine-video-1.5-preview', 'Grok 视频 1.5 预览', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1,
 '119337 grok-video-1.5 单图生视频模型：必须且只能上传 1 张参考图，最长 15 秒')
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

-- 119337 使用 OpenAI Bearer 鉴权形式，但实际视频路径由 provider_variant 适配器处理。
UPDATE `channel`
SET `protocol_type` = 'openai',
    `auth_header_type` = 'authorization',
    `health_check_enabled` = 0
WHERE `provider_variant` = 'grok-video-119337';

-- 管理员安全创建新渠道并写入真实 Base URL/API Key 后，可执行以下幂等映射模板：
-- INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
-- SELECT um.id, ch.id,
--        CASE WHEN um.model_name = 'grok-imagine-video-1.5-preview'
--             THEN 'grok-video-1.5' ELSE 'grok-image-video' END,
--        1
-- FROM `unified_model` um
-- JOIN `channel` ch ON ch.`provider_variant` = 'grok-video-119337' AND ch.`name` = '你的新渠道名称'
-- WHERE um.`model_name` IN ('grok-video', 'grok-imagine-video-1.5-preview')
-- ON DUPLICATE KEY UPDATE
--     `actual_model_name` = VALUES(`actual_model_name`),
--     `enabled` = VALUES(`enabled`);
