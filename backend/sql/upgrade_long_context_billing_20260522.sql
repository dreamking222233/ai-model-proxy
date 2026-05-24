DROP PROCEDURE IF EXISTS `upgrade_long_context_billing_20260522`;

DELIMITER $$

CREATE PROCEDURE `upgrade_long_context_billing_20260522`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'context_tokens_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `context_tokens_snapshot` INT DEFAULT 0 COMMENT '计费上下文Token快照' AFTER `fast_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'context_token_threshold_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `context_token_threshold_snapshot` INT DEFAULT 262144 COMMENT '长上下文计费阈值快照' AFTER `context_tokens_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'context_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `context_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '长上下文价格倍率快照' AFTER `context_token_threshold_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'context_tokens_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `context_tokens_snapshot` INT DEFAULT 0 COMMENT '计费上下文Token快照' AFTER `fast_price_multiplier_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'context_token_threshold_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `context_token_threshold_snapshot` INT DEFAULT 262144 COMMENT '长上下文计费阈值快照' AFTER `context_tokens_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'context_price_multiplier_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `context_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '长上下文价格倍率快照' AFTER `context_token_threshold_snapshot`;
    END IF;
END$$

DELIMITER ;

CALL `upgrade_long_context_billing_20260522`();
DROP PROCEDURE IF EXISTS `upgrade_long_context_billing_20260522`;
