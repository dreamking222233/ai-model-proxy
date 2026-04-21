DROP PROCEDURE IF EXISTS `upgrade_subscription_quota_packages_20260421`;

DELIMITER $$

CREATE PROCEDURE `upgrade_subscription_quota_packages_20260421`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'raw_input_tokens'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `raw_input_tokens` INT DEFAULT 0 AFTER `total_tokens`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'raw_output_tokens'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `raw_output_tokens` INT DEFAULT 0 AFTER `raw_input_tokens`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'raw_total_tokens'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `raw_total_tokens` INT DEFAULT 0 AFTER `raw_output_tokens`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'subscription_cycle_id'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `subscription_cycle_id` BIGINT UNSIGNED DEFAULT NULL AFTER `client_ip`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'quota_metric'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd' AFTER `subscription_cycle_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'quota_consumed_amount'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `quota_consumed_amount` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_metric`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'quota_limit_snapshot'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `quota_limit_snapshot` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_consumed_amount`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'quota_used_after'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `quota_used_after` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_limit_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'quota_cycle_date'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `quota_cycle_date` DATE DEFAULT NULL AFTER `quota_used_after`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND index_name = 'idx_request_log_subscription_cycle_id'
    ) THEN
        ALTER TABLE `request_log` ADD INDEX `idx_request_log_subscription_cycle_id` (`subscription_cycle_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'raw_input_tokens'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `raw_input_tokens` INT DEFAULT 0 AFTER `total_tokens`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'raw_output_tokens'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `raw_output_tokens` INT DEFAULT 0 AFTER `raw_input_tokens`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'raw_total_tokens'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `raw_total_tokens` INT DEFAULT 0 AFTER `raw_output_tokens`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'subscription_cycle_id'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `subscription_cycle_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '关联套餐周期ID' AFTER `subscription_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'quota_metric'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd' AFTER `subscription_cycle_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'quota_consumed_amount'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `quota_consumed_amount` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_metric`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'quota_limit_snapshot'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `quota_limit_snapshot` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_consumed_amount`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'quota_used_after'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `quota_used_after` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_limit_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'quota_cycle_date'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `quota_cycle_date` DATE DEFAULT NULL AFTER `quota_used_after`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND index_name = 'idx_subscription_cycle_id'
    ) THEN
        ALTER TABLE `consumption_record` ADD INDEX `idx_subscription_cycle_id` (`subscription_cycle_id`);
    END IF;

    CREATE TABLE IF NOT EXISTS `subscription_plan` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `plan_code` VARCHAR(64) NOT NULL COMMENT '套餐编码',
        `plan_name` VARCHAR(64) NOT NULL COMMENT '套餐名称',
        `plan_kind` VARCHAR(20) NOT NULL DEFAULT 'unlimited' COMMENT 'unlimited/daily_quota',
        `duration_mode` VARCHAR(20) NOT NULL DEFAULT 'custom',
        `duration_days` INT NOT NULL DEFAULT 1,
        `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd',
        `quota_value` DECIMAL(20, 6) DEFAULT 0,
        `reset_period` VARCHAR(20) NOT NULL DEFAULT 'day',
        `reset_timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
        `sort_order` INT NOT NULL DEFAULT 0,
        `status` VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active/inactive',
        `description` VARCHAR(255) DEFAULT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uk_subscription_plan_code` (`plan_code`),
        KEY `idx_subscription_plan_status` (`status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐模板表';

    CREATE TABLE IF NOT EXISTS `subscription_usage_cycle` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `subscription_id` BIGINT UNSIGNED NOT NULL,
        `user_id` BIGINT UNSIGNED NOT NULL,
        `cycle_date` DATE NOT NULL COMMENT '业务日期',
        `cycle_start_at` DATETIME NOT NULL,
        `cycle_end_at` DATETIME NOT NULL,
        `quota_metric` VARCHAR(20) NOT NULL COMMENT 'total_tokens/cost_usd',
        `quota_limit` DECIMAL(20, 6) NOT NULL DEFAULT 0,
        `used_amount` DECIMAL(20, 6) NOT NULL DEFAULT 0,
        `request_count` INT NOT NULL DEFAULT 0,
        `last_request_id` VARCHAR(36) DEFAULT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uk_subscription_cycle_date` (`subscription_id`, `cycle_date`),
        KEY `idx_subscription_usage_user_id` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐每日额度周期表';

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'plan_type'
          AND column_type <> 'varchar(20)'
    ) THEN
        ALTER TABLE `user_subscription` MODIFY COLUMN `plan_type` VARCHAR(20) NOT NULL COMMENT '套餐类型';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'plan_id'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `plan_id` BIGINT UNSIGNED DEFAULT NULL AFTER `user_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'plan_code_snapshot'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `plan_code_snapshot` VARCHAR(64) DEFAULT NULL COMMENT '套餐编码快照' AFTER `plan_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'plan_kind_snapshot'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `plan_kind_snapshot` VARCHAR(20) DEFAULT NULL COMMENT 'unlimited/daily_quota' AFTER `plan_type`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'duration_days_snapshot'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `duration_days_snapshot` INT DEFAULT 0 AFTER `plan_kind_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'quota_metric'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd' AFTER `duration_days_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'quota_value'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `quota_value` DECIMAL(20, 6) DEFAULT 0 AFTER `quota_metric`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'reset_period'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `reset_period` VARCHAR(20) DEFAULT 'day' AFTER `quota_value`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'reset_timezone'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `reset_timezone` VARCHAR(64) DEFAULT 'Asia/Shanghai' AFTER `reset_period`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'activation_mode'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `activation_mode` VARCHAR(20) DEFAULT 'append' AFTER `reset_timezone`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'activated_at'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `activated_at` DATETIME DEFAULT NULL AFTER `created_by`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND index_name = 'idx_user_subscription_plan_id'
    ) THEN
        ALTER TABLE `user_subscription` ADD INDEX `idx_user_subscription_plan_id` (`plan_id`);
    END IF;

    INSERT INTO `subscription_plan`
        (`plan_code`, `plan_name`, `plan_kind`, `duration_mode`, `duration_days`, `quota_metric`, `quota_value`, `reset_period`, `reset_timezone`, `sort_order`, `status`, `description`)
    VALUES
        ('daily-unlimited', '日度无限包', 'unlimited', 'day', 1, NULL, 0, 'day', 'Asia/Shanghai', 10, 'active', '1 天无限额度套餐'),
        ('weekly-unlimited', '周度无限包', 'unlimited', 'custom', 7, NULL, 0, 'day', 'Asia/Shanghai', 20, 'active', '7 天无限额度套餐'),
        ('monthly-unlimited', '月度无限包', 'unlimited', 'month', 30, NULL, 0, 'day', 'Asia/Shanghai', 30, 'active', '30 天无限额度套餐'),
        ('daily-10m-token', '日度畅享包', 'daily_quota', 'day', 1, 'total_tokens', 10000000, 'day', 'Asia/Shanghai', 40, 'active', '1 天有效，每天 1000 万 Token'),
        ('weekly-10m-token', '周度畅享包', 'daily_quota', 'custom', 7, 'total_tokens', 10000000, 'day', 'Asia/Shanghai', 50, 'active', '7 天有效，每天 1000 万 Token'),
        ('monthly-10m-token', '月度畅享包', 'daily_quota', 'month', 30, 'total_tokens', 10000000, 'day', 'Asia/Shanghai', 60, 'active', '30 天有效，每天 1000 万 Token')
    ON DUPLICATE KEY UPDATE
        `plan_name` = VALUES(`plan_name`),
        `plan_kind` = VALUES(`plan_kind`),
        `duration_mode` = VALUES(`duration_mode`),
        `duration_days` = VALUES(`duration_days`),
        `quota_metric` = VALUES(`quota_metric`),
        `quota_value` = VALUES(`quota_value`),
        `reset_period` = VALUES(`reset_period`),
        `reset_timezone` = VALUES(`reset_timezone`),
        `sort_order` = VALUES(`sort_order`),
        `status` = VALUES(`status`),
        `description` = VALUES(`description`);
END $$

DELIMITER ;

CALL `upgrade_subscription_quota_packages_20260421`();

DROP PROCEDURE IF EXISTS `upgrade_subscription_quota_packages_20260421`;
