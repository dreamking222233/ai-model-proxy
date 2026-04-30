-- 代理端结算系统升级
-- 用途：新增代理每日授信额度、额度使用量、待结算销售记录和结算批次审计。

DROP PROCEDURE IF EXISTS `upgrade_agent_settlement_system_20260430`;

DELIMITER $$

CREATE PROCEDURE `upgrade_agent_settlement_system_20260430`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_daily_limit'
    ) THEN
        CREATE TABLE `agent_daily_limit` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `resource_type` VARCHAR(32) NOT NULL COMMENT 'balance/image_credit/subscription',
            `plan_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '套餐资源对应 plan_id',
            `plan_id_key` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'NULL plan_id 唯一键占位',
            `daily_limit` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '每日授信额度',
            `status` VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_agent_daily_limit_resource` (`agent_id`, `resource_type`, `plan_id_key`),
            KEY `idx_agent_daily_limit_agent` (`agent_id`),
            KEY `idx_agent_daily_limit_status` (`status`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理每日授信额度配置';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_daily_limit_usage'
    ) THEN
        CREATE TABLE `agent_daily_limit_usage` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `usage_date` DATE NOT NULL COMMENT '北京时间业务日期',
            `resource_type` VARCHAR(32) NOT NULL COMMENT 'balance/image_credit/subscription',
            `plan_id` BIGINT UNSIGNED DEFAULT NULL,
            `plan_id_key` BIGINT UNSIGNED NOT NULL DEFAULT 0,
            `used_amount` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '当日已使用授信额度',
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_agent_daily_usage_resource` (`agent_id`, `usage_date`, `resource_type`, `plan_id_key`),
            KEY `idx_agent_daily_usage_date` (`usage_date`),
            KEY `idx_agent_daily_usage_agent` (`agent_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理每日授信额度使用量';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_settlement_record'
    ) THEN
        CREATE TABLE `agent_settlement_record` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `target_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `business_date` DATE NOT NULL COMMENT '北京时间业务日期',
            `resource_type` VARCHAR(32) NOT NULL COMMENT 'balance/image_credit/subscription/redemption_code',
            `plan_id` BIGINT UNSIGNED DEFAULT NULL,
            `plan_code_snapshot` VARCHAR(64) DEFAULT NULL,
            `plan_name_snapshot` VARCHAR(128) DEFAULT NULL,
            `plan_kind_snapshot` VARCHAR(32) DEFAULT NULL,
            `duration_days_snapshot` INT DEFAULT NULL,
            `quota_metric_snapshot` VARCHAR(32) DEFAULT NULL,
            `quota_value_snapshot` DECIMAL(20, 6) DEFAULT NULL,
            `quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '销售数量/金额',
            `settled_quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '已结算数量/金额',
            `unit_amount` DECIMAL(20, 6) DEFAULT NULL COMMENT '预留结算单价',
            `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/partial/settled/cancelled',
            `source_action` VARCHAR(64) NOT NULL,
            `related_subscription_id` BIGINT UNSIGNED DEFAULT NULL,
            `related_balance_record_id` BIGINT UNSIGNED DEFAULT NULL,
            `related_image_record_id` BIGINT UNSIGNED DEFAULT NULL,
            `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `remark` VARCHAR(255) DEFAULT NULL,
            `settled_at` DATETIME DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_agent_settlement_agent_date` (`agent_id`, `business_date`),
            KEY `idx_agent_settlement_status` (`status`),
            KEY `idx_agent_settlement_resource` (`resource_type`, `plan_id`),
            KEY `idx_agent_settlement_user` (`target_user_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理授信销售待结算记录';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_settlement_batch'
    ) THEN
        CREATE TABLE `agent_settlement_batch` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `agent_id` BIGINT UNSIGNED NOT NULL,
            `resource_type` VARCHAR(32) NOT NULL,
            `plan_id` BIGINT UNSIGNED DEFAULT NULL,
            `business_start_date` DATE DEFAULT NULL,
            `business_end_date` DATE DEFAULT NULL,
            `settled_quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0,
            `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `remark` VARCHAR(255) DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_agent_settlement_batch_agent` (`agent_id`),
            KEY `idx_agent_settlement_batch_resource` (`resource_type`, `plan_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理结算批次';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_settlement_batch_item'
    ) THEN
        CREATE TABLE `agent_settlement_batch_item` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `batch_id` BIGINT UNSIGNED NOT NULL,
            `settlement_record_id` BIGINT UNSIGNED NOT NULL,
            `settled_quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_agent_settlement_batch_item_batch` (`batch_id`),
            KEY `idx_agent_settlement_batch_item_record` (`settlement_record_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理结算批次明细';
    END IF;
END$$

DELIMITER ;

CALL `upgrade_agent_settlement_system_20260430`();
DROP PROCEDURE IF EXISTS `upgrade_agent_settlement_system_20260430`;
