-- ============================================================
-- 43.156 Claude 渠道切换到 Anthropic / Claude Messages API
-- 日期: 2026-03-24
-- 目标: 让 43.156.153.12-Claude 通过 http://43.156.153.12:8080/v1/messages
-- ============================================================

UPDATE `channel`
SET
    `base_url` = 'http://43.156.153.12:8080/v1',
    `protocol_type` = 'anthropic',
    `auth_header_type` = 'x-api-key',
    `updated_at` = NOW()
WHERE `id` = 9
   OR `name` = '43.156.153.12-Claude';

-- 验证结果
SELECT
    `id`,
    `name`,
    `base_url`,
    `protocol_type`,
    `auth_header_type`,
    `priority`,
    `enabled`
FROM `channel`
WHERE `id` = 9
   OR `name` = '43.156.153.12-Claude';
