-- 在线充值入账幂等保护
-- 用途：为支付成功后的用户资产入账增加数据库唯一键兜底，防止同一订单重复到账。

CREATE TABLE IF NOT EXISTS `payment_recharge_settlement` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `order_id` BIGINT UNSIGNED NOT NULL,
    `order_no` VARCHAR(64) NOT NULL,
    `asset_type` VARCHAR(32) NOT NULL DEFAULT 'balance' COMMENT '入账资产: balance/image_credit',
    `user_id` BIGINT UNSIGNED NOT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `amount_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '用户支付人民币金额',
    `credited_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '到账美元余额',
    `credited_image_credits` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '到账图片积分',
    `status` VARCHAR(16) NOT NULL DEFAULT 'settling' COMMENT 'settling/applied',
    `applied_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_payment_recharge_settlement_order_asset` (`order_no`, `asset_type`),
    KEY `idx_payment_recharge_settlement_order_id` (`order_id`),
    KEY `idx_payment_recharge_settlement_user_id` (`user_id`),
    KEY `idx_payment_recharge_settlement_agent_id` (`agent_id`),
    KEY `idx_payment_recharge_settlement_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='在线充值入账幂等表';

-- 发布前检查：正常应返回空结果；如有数据，说明半执行/手工建表中已存在重复幂等记录，
-- 需要人工清理后再添加唯一键。
SELECT
    `order_no`,
    `asset_type`,
    COUNT(*) AS `duplicate_count`
FROM `payment_recharge_settlement`
GROUP BY `order_no`, `asset_type`
HAVING COUNT(*) > 1;

SET @settlement_unique_exists := (
    SELECT COUNT(1)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'payment_recharge_settlement'
      AND index_name = 'uk_payment_recharge_settlement_order_asset'
);

SET @settlement_unique_sql := IF(
    @settlement_unique_exists = 0,
    'ALTER TABLE `payment_recharge_settlement` ADD UNIQUE KEY `uk_payment_recharge_settlement_order_asset` (`order_no`, `asset_type`)',
    'SELECT ''uk_payment_recharge_settlement_order_asset exists'''
);
PREPARE settlement_unique_stmt FROM @settlement_unique_sql;
EXECUTE settlement_unique_stmt;
DEALLOCATE PREPARE settlement_unique_stmt;

INSERT IGNORE INTO `payment_recharge_settlement` (
    `order_id`,
    `order_no`,
    `asset_type`,
    `user_id`,
    `agent_id`,
    `amount_cny`,
    `credited_usd`,
    `credited_image_credits`,
    `status`,
    `applied_at`,
    `created_at`,
    `updated_at`
)
SELECT
    `id`,
    `order_no`,
    CASE WHEN `recharge_type` = 'image_credit' THEN 'image_credit' ELSE 'balance' END,
    `user_id`,
    `agent_id`,
    `amount_cny`,
    `credited_usd`,
    `credited_image_credits`,
    'applied',
    `paid_at`,
    COALESCE(`paid_at`, `created_at`, NOW()),
    NOW()
FROM `payment_recharge_order`
WHERE `status` = 'paid';
