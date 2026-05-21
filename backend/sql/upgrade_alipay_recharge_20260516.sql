-- 支付宝在线充值升级
-- 用途：新增在线充值订单、代理人民币现金余额、现金流水与提现记录。

DROP PROCEDURE IF EXISTS `upgrade_alipay_recharge_20260516`;

DELIMITER $$

CREATE PROCEDURE `upgrade_alipay_recharge_20260516`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order'
    ) THEN
        CREATE TABLE `payment_recharge_order` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `order_no` VARCHAR(64) NOT NULL,
            `payment_channel` VARCHAR(32) NOT NULL DEFAULT 'alipay',
            `user_id` BIGINT UNSIGNED NOT NULL,
            `agent_id` BIGINT UNSIGNED DEFAULT NULL,
            `site_scope` VARCHAR(16) NOT NULL DEFAULT 'platform',
            `source_host` VARCHAR(255) DEFAULT NULL,
            `return_url_snapshot` VARCHAR(512) DEFAULT NULL,
            `amount_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '用户支付人民币金额',
            `credited_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '用户到账美元余额',
            `agent_settlement_rate` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '代理内部结算比例，单位：1 RMB 对应多少 USD',
            `agent_income_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '代理现金分润人民币',
            `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/closed/failed',
            `subject` VARCHAR(128) NOT NULL,
            `body` TEXT DEFAULT NULL,
            `alipay_trade_no` VARCHAR(64) DEFAULT NULL,
            `wechat_transaction_id` VARCHAR(64) DEFAULT NULL,
            `wechat_code_url` TEXT DEFAULT NULL,
            `trade_status` VARCHAR(32) DEFAULT NULL,
            `buyer_logon_id` VARCHAR(128) DEFAULT NULL,
            `buyer_user_id` VARCHAR(64) DEFAULT NULL,
            `expired_at` DATETIME DEFAULT NULL,
            `closed_at` DATETIME DEFAULT NULL,
            `paid_at` DATETIME DEFAULT NULL,
            `notify_raw` TEXT DEFAULT NULL,
            `return_raw` TEXT DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_payment_recharge_order_no` (`order_no`),
            UNIQUE KEY `uk_payment_recharge_alipay_trade_no` (`alipay_trade_no`),
            UNIQUE KEY `uk_payment_recharge_wechat_transaction_id` (`wechat_transaction_id`),
            KEY `idx_payment_recharge_user_status` (`user_id`, `status`),
            KEY `idx_payment_recharge_agent_status` (`agent_id`, `status`),
            KEY `idx_payment_recharge_created_at` (`created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='在线充值订单表';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_cash_balance'
    ) THEN
        CREATE TABLE `agent_cash_balance` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `balance` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '当前可提现人民币余额',
            `total_income` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '累计分润收入',
            `total_withdrawn` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '累计提现',
            `total_adjusted` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '累计人工调账',
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_agent_cash_balance_agent_id` (`agent_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理人民币现金余额表';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_cash_ledger'
    ) THEN
        CREATE TABLE `agent_cash_ledger` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `order_id` BIGINT UNSIGNED DEFAULT NULL,
            `withdrawal_id` BIGINT UNSIGNED DEFAULT NULL,
            `action_type` VARCHAR(32) NOT NULL COMMENT 'recharge_commission/withdraw/manual_adjust',
            `change_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '正数=增加，负数=减少',
            `balance_before` DECIMAL(12, 2) NOT NULL DEFAULT 0,
            `balance_after` DECIMAL(12, 2) NOT NULL DEFAULT 0,
            `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `remark` VARCHAR(255) DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_agent_cash_ledger_agent` (`agent_id`),
            KEY `idx_agent_cash_ledger_action` (`action_type`),
            KEY `idx_agent_cash_ledger_order` (`order_id`),
            KEY `idx_agent_cash_ledger_withdrawal` (`withdrawal_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理人民币现金流水表';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_cash_withdrawal'
    ) THEN
        CREATE TABLE `agent_cash_withdrawal` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `amount` DECIMAL(12, 2) NOT NULL DEFAULT 0,
            `status` VARCHAR(16) NOT NULL DEFAULT 'completed' COMMENT 'completed',
            `transfer_method` VARCHAR(32) NOT NULL DEFAULT 'offline_other' COMMENT 'alipay/wechat/bank/offline_other',
            `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `remark` VARCHAR(255) DEFAULT NULL,
            `completed_at` DATETIME DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_agent_cash_withdrawal_agent` (`agent_id`),
            KEY `idx_agent_cash_withdrawal_status` (`status`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理现金提现记录表';
    END IF;
END$$

DELIMITER ;

CALL `upgrade_alipay_recharge_20260516`();
DROP PROCEDURE IF EXISTS `upgrade_alipay_recharge_20260516`;
