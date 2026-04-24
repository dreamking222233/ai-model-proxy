-- ============================================================
-- 兼容老库的 sys_user.subscription_type 字段
-- 目的：
-- 1. 兼容旧环境中 subscription_type 为 ENUM('balance','unlimited') 的情况
-- 2. 将字段统一升级为 VARCHAR(16)
-- 3. 允许后续缓存写入 balance / unlimited / quota
-- ============================================================

SET @db_name = DATABASE();

SET @alter_sql = (
    SELECT IF(
        EXISTS (
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = @db_name
              AND TABLE_NAME = 'sys_user'
              AND COLUMN_NAME = 'subscription_type'
              AND (
                  DATA_TYPE <> 'varchar'
                  OR IFNULL(CHARACTER_MAXIMUM_LENGTH, 0) < 16
                  OR COLUMN_DEFAULT <> 'balance'
                  OR COLUMN_COMMENT NOT LIKE '%quota%'
              )
        ),
        "ALTER TABLE `sys_user` MODIFY COLUMN `subscription_type` VARCHAR(16) NOT NULL DEFAULT 'balance' COMMENT 'balance=按量计费, unlimited/quota=套餐缓存态'",
        "SELECT 'sys_user.subscription_type already compatible' AS message"
    )
);

PREPARE stmt FROM @alter_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
