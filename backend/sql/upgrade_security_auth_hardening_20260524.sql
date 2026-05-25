-- 安全-登录与CORS加固：JWT token_version 字段
SET @column_exists := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'token_version'
);

SET @sql := IF(
    @column_exists = 0,
    'ALTER TABLE `sys_user` ADD COLUMN `token_version` BIGINT NOT NULL DEFAULT 0 COMMENT ''登录令牌版本，递增后旧JWT失效'' AFTER `status`',
    'SELECT ''sys_user.token_version already exists'''
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
