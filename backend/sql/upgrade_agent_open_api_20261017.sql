-- Agent open API key management, recharge idempotency reservations and rate snapshot.
-- Safe to run repeatedly on MySQL 8 / supported MariaDB deployments.

CREATE TABLE IF NOT EXISTS `agent_open_api_key` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `name` VARCHAR(128) NOT NULL,
    `key_hash` VARCHAR(64) NOT NULL,
    `key_prefix` VARCHAR(16) NOT NULL,
    `scopes_json` TEXT NOT NULL,
    `status` VARCHAR(16) NOT NULL DEFAULT 'active',
    `created_by_user_id` BIGINT UNSIGNED NOT NULL,
    `expires_at` DATETIME NOT NULL,
    `last_used_at` DATETIME DEFAULT NULL,
    `revoked_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_open_api_key_hash` (`key_hash`),
    KEY `ix_agent_open_api_key_agent_id` (`agent_id`),
    KEY `ix_agent_open_api_key_key_prefix` (`key_prefix`),
    KEY `ix_agent_open_api_key_status` (`status`),
    KEY `ix_agent_open_api_key_created_by_user_id` (`created_by_user_id`),
    KEY `ix_agent_open_api_key_expires_at` (`expires_at`),
    KEY `ix_agent_open_api_key_agent_status_expiry` (`agent_id`, `status`, `expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理开放 API 凭据';

CREATE TABLE IF NOT EXISTS `agent_open_api_idempotency` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `key_id` BIGINT UNSIGNED NOT NULL,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `idempotency_hash` VARCHAR(64) NOT NULL,
    `request_fingerprint` VARCHAR(64) NOT NULL,
    `request_json` TEXT NOT NULL,
    `user_recharge_rate_code` VARCHAR(1) NOT NULL,
    `user_recharge_rate` DECIMAL(12,6) NOT NULL,
    `agent_settlement_rate` DECIMAL(12,6) NOT NULL,
    `order_no` VARCHAR(64) NOT NULL,
    `status` VARCHAR(24) NOT NULL DEFAULT 'reserved' COMMENT 'reserved/provisioning/ready/retryable_failed',
    `lease_until` DATETIME NOT NULL,
    `attempts` INT NOT NULL DEFAULT 0,
    `completed_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_open_api_idem_key_user_hash` (`key_id`, `user_id`, `idempotency_hash`),
    UNIQUE KEY `uk_agent_open_api_idem_order_no` (`order_no`),
    KEY `ix_agent_open_api_idempotency_agent_id` (`agent_id`),
    KEY `ix_agent_open_api_idempotency_key_id` (`key_id`),
    KEY `ix_agent_open_api_idempotency_user_id` (`user_id`),
    KEY `ix_agent_open_api_idempotency_status` (`status`),
    KEY `ix_agent_open_api_idem_status_lease` (`status`, `lease_until`),
    KEY `ix_agent_open_api_idem_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理开放 API 充值幂等预约';

SET @open_api_rate_code_exists := (
    SELECT COUNT(1) FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'payment_recharge_order'
      AND column_name = 'user_recharge_rate_code'
);
SET @open_api_rate_code_sql := IF(
    @open_api_rate_code_exists = 0,
    'ALTER TABLE `payment_recharge_order` ADD COLUMN `user_recharge_rate_code` VARCHAR(1) NULL AFTER `user_recharge_rate`',
    'SELECT ''payment_recharge_order.user_recharge_rate_code exists'''
);
PREPARE open_api_rate_code_stmt FROM @open_api_rate_code_sql;
EXECUTE open_api_rate_code_stmt;
DEALLOCATE PREPARE open_api_rate_code_stmt;
