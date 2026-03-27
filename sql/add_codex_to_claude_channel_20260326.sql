-- ============================================================
-- 新增 43.156.153.12-codex转claude 渠道，并将 claude-opus-4-6 切换到该渠道
-- 用途：
-- 1. 新增一个对外表现为 Anthropic 协议的渠道
-- 2. 该渠道实际仍转发到 43.156.153.12:8317/v1/responses
-- 3. 将 claude-opus-4-6 从 43.156.153.12-codex 切换到新渠道
-- 4. 实际上游模型仍为 gpt-5.4，代码侧固定 reasoning.effort=high
-- ============================================================

-- 1. 确保新渠道存在
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
    'http://43.156.153.12:8317/v1',
    COALESCE(src.`api_key`, 'sk-YOUR-API-KEY-HERE'),
    'anthropic',
    1,
    1,
    'Anthropic 协议入口，内部转发到 Codex Responses / gpt-5.4，供 Claude Code 使用'
FROM (
    SELECT `api_key`
    FROM `channel`
    WHERE `name` = '43.156.153.12-codex'
    LIMIT 1
) src
WHERE NOT EXISTS (
    SELECT 1 FROM `channel` WHERE `name` = '43.156.153.12-codex转claude'
);

UPDATE `channel` bridge
LEFT JOIN `channel` src
    ON src.`name` = '43.156.153.12-codex'
SET
    bridge.`base_url` = 'http://43.156.153.12:8317/v1',
    bridge.`api_key` = COALESCE(src.`api_key`, bridge.`api_key`),
    bridge.`protocol_type` = 'anthropic',
    bridge.`priority` = 1,
    bridge.`enabled` = 1,
    bridge.`description` = 'Anthropic 协议入口，内部转发到 Codex Responses / gpt-5.4，供 Claude Code 使用'
WHERE bridge.`name` = '43.156.153.12-codex转claude';

-- 2. 确保 claude-opus-4-6 对外协议为 Anthropic
UPDATE `unified_model`
SET
    `protocol_type` = 'anthropic',
    `description` = 'Claude Opus 4.6 alias exposed via Anthropic and routed to GPT-5.4 high reasoning on Codex Responses',
    `enabled` = 1
WHERE `model_name` = 'claude-opus-4-6';

-- 3. 关闭旧渠道上的 claude-opus-4-6 映射
UPDATE `model_channel_mapping` mc
JOIN `unified_model` um ON um.`id` = mc.`unified_model_id`
JOIN `channel` c ON c.`id` = mc.`channel_id`
SET mc.`enabled` = 0
WHERE um.`model_name` = 'claude-opus-4-6'
  AND c.`name` = '43.156.153.12-codex';

-- 4. 在新渠道上启用 claude-opus-4-6 -> responses:gpt-5.4
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
