-- Widen the lifetime API key cost counter so accounting cannot roll back at 10,000 USD.

SET SESSION lock_wait_timeout = 15;

DROP PROCEDURE IF EXISTS `upgrade_user_api_key_total_cost_20260814`;

DELIMITER $$

CREATE PROCEDURE `upgrade_user_api_key_total_cost_20260814`()
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'user_api_key'
          AND column_name = 'total_cost'
          AND (
              data_type <> 'decimal'
              OR numeric_precision IS NULL
              OR numeric_precision < 20
              OR numeric_scale <> 6
          )
    ) THEN
        ALTER TABLE `user_api_key`
            MODIFY COLUMN `total_cost` DECIMAL(20,6) NOT NULL DEFAULT 0
            COMMENT 'Total cost accumulated by API key (USD)';
    END IF;
END $$

DELIMITER ;

CALL `upgrade_user_api_key_total_cost_20260814`();
DROP PROCEDURE IF EXISTS `upgrade_user_api_key_total_cost_20260814`;
