-- 微信 Native 在线充值升级
-- 用途：为统一在线充值订单补充微信支付交易号与二维码链接字段。

DROP PROCEDURE IF EXISTS `upgrade_wechat_native_recharge_20260520`;

DELIMITER $$

CREATE PROCEDURE `upgrade_wechat_native_recharge_20260520`()
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'wechat_transaction_id'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `wechat_transaction_id` VARCHAR(64) DEFAULT NULL AFTER `alipay_trade_no`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND column_name = 'wechat_code_url'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD COLUMN `wechat_code_url` TEXT DEFAULT NULL AFTER `wechat_transaction_id`;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'payment_recharge_order' AND index_name = 'uk_payment_recharge_wechat_transaction_id'
        ) THEN
            ALTER TABLE `payment_recharge_order`
                ADD UNIQUE KEY `uk_payment_recharge_wechat_transaction_id` (`wechat_transaction_id`);
        END IF;
    END IF;
END$$

DELIMITER ;

CALL `upgrade_wechat_native_recharge_20260520`();
DROP PROCEDURE IF EXISTS `upgrade_wechat_native_recharge_20260520`;
