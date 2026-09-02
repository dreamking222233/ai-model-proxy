-- 为每个统一模型配置长上下文双倍计费的 Token 阈值。
-- 默认值精确保留升级前的 262144 判断边界。

DROP PROCEDURE IF EXISTS `upgrade_model_long_context_token_threshold_20260902`;

DELIMITER $$

CREATE PROCEDURE `upgrade_model_long_context_token_threshold_20260902`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'unified_model'
          AND column_name = 'long_context_token_threshold'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `long_context_token_threshold` INT NOT NULL DEFAULT 262144
            COMMENT '长上下文双倍计费Token阈值'
            AFTER `long_context_billing_enabled`;
    END IF;
END$$

DELIMITER ;

CALL `upgrade_model_long_context_token_threshold_20260902`();
DROP PROCEDURE IF EXISTS `upgrade_model_long_context_token_threshold_20260902`;
