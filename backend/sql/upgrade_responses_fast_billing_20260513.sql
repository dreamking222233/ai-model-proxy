ALTER TABLE `request_log`
  ADD COLUMN `service_tier` VARCHAR(32) DEFAULT NULL COMMENT 'Responses service tier snapshot' AFTER `quota_cycle_date`,
  ADD COLUMN `fast_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 AFTER `price_multiplier_snapshot`;

ALTER TABLE `consumption_record`
  ADD COLUMN `service_tier` VARCHAR(32) DEFAULT NULL COMMENT 'Responses service tier snapshot' AFTER `quota_cycle_date`,
  ADD COLUMN `fast_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 AFTER `price_multiplier_snapshot`;
