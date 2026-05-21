-- 在线充值支持图片积分
-- 用途：在统一支付订单中区分余额充值和图片积分充值，并记录图片积分到账数量。

DROP PROCEDURE IF EXISTS `upgrade_online_recharge_image_credit_20260521`;

DELIMITER $$

CREATE PROCEDURE `upgrade_online_recharge_image_credit_20260521`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'recharge_type'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `recharge_type` VARCHAR(32) NOT NULL DEFAULT 'balance' COMMENT '充值类型: balance/image_credit' AFTER `payment_channel`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'credited_image_credits'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `credited_image_credits` DECIMAL(12,3) NOT NULL DEFAULT 0 COMMENT '到账图片积分' AFTER `credited_usd`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND index_name = 'idx_payment_recharge_type'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD KEY `idx_payment_recharge_type` (`recharge_type`);
        END IF;
    END IF;
END$$

DELIMITER ;

CALL `upgrade_online_recharge_image_credit_20260521`();
DROP PROCEDURE IF EXISTS `upgrade_online_recharge_image_credit_20260521`;
