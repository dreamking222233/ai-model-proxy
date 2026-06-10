-- Anthropic Prompt Cache 用户 cache_control 处理策略
-- preserve: 保留用户断点，等同旧逻辑
-- augment: 保留用户断点，并补充稳定的系统断点
-- normalize: 移除用户断点，改由系统重新注入稳定断点

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
VALUES (
  'anthropic_prompt_cache_control_policy',
  'augment',
  'string',
  '用户自带 cache_control 处理策略：preserve/augment/normalize'
)
ON DUPLICATE KEY UPDATE
  `config_type` = VALUES(`config_type`),
  `description` = VALUES(`description`);
