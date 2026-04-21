-- Google 生图分辨率计费升级脚本
-- 日期：2026-04-20

ALTER TABLE `unified_model`
  MODIFY COLUMN `image_credit_multiplier` DECIMAL(12, 3) NOT NULL DEFAULT 1 COMMENT '图片请求默认扣减倍率';

ALTER TABLE `request_log`
  MODIFY COLUMN `image_credits_charged` DECIMAL(12, 3) DEFAULT 0;

ALTER TABLE `user_image_balance`
  MODIFY COLUMN `balance` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '图片积分余额',
  MODIFY COLUMN `total_recharged` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '总充值图片积分',
  MODIFY COLUMN `total_consumed` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '总消耗图片积分';

ALTER TABLE `image_credit_record`
  MODIFY COLUMN `change_amount` DECIMAL(12, 3) NOT NULL COMMENT '正数=充值，负数=扣减',
  MODIFY COLUMN `balance_before` DECIMAL(12, 3) NOT NULL DEFAULT 0,
  MODIFY COLUMN `balance_after` DECIMAL(12, 3) NOT NULL DEFAULT 0,
  MODIFY COLUMN `multiplier` DECIMAL(12, 3) NOT NULL DEFAULT 1;

SET @add_request_log_image_size = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'request_log'
        AND COLUMN_NAME = 'image_size'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `image_size` VARCHAR(16) DEFAULT NULL COMMENT 'Google 生图分辨率档位' AFTER `image_count`"
  )
);
PREPARE stmt FROM @add_request_log_image_size;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_image_credit_record_image_size = (
  SELECT IF(
    EXISTS (
      SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'image_credit_record'
        AND COLUMN_NAME = 'image_size'
    ),
    'SELECT 1',
    "ALTER TABLE `image_credit_record` ADD COLUMN `image_size` VARCHAR(16) DEFAULT NULL COMMENT 'Google 生图分辨率档位' AFTER `multiplier`"
  )
);
PREPARE stmt FROM @add_image_credit_record_image_size;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS `model_image_resolution_rule` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `unified_model_id` BIGINT UNSIGNED NOT NULL,
  `resolution_code` VARCHAR(16) NOT NULL COMMENT '512/1K/2K/4K',
  `enabled` TINYINT NOT NULL DEFAULT 1,
  `credit_cost` DECIMAL(12, 3) NOT NULL DEFAULT 1 COMMENT '该分辨率对应图片积分',
  `is_default` TINYINT NOT NULL DEFAULT 0,
  `sort_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_resolution_code` (`unified_model_id`, `resolution_code`),
  KEY `idx_resolution_model_id` (`unified_model_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型图片分辨率计费规则表';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '1K', 1, 1.000, 1, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-2.5-flash-image'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '1K'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '512', 1, 1.000, 0, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '512'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '1K', 1, 2.000, 1, 20
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '1K'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '2K', 1, 3.000, 0, 30
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '2K'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '4K', 1, 4.000, 0, 40
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '4K'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '1K', 1, 3.000, 1, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3-pro-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '1K'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '2K', 1, 4.500, 0, 20
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3-pro-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '2K'
  );

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '4K', 1, 6.000, 0, 30
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3-pro-image-preview'
  AND NOT EXISTS (
    SELECT 1 FROM `model_image_resolution_rule` r
    WHERE r.`unified_model_id` = um.id AND r.`resolution_code` = '4K'
  );
