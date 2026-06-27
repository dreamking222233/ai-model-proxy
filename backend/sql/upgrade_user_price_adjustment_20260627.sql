DROP PROCEDURE IF EXISTS `upgrade_user_price_adjustment_20260627`;

DELIMITER $$
CREATE PROCEDURE `upgrade_user_price_adjustment_20260627`()
BEGIN
    CREATE TABLE IF NOT EXISTS `user_price_adjustment_rule` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `name` VARCHAR(128) NOT NULL COMMENT '规则名称',
        `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
        `model_series` VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'gpt/claude/grok/gemini/other/all',
        `model_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'chat/image/video/embedding/completion/all',
        `billing_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'token/request/image_credit/free/all',
        `multiplier` DECIMAL(12, 6) NOT NULL DEFAULT 1 COMMENT '用户专属价格倍率',
        `schedule_type` VARCHAR(20) NOT NULL DEFAULT 'always' COMMENT 'always/daily_time',
        `start_time` TIME DEFAULT NULL COMMENT '每日开始时间，北京时间',
        `end_time` TIME DEFAULT NULL COMMENT '每日结束时间，北京时间',
        `priority` INT NOT NULL DEFAULT 100 COMMENT '优先级，数字小优先',
        `enabled` TINYINT NOT NULL DEFAULT 1,
        `description` TEXT DEFAULT NULL,
        `created_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '创建管理员ID',
        `updated_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '最后更新管理员ID',
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_user_price_adjustment_user` (`user_id`, `enabled`),
        KEY `idx_user_price_adjustment_match` (`user_id`, `enabled`, `model_series`, `model_type`, `billing_type`, `priority`),
        KEY `idx_user_price_adjustment_schedule` (`schedule_type`, `start_time`, `end_time`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户专属模型价格调控规则表';

    CREATE TABLE IF NOT EXISTS `video_task_billing_snapshot` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `video_id` VARCHAR(128) NOT NULL COMMENT '上游视频任务ID',
        `request_id` VARCHAR(36) DEFAULT NULL COMMENT '创建请求ID',
        `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
        `channel_id` BIGINT UNSIGNED NOT NULL COMMENT '渠道ID',
        `requested_model` VARCHAR(128) DEFAULT NULL,
        `actual_model` VARCHAR(128) DEFAULT NULL,
        `billing_type` VARCHAR(20) DEFAULT 'image_credit',
        `charged_credits` DECIMAL(12, 3) DEFAULT 0,
        `model_multiplier` DECIMAL(12, 3) DEFAULT 1,
        `video_size` VARCHAR(16) DEFAULT NULL,
        `video_seconds` INT DEFAULT 0,
        `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
        `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL,
        `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL,
        `billed` TINYINT NOT NULL DEFAULT 0,
        `billed_at` DATETIME DEFAULT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uk_video_task_billing_video_id` (`video_id`),
        KEY `idx_video_task_user` (`user_id`, `created_at`),
        KEY `idx_video_task_billed` (`billed`, `created_at`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异步视频任务计费快照表';

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'global_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `global_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '系统全局价格倍率快照' AFTER `request_price_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'adjustment_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '分类/用户价格调控倍率快照' AFTER `global_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'price_adjustment_source_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL COMMENT '倍率来源:user/global/default' AFTER `adjustment_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'price_adjustment_rule_id_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL COMMENT '命中倍率规则ID快照' AFTER `price_adjustment_source_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'global_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `global_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '系统全局价格倍率快照' AFTER `request_price_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'adjustment_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '分类/用户价格调控倍率快照' AFTER `global_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'price_adjustment_source_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL COMMENT '倍率来源:user/global/default' AFTER `adjustment_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'price_adjustment_rule_id_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL COMMENT '命中倍率规则ID快照' AFTER `price_adjustment_source_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'image_credit_record' AND column_name = 'adjustment_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `image_credit_record`
            ADD COLUMN `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '分类/用户价格调控倍率快照' AFTER `multiplier`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'image_credit_record' AND column_name = 'price_adjustment_source_snapshot'
    ) THEN
        ALTER TABLE `image_credit_record`
            ADD COLUMN `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL COMMENT '倍率来源:user/global/default' AFTER `adjustment_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'image_credit_record' AND column_name = 'price_adjustment_rule_id_snapshot'
    ) THEN
        ALTER TABLE `image_credit_record`
            ADD COLUMN `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL COMMENT '命中倍率规则ID快照' AFTER `price_adjustment_source_snapshot`;
    END IF;
END$$
DELIMITER ;

CALL `upgrade_user_price_adjustment_20260627`();
DROP PROCEDURE IF EXISTS `upgrade_user_price_adjustment_20260627`;
