-- Grok Imagine 图片/视频渠道接入说明：
-- 1. 渠道 protocol_type 使用 openai，provider_variant 使用 grok-imagine。
-- 2. 鉴权 Authorization: Bearer <API_KEY>。
-- 3. Base URL 填渠道根地址或带 /v1 的地址；不要写成 119337 的 /v1/video/generations。
-- 4. 本脚本不写入 API Key，不写入生产 Base URL。
-- 5. 管理员在 /admin/channels 创建渠道后，按文末模板绑定模型映射。

ALTER TABLE `channel`
    MODIFY COLUMN `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default'
    COMMENT '渠道子类型: default/openai-image-compatible/openai-image-native-size/openai-image-modelinvoke/geek2api-image/cpa-grok-video/grok-video-119337/zz1cc-video/grok-imagine/google-official/google-vertex-image';

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`,
    `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('grok-imagine-image', 'Grok Imagine Image', 'image', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1,
 'Grok Imagine 图片 1.0：每张 0.5 媒体积分，分辨率 1K/2K'),
('grok-imagine-image-2.0', 'Grok Imagine Image 2.0', 'image', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1,
 'Grok Imagine 图片 2.0：每张 0.5 媒体积分，quality=low/medium/auto'),
('grok-imagine-video', 'Grok Imagine Video', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1,
 'Grok Imagine 视频 1.0：每条 0.5 媒体积分，文生/图生最长 15 秒，参考生最长 10 秒'),
('grok-imagine-video-1.5', 'Grok Imagine Video 1.5', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1,
 'Grok Imagine 视频 1.5：每条 0.5 媒体积分，T2V/I2V 可到 1080p，R2V 最高 720p')
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

INSERT INTO `model_image_resolution_rule` (
    `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '1K', 1, 0.500, 1, 10
FROM `unified_model` um
WHERE um.model_name IN ('grok-imagine-image', 'grok-imagine-image-2.0')
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.unified_model_id = um.id AND r.resolution_code = '1K'
  );

INSERT INTO `model_image_resolution_rule` (
    `unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`
)
SELECT um.id, '2K', 1, 0.500, 0, 20
FROM `unified_model` um
WHERE um.model_name IN ('grok-imagine-image', 'grok-imagine-image-2.0')
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.unified_model_id = um.id AND r.resolution_code = '2K'
  );

UPDATE `model_image_resolution_rule` r
JOIN `unified_model` um ON um.id = r.unified_model_id
SET r.credit_cost = 0.500
WHERE um.model_name IN ('grok-imagine-image', 'grok-imagine-image-2.0');

-- 管理员创建 grok-imagine 渠道后执行（替换渠道名称）：
-- INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
-- SELECT um.id, ch.id, um.model_name, 1
-- FROM `unified_model` um
-- JOIN `channel` ch ON ch.`provider_variant` = 'grok-imagine' AND ch.`name` = '你的新渠道名称'
-- WHERE um.`model_name` IN (
--     'grok-imagine-image',
--     'grok-imagine-image-2.0',
--     'grok-imagine-video',
--     'grok-imagine-video-1.5'
-- )
-- ON DUPLICATE KEY UPDATE
--     `actual_model_name` = VALUES(`actual_model_name`),
--     `enabled` = VALUES(`enabled`);
