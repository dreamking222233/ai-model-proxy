-- zz1cc 视频渠道接入说明：
-- 1. 渠道 protocol_type 使用 openai。
-- 2. 渠道 provider_variant 使用 zz1cc-video。
-- 3. 渠道 base_url 填 https://zz1cc.cc.cd 或 https://zz1cc.cc.cd/v1。
-- 4. api_key 使用 zz1cc token，认证头使用 Authorization: Bearer。
-- 5. 模型映射 actual_model_name 分别配置为 video-ds-2.0、video-ds-2.0-fast。
-- 6. 首版 seconds 默认 15 且仅允许 15；非 15 会返回 INVALID_VIDEO_SECONDS。
-- 7. 本脚本只 upsert 统一模型，不自动绑定未知渠道。

ALTER TABLE `unified_model`
    MODIFY COLUMN `model_type` ENUM('chat', 'embedding', 'image', 'video') NOT NULL DEFAULT 'chat';

ALTER TABLE `channel`
    MODIFY COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default'
    COMMENT '渠道子类型: default/openai-image-compatible/openai-image-native-size/openai-image-modelinvoke/cpa-grok-video/zz1cc-video/google-official/google-vertex-image';

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`,
    `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('video-ds-2.0', 'video-ds-2.0', 'video', 'other', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'zz1cc video-ds-2.0 视频生成模型（按媒体积分计费，默认 0.5 积分/秒，需映射到 zz1cc-video 渠道）'),
('video-ds-2.0-fast', 'video-ds-2.0-fast', 'video', 'other', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'zz1cc video-ds-2.0-fast 视频生成模型（按媒体积分计费，默认 0.5 积分/秒，需映射到 zz1cc-video 渠道）')
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
WHERE `provider_variant` = 'zz1cc-video';

-- 管理员创建 zz1cc-video 渠道后，可按需执行映射示例：
-- INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
-- SELECT um.id, ch.id, um.model_name, 1
-- FROM `unified_model` um
-- JOIN `channel` ch ON ch.`provider_variant` = 'zz1cc-video'
-- WHERE um.`model_name` IN ('video-ds-2.0', 'video-ds-2.0-fast')
--   AND NOT EXISTS (
--     SELECT 1 FROM `model_channel_mapping` m
--     WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
--   );
