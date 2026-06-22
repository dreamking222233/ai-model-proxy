-- 用户在线购买套餐与代理套餐销售核销
-- 用途：套餐模板增加前台售价配置，支付订单支持 subscription 类型，并记录代理套餐销售返现核销流水。

DROP PROCEDURE IF EXISTS `upgrade_user_subscription_purchase_20260622`;

DELIMITER $$

CREATE PROCEDURE `upgrade_user_subscription_purchase_20260622`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'subscription_plan'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'subscription_plan' AND column_name = 'sale_price_cny'
        ) THEN
            ALTER TABLE `subscription_plan`
                ADD COLUMN `sale_price_cny` DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '用户在线购买售价 RMB' AFTER `reset_timezone`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'subscription_plan' AND column_name = 'agent_cost_price_cny'
        ) THEN
            ALTER TABLE `subscription_plan`
                ADD COLUMN `agent_cost_price_cny` DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '代理拿货价 RMB' AFTER `sale_price_cny`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'subscription_plan' AND column_name = 'online_sale_enabled'
        ) THEN
            ALTER TABLE `subscription_plan`
                ADD COLUMN `online_sale_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '是否允许用户前台在线购买' AFTER `agent_cost_price_cny`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'subscription_plan' AND index_name = 'idx_subscription_plan_online_sale'
        ) THEN
            ALTER TABLE `subscription_plan`
                ADD KEY `idx_subscription_plan_online_sale` (`online_sale_enabled`, `status`);
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'subscription_plan_id'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `subscription_plan_id` BIGINT UNSIGNED DEFAULT NULL AFTER `agent_income_cny`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'subscription_id'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `subscription_id` BIGINT UNSIGNED DEFAULT NULL AFTER `subscription_plan_id`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'plan_code_snapshot'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `plan_code_snapshot` VARCHAR(64) DEFAULT NULL AFTER `subscription_id`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'plan_name_snapshot'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `plan_name_snapshot` VARCHAR(128) DEFAULT NULL AFTER `plan_code_snapshot`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'plan_kind_snapshot'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `plan_kind_snapshot` VARCHAR(32) DEFAULT NULL AFTER `plan_name_snapshot`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'duration_days_snapshot'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `duration_days_snapshot` INT DEFAULT NULL AFTER `plan_kind_snapshot`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'quota_metric_snapshot'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `quota_metric_snapshot` VARCHAR(32) DEFAULT NULL AFTER `duration_days_snapshot`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'quota_value_snapshot'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `quota_value_snapshot` DECIMAL(20,6) DEFAULT NULL AFTER `quota_metric_snapshot`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'subscription_activation_mode'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `subscription_activation_mode` VARCHAR(20) NOT NULL DEFAULT 'append' AFTER `quota_value_snapshot`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'subscription_sale_price_cny'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `subscription_sale_price_cny` DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER `subscription_activation_mode`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'subscription_agent_cost_cny'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `subscription_agent_cost_cny` DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER `subscription_sale_price_cny`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'subscription_agent_rebate_cny'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `subscription_agent_rebate_cny` DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER `subscription_agent_cost_cny`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND index_name = 'idx_payment_recharge_subscription_plan'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD KEY `idx_payment_recharge_subscription_plan` (`subscription_plan_id`);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND index_name = 'idx_payment_recharge_subscription_id'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD KEY `idx_payment_recharge_subscription_id` (`subscription_id`);
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_settlement'
    ) THEN
        CREATE TABLE `payment_recharge_settlement` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `order_id` BIGINT UNSIGNED NOT NULL,
            `order_no` VARCHAR(64) NOT NULL,
            `asset_type` VARCHAR(32) NOT NULL DEFAULT 'balance' COMMENT '入账资产: balance/image_credit/subscription',
            `user_id` BIGINT UNSIGNED NOT NULL,
            `agent_id` BIGINT UNSIGNED DEFAULT NULL,
            `amount_cny` DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '用户支付人民币金额',
            `credited_usd` DECIMAL(12,6) NOT NULL DEFAULT 0 COMMENT '到账美元余额',
            `credited_image_credits` DECIMAL(12,3) NOT NULL DEFAULT 0 COMMENT '到账图片积分',
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
    ELSE
        ALTER TABLE `payment_recharge_settlement`
            MODIFY COLUMN `asset_type` VARCHAR(32) NOT NULL DEFAULT 'balance' COMMENT '入账资产: balance/image_credit/subscription';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_subscription_sale_record'
    ) THEN
        CREATE TABLE `agent_subscription_sale_record` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `order_id` BIGINT UNSIGNED NOT NULL,
            `order_no` VARCHAR(64) NOT NULL,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `user_id` BIGINT UNSIGNED NOT NULL,
            `subscription_id` BIGINT UNSIGNED DEFAULT NULL,
            `plan_id` BIGINT UNSIGNED DEFAULT NULL,
            `plan_code_snapshot` VARCHAR(64) DEFAULT NULL,
            `plan_name_snapshot` VARCHAR(128) NOT NULL,
            `plan_kind_snapshot` VARCHAR(32) DEFAULT NULL,
            `duration_days_snapshot` INT DEFAULT NULL,
            `sale_price_cny` DECIMAL(12,2) NOT NULL DEFAULT 0,
            `agent_cost_price_cny` DECIMAL(12,2) NOT NULL DEFAULT 0,
            `agent_rebate_cny` DECIMAL(12,2) NOT NULL DEFAULT 0,
            `payment_channel` VARCHAR(32) NOT NULL,
            `payment_status` VARCHAR(16) NOT NULL DEFAULT 'paid',
            `rebate_status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/settled/void',
            `settled_at` DATETIME DEFAULT NULL,
            `settled_by` BIGINT UNSIGNED DEFAULT NULL,
            `settlement_remark` VARCHAR(255) DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_agent_subscription_sale_order` (`order_no`),
            KEY `idx_agent_subscription_sale_agent_status` (`agent_id`, `rebate_status`),
            KEY `idx_agent_subscription_sale_created` (`created_at`),
            KEY `idx_agent_subscription_sale_plan` (`plan_id`),
            KEY `idx_agent_subscription_sale_user` (`user_id`),
            KEY `idx_agent_subscription_sale_subscription` (`subscription_id`),
            KEY `idx_agent_subscription_sale_settled_by` (`settled_by`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理套餐销售返现核销记录表';
    END IF;
END$$

DELIMITER ;

CALL `upgrade_user_subscription_purchase_20260622`();
DROP PROCEDURE IF EXISTS `upgrade_user_subscription_purchase_20260622`;
