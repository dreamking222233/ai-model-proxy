-- Add per-subscription quota refresh period selection.
-- NULL means the user has not selected a period and the legacy 1-day cycle applies.
ALTER TABLE `user_subscription`
  ADD COLUMN IF NOT EXISTS `refresh_period_days` INT NULL COMMENT '用户选择的额度刷新周期（天），NULL 表示未选择' AFTER `reset_timezone`,
  ADD COLUMN IF NOT EXISTS `refresh_period_selected_at` DATETIME NULL COMMENT '用户选择额度刷新周期的时间' AFTER `refresh_period_days`;
