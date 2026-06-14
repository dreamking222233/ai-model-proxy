-- 优化用户自带 cache_control 的覆盖策略：连续低命中快速接管，连续稳定高命中才恢复用户策略

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
('anthropic_prompt_cache_override_quick_fail_consecutive', '2', 'number', '连续低命中多少次后立即覆盖用户 cache_control'),
('anthropic_prompt_cache_override_recovery_hit_ratio', '0.50', 'number', '连续恢复命中率达到该值后才停止覆盖用户 cache_control')
ON DUPLICATE KEY UPDATE
  `config_value` = VALUES(`config_value`),
  `description` = VALUES(`description`),
  `config_type` = VALUES(`config_type`);
