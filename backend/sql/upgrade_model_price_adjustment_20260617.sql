DROP PROCEDURE IF EXISTS `upgrade_model_price_adjustment_20260617`;

DELIMITER $$
CREATE PROCEDURE `upgrade_model_price_adjustment_20260617`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'model_series'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `model_series` VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT '模型系列:gpt/claude/grok/gemini/other' AFTER `model_type`;
    END IF;

    UPDATE `unified_model`
    SET `model_series` = CASE
        WHEN LOWER(`model_name`) LIKE 'gpt%' OR LOWER(`model_name`) LIKE 'o1%' OR LOWER(`model_name`) LIKE 'o3%' OR LOWER(`model_name`) LIKE 'o4%' THEN 'gpt'
        WHEN LOWER(`model_name`) LIKE 'claude%' THEN 'claude'
        WHEN LOWER(`model_name`) LIKE 'grok%' THEN 'grok'
        WHEN LOWER(`model_name`) LIKE 'gemini%' THEN 'gemini'
        ELSE COALESCE(NULLIF(`model_series`, ''), 'other')
    END
    WHERE `model_series` IS NULL OR `model_series` = '' OR `model_series` = 'other';

    CREATE TABLE IF NOT EXISTS `model_price_adjustment_rule` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `name` VARCHAR(128) NOT NULL,
        `model_series` VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'gpt/claude/grok/gemini/other/all',
        `model_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'chat/image/video/embedding/completion/all',
        `billing_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'token/request/image_credit/free/all',
        `multiplier` DECIMAL(12, 6) NOT NULL DEFAULT 1 COMMENT '价格调控倍率',
        `schedule_type` VARCHAR(20) NOT NULL DEFAULT 'always' COMMENT 'always/daily_time',
        `start_time` TIME DEFAULT NULL COMMENT '每日开始时间，北京时间',
        `end_time` TIME DEFAULT NULL COMMENT '每日结束时间，北京时间',
        `priority` INT NOT NULL DEFAULT 100 COMMENT '优先级，数字小优先',
        `enabled` TINYINT NOT NULL DEFAULT 1,
        `description` TEXT DEFAULT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_price_adjustment_match` (`enabled`, `model_series`, `model_type`, `billing_type`, `priority`),
        KEY `idx_price_adjustment_schedule` (`schedule_type`, `start_time`, `end_time`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型分类价格调控规则表';
END$$
DELIMITER ;

CALL `upgrade_model_price_adjustment_20260617`();
DROP PROCEDURE IF EXISTS `upgrade_model_price_adjustment_20260617`;
