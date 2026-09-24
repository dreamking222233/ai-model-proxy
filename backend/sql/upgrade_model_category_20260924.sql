-- Add administrator-managed model categories without changing the fixed model-series contract.
DROP PROCEDURE IF EXISTS `upgrade_model_category_20260924`;

DELIMITER $$
CREATE PROCEDURE `upgrade_model_category_20260924`()
BEGIN
    CREATE TABLE IF NOT EXISTS `model_category` (
        `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        `code` VARCHAR(64) NOT NULL,
        `name` VARCHAR(128) NOT NULL,
        `model_series` VARCHAR(32) NOT NULL,
        `sort_order` INT NOT NULL DEFAULT 100,
        `enabled` TINYINT NOT NULL DEFAULT 1,
        `description` TEXT DEFAULT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uk_model_category_code` (`code`),
        KEY `idx_model_category_series` (`model_series`, `enabled`, `sort_order`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员自定义模型类别';

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'model_category'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `model_category` VARCHAR(64) DEFAULT NULL COMMENT '管理员自定义模型类别' AFTER `model_series`,
            ADD KEY `idx_model_category` (`model_category`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'model_price_adjustment_rule' AND column_name = 'model_category'
    ) THEN
        ALTER TABLE `model_price_adjustment_rule`
            ADD COLUMN `model_category` VARCHAR(64) NOT NULL DEFAULT 'all' COMMENT '模型类别编码或 all' AFTER `model_series`,
            ADD KEY `idx_price_adjustment_category_match` (`enabled`, `model_category`, `model_type`, `billing_type`, `priority`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_price_adjustment_rule' AND column_name = 'model_category'
    ) THEN
        ALTER TABLE `user_price_adjustment_rule`
            ADD COLUMN `model_category` VARCHAR(64) NOT NULL DEFAULT 'all' COMMENT '模型类别编码或 all' AFTER `model_series`,
            ADD KEY `idx_user_price_adjustment_category_match` (`user_id`, `enabled`, `model_category`, `model_type`, `billing_type`, `priority`);
    END IF;

    INSERT INTO `model_category` (`code`, `name`, `model_series`, `sort_order`, `enabled`)
    SELECT `series`, `label`, `series`, `sort_order`, 1
    FROM (
        SELECT 'gpt' AS series, 'GPT' AS label, 10 AS sort_order
        UNION ALL SELECT 'claude', 'Claude', 20
        UNION ALL SELECT 'grok', 'Grok', 30
        UNION ALL SELECT 'gemini', 'Gemini', 40
        UNION ALL SELECT 'deepseek', 'DeepSeek', 50
        UNION ALL SELECT 'domestic', '国产模型', 60
        UNION ALL SELECT 'other', '其他', 70
    ) AS defaults
    WHERE NOT EXISTS (SELECT 1 FROM `model_category` c WHERE c.`code` = defaults.`series`);

    UPDATE `unified_model`
    SET `model_category` = LOWER(`model_series`)
    WHERE (`model_category` IS NULL OR `model_category` = '')
      AND `model_series` IN ('gpt', 'claude', 'grok', 'gemini', 'deepseek', 'domestic', 'other');
END$$
DELIMITER ;

CALL `upgrade_model_category_20260924`();
DROP PROCEDURE IF EXISTS `upgrade_model_category_20260924`;
