DROP PROCEDURE IF EXISTS `upgrade_cache_read_billing_20260821`;

DELIMITER $$
CREATE PROCEDURE `upgrade_cache_read_billing_20260821`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'cache_read_price_per_million'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `cache_read_price_per_million` DECIMAL(12, 6) NULL DEFAULT NULL
            COMMENT '每百万缓存读取Token单价(美元)，为空时按输入价格10%'
            AFTER `output_price_per_million`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'cache_read_price_per_million_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `cache_read_price_per_million_snapshot` DECIMAL(12, 6) NULL DEFAULT NULL
            COMMENT '缓存读取每百万Token实际单价快照'
            AFTER `output_price_per_million_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'cache_read_price_per_million_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `cache_read_price_per_million_snapshot` DECIMAL(12, 6) NULL DEFAULT NULL
            COMMENT '缓存读取每百万Token实际单价快照'
            AFTER `output_price_per_million_snapshot`;
    END IF;
END$$
DELIMITER ;

CALL `upgrade_cache_read_billing_20260821`();
DROP PROCEDURE IF EXISTS `upgrade_cache_read_billing_20260821`;
