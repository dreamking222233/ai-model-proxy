ALTER TABLE `consumption_record`
    ADD COLUMN `billing_mode` VARCHAR(20) DEFAULT NULL COMMENT 'balance=按量计费, subscription=套餐计费' AFTER `balance_after`,
    ADD COLUMN `subscription_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '关联套餐ID' AFTER `billing_mode`,
    ADD KEY `idx_billing_mode` (`billing_mode`),
    ADD KEY `idx_subscription_id` (`subscription_id`);
