-- 直营联系方式展示门槛配置
-- 用途：新增/修正平台直营 QQ/微信展示门槛，用户在线充值余额或购买套餐累计成功付款人民币金额需大于该值。

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
VALUES (
  'platform_support_contact_threshold_cny',
  '100',
  'number',
  '平台直营联系方式展示门槛，累计成功付款人民币金额需大于该值'
)
ON DUPLICATE KEY UPDATE
  `config_type` = VALUES(`config_type`),
  `description` = VALUES(`description`);
