INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
VALUES ('promotion_reward_rate', '0.2', 'number', '推广返利比例，小数形式：0.2=20%，0=关闭')
ON DUPLICATE KEY UPDATE
    `description` = VALUES(`description`);
