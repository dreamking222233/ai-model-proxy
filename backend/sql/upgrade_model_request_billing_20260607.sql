DROP PROCEDURE IF EXISTS `upgrade_model_request_billing_20260607`;

DELIMITER $$

CREATE PROCEDURE `upgrade_model_request_billing_20260607`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'request_price'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `request_price` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '按请求次数计费的单次请求价格(美元)' AFTER `billing_type`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'request_price_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `request_price_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '按请求计费单次价格快照' AFTER `output_price_per_million_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'request_price_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `request_price_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '按请求计费单次价格快照' AFTER `output_price_per_million_snapshot`;
    END IF;
END$$

DELIMITER ;

CALL `upgrade_model_request_billing_20260607`();
DROP PROCEDURE IF EXISTS `upgrade_model_request_billing_20260607`;
