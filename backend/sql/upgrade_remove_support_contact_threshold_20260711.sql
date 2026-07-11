-- 移除已废弃的平台直营联系方式展示门槛配置。
DELETE FROM `system_config`
WHERE `config_key` = 'platform_support_contact_threshold_cny';
