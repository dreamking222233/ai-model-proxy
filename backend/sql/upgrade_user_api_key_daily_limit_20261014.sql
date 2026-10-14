-- Schema first; deploy all workers after draining old in-flight requests.
-- Idempotent: repeated execution preserves counters and configured limits.

SET @daily_limit_ddl = IF(
  EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'user_api_key' AND column_name = 'daily_limit_usd'),
  'SELECT 1', 'ALTER TABLE `user_api_key` ADD COLUMN `daily_limit_usd` DECIMAL(20,6) NULL');
PREPARE daily_limit_stmt FROM @daily_limit_ddl;
EXECUTE daily_limit_stmt;
DEALLOCATE PREPARE daily_limit_stmt;

SET @daily_limit_ddl = IF(
  EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'user_api_key' AND column_name = 'daily_used_usd'),
  'SELECT 1', 'ALTER TABLE `user_api_key` ADD COLUMN `daily_used_usd` DECIMAL(20,6) NOT NULL DEFAULT 0');
PREPARE daily_limit_stmt FROM @daily_limit_ddl;
EXECUTE daily_limit_stmt;
DEALLOCATE PREPARE daily_limit_stmt;

SET @daily_limit_ddl = IF(
  EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'user_api_key' AND column_name = 'daily_usage_date'),
  'SELECT 1', 'ALTER TABLE `user_api_key` ADD COLUMN `daily_usage_date` DATE NULL');
PREPARE daily_limit_stmt FROM @daily_limit_ddl;
EXECUTE daily_limit_stmt;
DEALLOCATE PREPARE daily_limit_stmt;

SET @daily_limit_ddl = IF(
  EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'video_task_billing_snapshot' AND column_name = 'user_api_key_id'),
  'SELECT 1', 'ALTER TABLE `video_task_billing_snapshot` ADD COLUMN `user_api_key_id` BIGINT UNSIGNED NULL');
PREPARE daily_limit_stmt FROM @daily_limit_ddl;
EXECUTE daily_limit_stmt;
DEALLOCATE PREPARE daily_limit_stmt;
