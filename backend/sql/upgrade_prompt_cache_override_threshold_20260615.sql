-- 放宽用户自带 cache_control 覆盖阈值，连续低命中请求超过 10k token 即可触发系统缓存断点

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
VALUES ('anthropic_prompt_cache_override_min_logical_tokens', '10000', 'number', '覆盖低效用户 cache_control 的最小逻辑输入 token 阈值')
ON DUPLICATE KEY UPDATE
  `config_value` = VALUES(`config_value`),
  `description` = VALUES(`description`),
  `config_type` = VALUES(`config_type`);
