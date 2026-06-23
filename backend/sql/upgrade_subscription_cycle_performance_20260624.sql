DROP PROCEDURE IF EXISTS `upgrade_subscription_cycle_performance_20260624`;

DELIMITER $$

CREATE PROCEDURE `upgrade_subscription_cycle_performance_20260624`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'consumption_record'
          AND index_name = 'idx_consumption_subscription_created_id'
    ) THEN
        ALTER TABLE `consumption_record`
            ADD KEY `idx_consumption_subscription_created_id` (`subscription_id`, `created_at`, `id`);
    END IF;
END$$

DELIMITER ;

CALL `upgrade_subscription_cycle_performance_20260624`();
DROP PROCEDURE IF EXISTS `upgrade_subscription_cycle_performance_20260624`;
