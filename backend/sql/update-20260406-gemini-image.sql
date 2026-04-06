-- Incremental database update for Gemini image generation and image credits
-- Date: 2026-04-06
-- Safe to run on an existing modelinvoke database.

ALTER TABLE `channel`
  MODIFY COLUMN `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai',
  MODIFY COLUMN `auth_header_type` VARCHAR(32) NOT NULL DEFAULT 'x-api-key' COMMENT '鉴权头类型: authorization/x-api-key/anthropic-api-key/x-goog-api-key';

ALTER TABLE `unified_model`
  MODIFY COLUMN `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai';

SET @ddl = IF(
  EXISTS(
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'unified_model'
      AND COLUMN_NAME = 'billing_type'
  ),
  'SELECT 1',
  "ALTER TABLE `unified_model` ADD COLUMN `billing_type` VARCHAR(20) NOT NULL DEFAULT 'token' COMMENT 'token/image_credit/free' AFTER `output_price_per_million`"
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = IF(
  EXISTS(
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'unified_model'
      AND COLUMN_NAME = 'image_credit_multiplier'
  ),
  'SELECT 1',
  "ALTER TABLE `unified_model` ADD COLUMN `image_credit_multiplier` INT NOT NULL DEFAULT 1 COMMENT '图片请求扣减倍率' AFTER `billing_type`"
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE `request_log`
  MODIFY COLUMN `protocol_type` ENUM('openai', 'anthropic', 'google') DEFAULT NULL;

SET @ddl = IF(
  EXISTS(
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'request_log'
      AND COLUMN_NAME = 'request_type'
  ),
  'SELECT 1',
  "ALTER TABLE `request_log` ADD COLUMN `request_type` VARCHAR(32) DEFAULT 'chat' AFTER `protocol_type`"
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = IF(
  EXISTS(
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'request_log'
      AND COLUMN_NAME = 'billing_type'
  ),
  'SELECT 1',
  "ALTER TABLE `request_log` ADD COLUMN `billing_type` VARCHAR(20) DEFAULT 'token' AFTER `request_type`"
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = IF(
  EXISTS(
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'request_log'
      AND COLUMN_NAME = 'image_credits_charged'
  ),
  'SELECT 1',
  "ALTER TABLE `request_log` ADD COLUMN `image_credits_charged` INT DEFAULT 0 AFTER `total_tokens`"
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = IF(
  EXISTS(
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'request_log'
      AND COLUMN_NAME = 'image_count'
  ),
  'SELECT 1',
  "ALTER TABLE `request_log` ADD COLUMN `image_count` INT DEFAULT 0 AFTER `image_credits_charged`"
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS `user_image_balance` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `balance` INT NOT NULL DEFAULT 0 COMMENT '图片积分余额',
  `total_recharged` INT NOT NULL DEFAULT 0 COMMENT '总充值图片积分',
  `total_consumed` INT NOT NULL DEFAULT 0 COMMENT '总消耗图片积分',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_image_balance_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户图片积分余额表';

CREATE TABLE IF NOT EXISTS `image_credit_record` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `request_id` VARCHAR(36) DEFAULT NULL,
  `model_name` VARCHAR(128) DEFAULT NULL,
  `change_amount` INT NOT NULL COMMENT '正数=充值，负数=扣减',
  `balance_before` INT NOT NULL DEFAULT 0,
  `balance_after` INT NOT NULL DEFAULT 0,
  `multiplier` INT NOT NULL DEFAULT 1,
  `action_type` VARCHAR(20) NOT NULL DEFAULT 'request' COMMENT 'request/recharge/deduct',
  `operator_id` BIGINT UNSIGNED DEFAULT NULL,
  `remark` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_image_credit_user_id` (`user_id`),
  KEY `idx_image_credit_request_id` (`request_id`),
  KEY `idx_image_credit_operator_id` (`operator_id`),
  KEY `idx_image_credit_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图片积分流水表';

INSERT INTO `user_image_balance` (`user_id`, `balance`, `total_recharged`, `total_consumed`)
SELECT `id`, 0, 0, 0
FROM `sys_user`
WHERE NOT EXISTS (
  SELECT 1 FROM `user_image_balance` uib WHERE uib.user_id = `sys_user`.`id`
);

INSERT INTO `unified_model` (
  `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
  `input_price_per_million`, `output_price_per_million`, `billing_type`, `image_credit_multiplier`, `enabled`, `description`
)
SELECT * FROM (
  SELECT 'gemini-3.1-flash-image-preview', 'Gemini 3.1 Flash Image Preview', 'image', 'google', NULL, 0, 0, 'image_credit', 1, 1, 'Google Gemini 图片生成（按图片积分计费）'
) AS tmp
WHERE NOT EXISTS (
  SELECT 1 FROM `unified_model` WHERE `model_name` = 'gemini-3.1-flash-image-preview'
);

INSERT INTO `unified_model` (
  `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
  `input_price_per_million`, `output_price_per_million`, `billing_type`, `image_credit_multiplier`, `enabled`, `description`
)
SELECT * FROM (
  SELECT 'gemini-3-pro-image-preview', 'Gemini 3 Pro Image Preview', 'image', 'google', NULL, 0, 0, 'image_credit', 2, 1, 'Google Gemini Pro 图片生成（按图片积分计费）'
) AS tmp
WHERE NOT EXISTS (
  SELECT 1 FROM `unified_model` WHERE `model_name` = 'gemini-3-pro-image-preview'
);

UPDATE `unified_model`
SET `protocol_type` = 'google', `model_type` = 'image', `billing_type` = 'image_credit', `image_credit_multiplier` = 1
WHERE `model_name` = 'gemini-3.1-flash-image-preview';

UPDATE `unified_model`
SET `protocol_type` = 'google', `model_type` = 'image', `billing_type` = 'image_credit', `image_credit_multiplier` = 2
WHERE `model_name` = 'gemini-3-pro-image-preview';
