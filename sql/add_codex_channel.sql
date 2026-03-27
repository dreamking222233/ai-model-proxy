-- ============================================================
-- 添加 43.156.153.12-codex 渠道和相关模型
-- ============================================================

-- 1. 添加新渠道
INSERT INTO `channel` (`name`, `base_url`, `api_key`, `protocol_type`, `priority`, `enabled`, `description`)
SELECT
    '43.156.153.12-codex',
    'http://43.156.153.12:8317/v1',
    'sk-YOUR-API-KEY-HERE',
    'openai',
    1,
    1,
    'GPT-5 Codex 系列模型渠道'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM `channel` WHERE `name` = '43.156.153.12-codex'
);

SELECT @channel_id := `id`
FROM `channel`
WHERE `name` = '43.156.153.12-codex'
LIMIT 1;

-- 1.1 添加 Claude Code 专用的 Anthropic 入口渠道
INSERT INTO `channel` (`name`, `base_url`, `api_key`, `protocol_type`, `priority`, `enabled`, `description`)
SELECT
    '43.156.153.12-codex转claude',
    src.`base_url`,
    src.`api_key`,
    'anthropic',
    1,
    1,
    'Anthropic 协议入口，内部转发到 Codex Responses / gpt-5.4，供 Claude Code 使用'
FROM `channel` src
WHERE src.`name` = '43.156.153.12-codex'
  AND NOT EXISTS (
      SELECT 1 FROM `channel` WHERE `name` = '43.156.153.12-codex转claude'
  );

UPDATE `channel` bridge
JOIN `channel` src
    ON src.`name` = '43.156.153.12-codex'
SET
    bridge.`base_url` = src.`base_url`,
    bridge.`api_key` = src.`api_key`,
    bridge.`protocol_type` = 'anthropic',
    bridge.`priority` = 1,
    bridge.`enabled` = 1,
    bridge.`description` = 'Anthropic 协议入口，内部转发到 Codex Responses / gpt-5.4，供 Claude Code 使用'
WHERE bridge.`name` = '43.156.153.12-codex转claude';

SELECT @claude_bridge_channel_id := `id`
FROM `channel`
WHERE `name` = '43.156.153.12-codex转claude'
LIMIT 1;

-- 2. 添加新模型（如果不存在）
INSERT INTO `unified_model` (`model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`, `input_price_per_million`, `output_price_per_million`, `enabled`, `description`) VALUES
('gpt-5.1-codex-mini', 'GPT-5.1 Codex Mini', 'chat', 'openai', 128000, 0.500000, 1.500000, 1, 'GPT-5.1 Codex Mini - 轻量级代码模型'),
('gpt-5', 'GPT-5', 'chat', 'openai', 128000, 2.500000, 7.500000, 1, 'GPT-5 - 基础模型'),
('gpt-5.1-codex-max', 'GPT-5.1 Codex Max', 'chat', 'openai', 128000, 4.000000, 12.000000, 1, 'GPT-5.1 Codex Max - 高性能代码模型'),
('gpt-5.4-mini', 'GPT-5.4 Mini', 'chat', 'openai', 128000, 0.800000, 2.400000, 1, 'GPT-5.4 Mini - 轻量级模型'),
('gpt-5-codex', 'GPT-5 Codex', 'chat', 'openai', 128000, 3.000000, 9.000000, 1, 'GPT-5 Codex - 代码专用模型'),
('gpt-5-codex-mini', 'GPT-5 Codex Mini', 'chat', 'openai', 128000, 0.600000, 1.800000, 1, 'GPT-5 Codex Mini - 轻量级代码模型'),
('claude-opus-4-6', 'Claude Opus 4.6', 'chat', 'anthropic', 32768, 5.000000, 20.000000, 1, 'Claude Opus 4.6 alias exposed via Anthropic and routed to GPT-5.4 high reasoning on Codex Responses')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `protocol_type` = VALUES(`protocol_type`),
    `max_tokens` = VALUES(`max_tokens`),
    `input_price_per_million` = VALUES(`input_price_per_million`),
    `output_price_per_million` = VALUES(`output_price_per_million`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

-- 3. 创建模型-渠道映射
-- gpt-5.1-codex-mini
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.1-codex-mini', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.1-codex-mini'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.2
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.2', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.2'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.2-codex
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.2-codex', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.2-codex'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.3-codex
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.3-codex', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.3-codex'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.1
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.1', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.1'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.1-codex-max
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.1-codex-max', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.1-codex-max'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.4
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.4', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.4'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.4-mini
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.4-mini', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.4-mini'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5-codex
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5-codex', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5-codex'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5-codex-mini
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5-codex-mini', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5-codex-mini'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- gpt-5.1-codex
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @channel_id, 'responses:gpt-5.1-codex', 1 FROM `unified_model` WHERE `model_name` = 'gpt-5.1-codex'
ON DUPLICATE KEY UPDATE `actual_model_name` = VALUES(`actual_model_name`), `enabled` = 1;

-- claude-opus-4-6 (Anthropic-facing alias to GPT-5.4 high reasoning on Responses API)
INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT id, @claude_bridge_channel_id, 'responses:gpt-5.4', 1 FROM `unified_model` WHERE `model_name` = 'claude-opus-4-6'
ON DUPLICATE KEY UPDATE `enabled` = 1, `actual_model_name` = VALUES(`actual_model_name`);

-- 完成
SELECT CONCAT('✓ 渠道添加完成，codex 渠道 ID: ', @channel_id, '，claude bridge 渠道 ID: ', @claude_bridge_channel_id) AS result;
