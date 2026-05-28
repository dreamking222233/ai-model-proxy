-- Grok 视频模型接入：允许统一模型类型使用 video，并预置 grok-imagine-video。

ALTER TABLE `unified_model`
    MODIFY COLUMN `model_type` ENUM('chat', 'embedding', 'image', 'video') NOT NULL DEFAULT 'chat';

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`,
    `image_credit_multiplier`, `enabled`, `description`
) VALUES (
    'grok-imagine-video', 'Grok Imagine Video', 'video', 'openai', NULL,
    0, 0, 'image_credit', 0.500, 1, 'Grok Imagine 视频生成模型（按媒体积分计费，默认 0.5 积分/秒，需映射到 grok2api 渠道）'
) ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `protocol_type` = VALUES(`protocol_type`),
    `billing_type` = VALUES(`billing_type`),
    `image_credit_multiplier` = VALUES(`image_credit_multiplier`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);
