-- Add per-subscription quota refresh period selection.
-- NULL means the user has not selected a period and the legacy 1-day cycle applies.
-- Use information_schema checks instead of ADD COLUMN IF NOT EXISTS because
-- MySQL 9.x does not support that form of ALTER TABLE syntax.
SET @add_refresh_period_days = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `user_subscription` ADD COLUMN `refresh_period_days` INT NULL COMMENT ''用户选择的额度刷新周期（天），NULL 表示未选择'' AFTER `reset_timezone`',
    'SET @subscription_refresh_period_noop = 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'user_subscription'
    AND column_name = 'refresh_period_days'
);
PREPARE stmt FROM @add_refresh_period_days;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_refresh_period_selected_at = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `user_subscription` ADD COLUMN `refresh_period_selected_at` DATETIME NULL COMMENT ''用户选择额度刷新周期的时间'' AFTER `refresh_period_days`',
    'SET @subscription_refresh_period_noop = 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'user_subscription'
    AND column_name = 'refresh_period_selected_at'
);
PREPARE stmt FROM @add_refresh_period_selected_at;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
