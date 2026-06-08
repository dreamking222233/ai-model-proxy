DROP PROCEDURE IF EXISTS `upgrade_user_asset_source_records_20260608`;

DELIMITER $$

CREATE PROCEDURE `upgrade_user_asset_source_records_20260608`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'operator_id'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `operator_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '人工操作用户ID' AFTER `service_tier`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'remark'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD COLUMN `remark` VARCHAR(255) DEFAULT NULL COMMENT '用户可见备注' AFTER `operator_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND index_name = 'idx_consumption_operator_id'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD KEY `idx_consumption_operator_id` (`operator_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND index_name = 'idx_consumption_user_created_id'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD KEY `idx_consumption_user_created_id` (`user_id`, `created_at`, `id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'request_id'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD KEY `idx_consumption_request_id` (`request_id`);
    END IF;
END$$

DELIMITER ;

CALL `upgrade_user_asset_source_records_20260608`();
DROP PROCEDURE IF EXISTS `upgrade_user_asset_source_records_20260608`;
