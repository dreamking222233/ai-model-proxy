DROP PROCEDURE IF EXISTS `upgrade_cache_creation_billing_20260625`;

DELIMITER $$
CREATE PROCEDURE `upgrade_cache_creation_billing_20260625`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'unified_model' AND column_name = 'cache_creation_price_per_million'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `cache_creation_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万缓存创建Token单价(美元)' AFTER `output_price_per_million`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'cache_creation_cost'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `cache_creation_cost` DECIMAL(12, 6) DEFAULT 0 COMMENT '缓存创建费用' AFTER `cache_read_cost`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'cache_creation_price_per_million_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `cache_creation_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '缓存创建每百万Token单价快照' AFTER `output_price_per_million_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'request_price_snapshot'
    ) THEN
        ALTER TABLE `request_log`
            ADD COLUMN `request_price_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '按请求计费单次价格快照' AFTER `cache_creation_price_per_million_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'cache_creation_cost'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `cache_creation_cost` DECIMAL(12, 6) DEFAULT 0 COMMENT '缓存创建费用' AFTER `cache_read_cost`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'cache_creation_price_per_million_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `cache_creation_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '缓存创建每百万Token单价快照' AFTER `output_price_per_million_snapshot`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.COLUMNS
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'request_price_snapshot'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `request_price_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '按请求计费单次价格快照' AFTER `cache_creation_price_per_million_snapshot`;
    END IF;
END$$
DELIMITER ;

CALL `upgrade_cache_creation_billing_20260625`();
DROP PROCEDURE IF EXISTS `upgrade_cache_creation_billing_20260625`;
