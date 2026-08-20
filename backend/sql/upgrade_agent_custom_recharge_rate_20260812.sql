-- Add per-agent user recharge pricing and an order-level user-rate snapshot.

DROP PROCEDURE IF EXISTS `upgrade_agent_custom_recharge_rate_20260812`;

DELIMITER $$

CREATE PROCEDURE `upgrade_agent_custom_recharge_rate_20260812`()
BEGIN
    DECLARE invalid_agent_count BIGINT DEFAULT 0;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'agent'
              AND column_name = 'custom_recharge_rate_enabled'
        ) THEN
            ALTER TABLE `agent`
                ADD COLUMN `custom_recharge_rate_enabled` SMALLINT NOT NULL DEFAULT 0
                COMMENT '1=agent may set its user recharge rate, 0=use platform user rate'
                AFTER `subscription_online_recharge_enabled`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'agent'
              AND column_name = 'custom_recharge_rate'
        ) THEN
            ALTER TABLE `agent`
                ADD COLUMN `custom_recharge_rate` DECIMAL(12,6) NOT NULL DEFAULT 5
                COMMENT 'User assets credited per CNY for both balance and image credits'
                AFTER `custom_recharge_rate_enabled`;
        END IF;

    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'payment_recharge_order'
              AND column_name = 'user_recharge_rate'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `user_recharge_rate` DECIMAL(12,6) NOT NULL DEFAULT 0
                COMMENT 'Effective user recharge rate captured when the order is created'
                AFTER `credited_image_credits`;
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent'
    ) THEN
        SELECT COUNT(*) INTO invalid_agent_count
        FROM `agent`
        WHERE `custom_recharge_rate_enabled` = 1
          AND (`custom_recharge_rate` < 0.010000 OR `custom_recharge_rate` > @max_custom_recharge_rate);

        IF invalid_agent_count > 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Enabled agent custom recharge rate is outside the allowed range';
        END IF;
    END IF;
END $$

DELIMITER ;

-- The current settlement ceiling is 7. Change this session value before a
-- release check when the backend settlement configuration differs.
SET @max_custom_recharge_rate = 7.000000;
CALL `upgrade_agent_custom_recharge_rate_20260812`();
DROP PROCEDURE IF EXISTS `upgrade_agent_custom_recharge_rate_20260812`;
