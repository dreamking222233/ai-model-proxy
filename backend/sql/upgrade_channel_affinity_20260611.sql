-- Add text channel affinity configs for improving upstream prompt-cache hit rate.

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'channel_affinity_enabled', 'true', 'boolean', '是否启用文本请求渠道亲和，尽量让同一会话复用上次成功渠道'
WHERE NOT EXISTS (
  SELECT 1 FROM `system_config` WHERE `config_key` = 'channel_affinity_enabled'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'channel_affinity_ttl_seconds', '3600', 'number', '文本请求渠道亲和绑定有效期（秒）'
WHERE NOT EXISTS (
  SELECT 1 FROM `system_config` WHERE `config_key` = 'channel_affinity_ttl_seconds'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'channel_affinity_fallback_enabled', 'true', 'boolean', '缺少显式会话ID时是否根据稳定请求前缀生成渠道亲和键'
WHERE NOT EXISTS (
  SELECT 1 FROM `system_config` WHERE `config_key` = 'channel_affinity_fallback_enabled'
);
