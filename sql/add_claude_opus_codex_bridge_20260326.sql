-- ============================================================
-- 兼容旧脚本名：当前最终语义为
-- claude-opus-4-6 -> 43.156.153.12-codex转claude -> responses:gpt-5.4
-- 用途：
-- 1. 确保 claude-opus-4-6 对外走 Anthropic 协议
-- 2. 新增 Anthropic 入口渠道 43.156.153.12-codex转claude
-- 3. 复制旧 codex 渠道的真实 API Key / base_url
-- 4. 禁用旧的 claude-opus-4-6 -> 43.156.153.12-codex 映射
-- 5. 启用新的 claude-opus-4-6 -> responses:gpt-5.4 映射
-- ============================================================

-- 1. 确保 alias 模型存在，且对外协议为 Anthropic
INSERT INTO `unified_model` (
    `model_name`,
    `display_name`,
    `model_type`,
    `protocol_type`,
    `max_tokens`,
    `input_price_per_million`,
    `output_price_per_million`,
    `enabled`,
    `description`
) VALUES (
    'claude-opus-4-6',
    'Claude Opus 4.6',
    'chat',
    'anthropic',
    32768,
    5.000000,
    20.000000,
    1,
    'Claude Opus 4.6 alias exposed via Anthropic and routed to GPT-5.4 high reasoning on Codex Responses'
)
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `protocol_type` = VALUES(`protocol_type`),
    `max_tokens` = VALUES(`max_tokens`),
    `input_price_per_million` = VALUES(`input_price_per_million`),
    `output_price_per_million` = VALUES(`output_price_per_million`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

-- 2. 确保新渠道存在，并复制旧 codex 渠道的上游连接信息
INSERT INTO `channel` (
    `name`,
    `base_url`,
    `api_key`,
    `protocol_type`,
    `priority`,
    `enabled`,
    `description`
)
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

-- 3. 关闭旧渠道上的 claude-opus-4-6 映射
UPDATE `model_channel_mapping` mc
JOIN `unified_model` um ON um.`id` = mc.`unified_model_id`
JOIN `channel` c ON c.`id` = mc.`channel_id`
SET mc.`enabled` = 0
WHERE um.`model_name` = 'claude-opus-4-6'
  AND c.`name` = '43.156.153.12-codex';

-- 4. 启用新渠道映射
INSERT INTO `model_channel_mapping` (
    `unified_model_id`,
    `channel_id`,
    `actual_model_name`,
    `enabled`
)
SELECT
    um.`id`,
    c.`id`,
    'responses:gpt-5.4',
    1
FROM `unified_model` um
JOIN `channel` c ON c.`name` = '43.156.153.12-codex转claude'
WHERE um.`model_name` = 'claude-opus-4-6'
ON DUPLICATE KEY UPDATE
    `actual_model_name` = VALUES(`actual_model_name`),
    `enabled` = VALUES(`enabled`);

-- 5. 核对结果
SELECT
    c.`name` AS `channel_name`,
    c.`protocol_type`,
    um.`model_name`,
    mc.`actual_model_name`,
    mc.`enabled`
FROM `model_channel_mapping` mc
JOIN `unified_model` um ON um.`id` = mc.`unified_model_id`
JOIN `channel` c ON c.`id` = mc.`channel_id`
WHERE um.`model_name` = 'claude-opus-4-6'
ORDER BY c.`name`;
