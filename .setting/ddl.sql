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
