-- 上游失败重试与错误脱敏配置

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
VALUES ('max_retry_count', '3', 'number', '上游失败重试次数')
ON DUPLICATE KEY UPDATE
  `description` = VALUES(`description`),
  `config_type` = VALUES(`config_type`);
