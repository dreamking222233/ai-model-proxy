-- 安全-模型监控开关：按统一模型控制是否启用安全风控

DROP PROCEDURE IF EXISTS `upgrade_model_security_monitor_enabled_20260627`;

DELIMITER $$

CREATE PROCEDURE `upgrade_model_security_monitor_enabled_20260627`()
BEGIN
    DECLARE column_added TINYINT DEFAULT 0;
    DECLARE has_model_series TINYINT DEFAULT 0;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'unified_model'
          AND column_name = 'model_series'
    ) THEN
        SET has_model_series = 1;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'unified_model'
          AND column_name = 'security_monitor_enabled'
    ) THEN
        ALTER TABLE `unified_model`
            ADD COLUMN `security_monitor_enabled` TINYINT NOT NULL DEFAULT 0
            COMMENT '是否启用安全风控监控';
        SET column_added = 1;
    END IF;

    IF column_added = 1 AND has_model_series = 1 THEN
        UPDATE `unified_model`
        SET `security_monitor_enabled` = CASE
            WHEN `model_series` IN ('gpt', 'claude')
              OR LOWER(`model_name`) LIKE 'gpt%'
              OR LOWER(`model_name`) LIKE 'o1%'
              OR LOWER(`model_name`) LIKE 'o3%'
              OR LOWER(`model_name`) LIKE 'o4%'
              OR LOWER(`model_name`) LIKE 'claude%' THEN 1
            ELSE 0
        END;
    ELSEIF column_added = 1 THEN
        UPDATE `unified_model`
        SET `security_monitor_enabled` = CASE
            WHEN LOWER(`model_name`) LIKE 'gpt%'
              OR LOWER(`model_name`) LIKE 'o1%'
              OR LOWER(`model_name`) LIKE 'o3%'
              OR LOWER(`model_name`) LIKE 'o4%'
              OR LOWER(`model_name`) LIKE 'claude%' THEN 1
            ELSE 0
        END;
    END IF;
END$$

DELIMITER ;

CALL `upgrade_model_security_monitor_enabled_20260627`();
DROP PROCEDURE IF EXISTS `upgrade_model_security_monitor_enabled_20260627`;
