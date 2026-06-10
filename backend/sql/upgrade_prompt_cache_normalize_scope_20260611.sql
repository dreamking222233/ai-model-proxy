-- Add scoped Anthropic prompt-cache normalize controls.
-- Defaults only enable normalize for DDD (user_id=244) for production observation.

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT
  'anthropic_prompt_cache_normalize_user_ids',
  '244',
  'string',
  'Anthropic Prompt Cache 强制清洗用户自带 cache_control 的用户ID列表，逗号/空格/换行分隔'
WHERE NOT EXISTS (
  SELECT 1 FROM `system_config`
  WHERE `config_key` = 'anthropic_prompt_cache_normalize_user_ids'
);

UPDATE `system_config`
SET `config_value` = '244'
WHERE `config_key` = 'anthropic_prompt_cache_normalize_user_ids'
  AND TRIM(COALESCE(`config_value`, '')) = '';

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT
  'anthropic_prompt_cache_normalize_agent_ids',
  '',
  'string',
  'Anthropic Prompt Cache 强制清洗用户自带 cache_control 的代理ID列表，逗号/空格/换行分隔'
WHERE NOT EXISTS (
  SELECT 1 FROM `system_config`
  WHERE `config_key` = 'anthropic_prompt_cache_normalize_agent_ids'
);
