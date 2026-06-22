-- 代理站套餐在线充值开关

DROP PROCEDURE IF EXISTS `upgrade_agent_subscription_online_recharge_20260622`;

DELIMITER $$

CREATE PROCEDURE `upgrade_agent_subscription_online_recharge_20260622`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'agent'
              AND column_name = 'subscription_online_recharge_enabled'
        ) THEN
            ALTER TABLE `agent`
                ADD COLUMN `subscription_online_recharge_enabled` SMALLINT NOT NULL DEFAULT 1
                COMMENT '代理站套餐在线充值开关 1=开启 0=关闭'
                AFTER `online_recharge_enabled`;
        END IF;
    END IF;
END $$

DELIMITER ;

CALL `upgrade_agent_subscription_online_recharge_20260622`();
DROP PROCEDURE IF EXISTS `upgrade_agent_subscription_online_recharge_20260622`;
