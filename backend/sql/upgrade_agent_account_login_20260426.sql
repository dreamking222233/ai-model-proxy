-- ============================================================
-- 代理账号创建与专用登录入口兼容升级
-- 目的：
-- 1. 兼容“新增代理时直接创建代理账号”的最新逻辑
-- 2. 回填已有代理主账号的 role / agent_id / source_domain
-- 3. 将历史代理站点统一收口到共享 API 地址模式
-- ============================================================

SET @db_name = DATABASE();

-- 1) 共享 API 模式下，历史代理如果还没有 quickstart_api_base_url，则统一补齐
UPDATE `agent`
SET `quickstart_api_base_url` = 'https://api.xiaoleai.team'
WHERE (`quickstart_api_base_url` IS NULL OR TRIM(`quickstart_api_base_url`) = '');

-- 2) 如果历史数据把平台代理共享 API 域名写到了 agent.api_domain，清空即可
UPDATE `agent`
SET `api_domain` = NULL
WHERE `api_domain` IN (
    'api.xiaoleai.team',
    'api.localhost',
    'api.local',
    'platform-api.localhost',
    'platform-api.local'
);

-- 3) 已绑定 owner_user_id 的历史代理，统一回填代理主账号属性
UPDATE `sys_user` u
JOIN `agent` a ON a.`owner_user_id` = u.`id`
SET
    u.`role` = 'agent',
    u.`agent_id` = a.`id`,
    u.`source_domain` = CASE
        WHEN u.`source_domain` IS NULL OR TRIM(u.`source_domain`) = '' THEN a.`frontend_domain`
        ELSE u.`source_domain`
    END
WHERE a.`owner_user_id` IS NOT NULL;

SELECT
    COUNT(*) AS `agent_count`,
    SUM(CASE WHEN `owner_user_id` IS NOT NULL THEN 1 ELSE 0 END) AS `bound_owner_count`,
    SUM(CASE WHEN `quickstart_api_base_url` = 'https://api.xiaoleai.team' THEN 1 ELSE 0 END) AS `shared_api_base_count`
FROM `agent`;
