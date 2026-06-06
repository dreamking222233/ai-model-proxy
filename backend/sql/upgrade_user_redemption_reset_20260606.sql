-- 用户兑换码资格重置能力
-- 为 sys_user 增加 redemption_reset_count，用于允许管理员重置后再次兑换新码。

SET @exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'redemption_reset_count'
);

SET @sql := IF(
    @exists = 0,
    "ALTER TABLE `sys_user` ADD COLUMN `redemption_reset_count` BIGINT NOT NULL DEFAULT 0 COMMENT '兑换码资格重置次数'",
    "SELECT 1"
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
