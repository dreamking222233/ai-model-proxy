DROP PROCEDURE IF EXISTS `upgrade_model_long_context_billing_enabled_20260617`;

DELIMITER $$

CREATE PROCEDURE `upgrade_model_long_context_billing_enabled_20260617`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'long_context_billing_enabled'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `long_context_billing_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '是否启用超过256k上下文2倍计费' AFTER `image_credit_multiplier`;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'model_series'
    ) THEN
        UPDATE `unified_model`
        SET `long_context_billing_enabled` = 1
        WHERE `model_series` = 'gpt'
          AND `model_type` IN ('chat', 'completion', 'embedding')
          AND `billing_type` IN ('token', 'request');
    ELSE
        UPDATE `unified_model`
        SET `long_context_billing_enabled` = 1
        WHERE (
            `model_name` LIKE 'gpt%'
            OR `model_name` LIKE 'o1%'
            OR `model_name` LIKE 'o3%'
            OR `model_name` LIKE 'o4%'
        )
          AND `model_type` IN ('chat', 'completion', 'embedding')
          AND `billing_type` IN ('token', 'request');
    END IF;
END$$

DELIMITER ;

CALL `upgrade_model_long_context_billing_enabled_20260617`();
DROP PROCEDURE IF EXISTS `upgrade_model_long_context_billing_enabled_20260617`;
