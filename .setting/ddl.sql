# 2026-03-13 20:39:53
ALTER TABLE user_api_key ADD COLUMN key_full VARCHAR(128) NULL COMMENT '完整API Key明文' AFTER key_hash;
# 2026-03-14 12:12:11
ALTER TABLE user_api_key ADD COLUMN total_cost DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '总消费金额(USD)' AFTER total_tokens;
# 2026-03-16 13:06:05
ALTER TABLE sys_user 
ADD COLUMN subscription_type ENUM('balance', 'unlimited') DEFAULT 'balance' COMMENT '计费类型：balance=按量计费，unlimited=时间套餐',
ADD COLUMN subscription_expires_at DATETIME NULL COMMENT '套餐过期时间';
# 2026-03-16 13:06:13
CREATE TABLE user_subscription (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    plan_name VARCHAR(64) NOT NULL COMMENT '套餐名称',
    plan_type ENUM('monthly', 'quarterly', 'yearly', 'custom') NOT NULL COMMENT '套餐类型',
    start_time DATETIME NOT NULL COMMENT '开始时间',
    end_time DATETIME NOT NULL COMMENT '结束时间',
    status ENUM('active', 'expired', 'cancelled') DEFAULT 'active' COMMENT '状态',
    created_by BIGINT UNSIGNED COMMENT '创建者（管理员ID）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_end_time (end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户套餐记录表';
# 2026-03-30 16:04:18
CREATE TABLE IF NOT EXISTS `redemption_code` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(32) NOT NULL COMMENT '兑换码',
  `amount` DECIMAL(12,6) NOT NULL COMMENT '兑换金额(美元)',
  `status` ENUM('unused','used','expired') NOT NULL DEFAULT 'unused' COMMENT '状态',
  `created_by` BIGINT NOT NULL COMMENT '创建者(管理员ID)',
  `used_by` BIGINT DEFAULT NULL COMMENT '使用者(用户ID)',
  `used_at` DATETIME DEFAULT NULL COMMENT '使用时间',
  `expires_at` DATETIME DEFAULT NULL COMMENT '过期时间',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`),
  KEY `idx_status` (`status`),
  KEY `idx_used_by` (`used_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='兑换码表';
# 2026-03-30 16:15:42
CREATE TABLE `redemption_code` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `code` VARCHAR(32) NOT NULL COMMENT '兑换码',
    `amount` DECIMAL(12, 6) NOT NULL COMMENT '兑换金额(美元)',
    `status` ENUM('unused', 'used', 'expired') NOT NULL DEFAULT 'unused' COMMENT '状态',
    `created_by` BIGINT UNSIGNED NOT NULL COMMENT '创建者(管理员ID)',
    `used_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '使用者(用户ID)',
    `used_at` DATETIME DEFAULT NULL COMMENT '使用时间',
    `expires_at` DATETIME DEFAULT NULL COMMENT '过期时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_status` (`status`),
    KEY `idx_created_by` (`created_by`),
    KEY `idx_used_by` (`used_by`),
    KEY `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='兑换码表';
