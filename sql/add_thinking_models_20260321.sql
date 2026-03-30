-- ============================================================
-- Thinking 模式支持 - 数据库迁移脚本
-- 日期: 2026-03-21
-- 功能: 添加 Claude Thinking 模式模型支持
-- ============================================================

-- 1. 添加统一模型定义
INSERT INTO `unified_model` (`id`, `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`, `input_price_per_million`, `output_price_per_million`, `enabled`, `description`) VALUES
(26, 'claude-sonnet-4-5-thinking', 'Claude Sonnet 4.5 Thinking', 'chat', 'openai', 8192, 3.000000, 15.000000, 1, 'Claude Sonnet 4.5 with extended thinking capability'),
(27, 'claude-haiku-4-5-thinking', 'Claude Haiku 4.5 Thinking', 'chat', 'openai', 8192, 0.800000, 4.000000, 1, 'Claude Haiku 4.5 with extended thinking capability')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `max_tokens` = VALUES(`max_tokens`),
    `input_price_per_million` = VALUES(`input_price_per_million`),
    `output_price_per_million` = VALUES(`output_price_per_million`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

-- 2. 添加模型-渠道映射
-- 渠道 9: 43.156.153.12-Claude
-- 注意: claude-sonnet-4-5-thinking 映射到 claude-sonnet-4.5 (上游实际请求的模型名)
INSERT INTO `model_channel_mapping` (`id`, `unified_model_id`, `channel_id`, `actual_model_name`, `enabled`) VALUES
(51, 26, 9, 'claude-sonnet-4.5', 1),
(52, 27, 9, 'claude-haiku-4-5-thinking', 1)
ON DUPLICATE KEY UPDATE
    `actual_model_name` = VALUES(`actual_model_name`),
    `enabled` = VALUES(`enabled`);

-- ============================================================
-- 验证查询
-- ============================================================

-- 查看新增的统一模型
SELECT id, model_name, display_name, enabled
FROM unified_model
WHERE model_name LIKE '%thinking%';

-- 查看新增的模型映射
SELECT m.id, m.unified_model_id, u.model_name, m.channel_id, c.name as channel_name, m.actual_model_name, m.enabled
FROM model_channel_mapping m
JOIN unified_model u ON m.unified_model_id = u.id
JOIN channel c ON m.channel_id = c.id
WHERE u.model_name LIKE '%thinking%';
