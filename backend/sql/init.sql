-- ============================================================
-- 大模型调用中转平台 - 数据库初始化脚本
-- Database: modelinvoke
-- ============================================================

-- 清空所有旧表和视图
SET FOREIGN_KEY_CHECKS = 0;

-- 删除所有视图
SET @views = NULL;
SELECT GROUP_CONCAT('`', table_name, '`') INTO @views
FROM information_schema.views
WHERE table_schema = 'modelinvoke';
SET @views = IF(@views IS NOT NULL, CONCAT('DROP VIEW IF EXISTS ', @views), 'SELECT 1');
PREPARE stmt FROM @views;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 删除所有表
SET @tables = NULL;
SELECT GROUP_CONCAT('`', table_name, '`') INTO @tables
FROM information_schema.tables
WHERE table_schema = 'modelinvoke' AND table_type = 'BASE TABLE';
SET @tables = IF(@tables IS NOT NULL, CONCAT('DROP TABLE IF EXISTS ', @tables), 'SELECT 1');
PREPARE stmt FROM @tables;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 1. sys_user - 系统用户表
-- ============================================================
CREATE TABLE `sys_user` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `username` VARCHAR(64) NOT NULL,
    `email` VARCHAR(128) NOT NULL,
    `password_hash` VARCHAR(256) NOT NULL,
    `role` ENUM('admin', 'user') NOT NULL DEFAULT 'user',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '1=正常, 0=禁用',
    `avatar` VARCHAR(512) DEFAULT NULL,
    `last_login_at` DATETIME DEFAULT NULL,
    `last_login_ip` VARCHAR(45) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_email` (`email`),
    KEY `idx_role` (`role`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- ============================================================
-- 2. user_api_key - 用户 API Key 表
-- ============================================================
CREATE TABLE `user_api_key` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `name` VARCHAR(128) NOT NULL COMMENT 'Key备注名称',
    `key_prefix` VARCHAR(16) NOT NULL COMMENT '展示用前缀,如sk-xxxx',
    `key_hash` VARCHAR(64) NOT NULL COMMENT 'SHA256哈希',
    `key_full` VARCHAR(128) DEFAULT NULL COMMENT '完整API Key明文',
    `status` ENUM('active', 'disabled', 'expired') NOT NULL DEFAULT 'active',
    `expires_at` DATETIME DEFAULT NULL,
    `total_requests` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `total_tokens` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `total_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '总消费金额(USD)',
    `last_used_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_key_hash` (`key_hash`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`),
    KEY `idx_key_prefix` (`key_prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户API Key表';

-- ============================================================
-- 3. channel - 渠道（模型提供商）表
-- ============================================================
CREATE TABLE `channel` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(128) NOT NULL,
    `base_url` VARCHAR(512) NOT NULL,
    `api_key` TEXT NOT NULL COMMENT '加密存储的API Key',
    `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai',
    `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default' COMMENT '渠道子类型: default/google-official/google-vertex-image',
    `auth_header_type` VARCHAR(32) NOT NULL DEFAULT 'x-api-key' COMMENT '鉴权头类型: authorization/x-api-key/anthropic-api-key/x-goog-api-key',
    `priority` INT NOT NULL DEFAULT 10 COMMENT '优先级,1=最高',
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `health_check_enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否参与健康监控',
    `is_healthy` TINYINT NOT NULL DEFAULT 1,
    `health_score` INT NOT NULL DEFAULT 100 COMMENT '健康分0-100',
    `failure_count` INT NOT NULL DEFAULT 0 COMMENT '连续失败次数',
    `circuit_breaker_until` DATETIME DEFAULT NULL COMMENT '熔断截止时间',
    `health_check_model` VARCHAR(128) DEFAULT NULL COMMENT '健康检查优先使用的模型名',
    `last_health_check_at` DATETIME DEFAULT NULL,
    `last_success_at` DATETIME DEFAULT NULL,
    `last_failure_at` DATETIME DEFAULT NULL,
    `description` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_enabled` (`enabled`),
    KEY `idx_priority` (`priority`),
    KEY `idx_is_healthy` (`is_healthy`),
    KEY `idx_protocol_type` (`protocol_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='渠道(模型提供商)表';

-- ============================================================
-- 4. unified_model - 统一模型定义表
-- ============================================================
CREATE TABLE `unified_model` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `model_name` VARCHAR(128) NOT NULL COMMENT '统一模型名称,用户请求时使用',
    `display_name` VARCHAR(128) DEFAULT NULL,
    `model_type` ENUM('chat', 'embedding', 'image') NOT NULL DEFAULT 'chat',
    `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai',
    `max_tokens` INT DEFAULT NULL,
    `input_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万输入Token单价(美元)',
    `output_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万输出Token单价(美元)',
    `billing_type` VARCHAR(20) NOT NULL DEFAULT 'token' COMMENT 'token/image_credit/free',
    `image_credit_multiplier` DECIMAL(12, 3) NOT NULL DEFAULT 1 COMMENT '图片请求默认扣减倍率',
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `description` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_model_name` (`model_name`),
    KEY `idx_model_type` (`model_type`),
    KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统一模型定义表';

-- ============================================================
-- 5. model_channel_mapping - 模型-渠道映射表
-- ============================================================
CREATE TABLE `model_channel_mapping` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `unified_model_id` BIGINT UNSIGNED NOT NULL,
    `channel_id` BIGINT UNSIGNED NOT NULL,
    `actual_model_name` VARCHAR(128) NOT NULL COMMENT '该渠道中的实际模型名称',
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_model_channel` (`unified_model_id`, `channel_id`),
    KEY `idx_channel_id` (`channel_id`),
    KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型-渠道映射表';

-- ============================================================
-- 5.1 model_image_resolution_rule - 模型图片分辨率计费规则
-- ============================================================
CREATE TABLE `model_image_resolution_rule` (
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

-- ============================================================
-- 6. model_override_rule - 模型覆盖规则表
-- ============================================================
CREATE TABLE `model_override_rule` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(128) NOT NULL,
    `rule_type` ENUM('redirect_all', 'redirect_specific') NOT NULL,
    `source_pattern` VARCHAR(128) NOT NULL COMMENT '*=所有,或具体模型名',
    `target_unified_model_id` BIGINT UNSIGNED NOT NULL,
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `priority` INT NOT NULL DEFAULT 10 COMMENT '规则优先级,数字小优先',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_enabled_priority` (`enabled`, `priority`),
    KEY `idx_source_pattern` (`source_pattern`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型覆盖规则表';

-- ============================================================
-- 7. health_check_log - 健康检查记录表
-- ============================================================
CREATE TABLE `health_check_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `channel_id` BIGINT UNSIGNED NOT NULL,
    `channel_name` VARCHAR(128) NOT NULL,
    `model_name` VARCHAR(128) DEFAULT NULL,
    `status` ENUM('success', 'fail') NOT NULL,
    `response_time_ms` INT DEFAULT NULL,
    `error_message` TEXT DEFAULT NULL,
    `checked_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_channel_id` (`channel_id`),
    KEY `idx_checked_at` (`checked_at`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康检查记录表';

-- ============================================================
-- 8. request_log - 请求日志表
-- ============================================================
CREATE TABLE `request_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `request_id` VARCHAR(36) NOT NULL COMMENT 'UUID',
    `user_id` BIGINT UNSIGNED DEFAULT NULL,
    `user_api_key_id` BIGINT UNSIGNED DEFAULT NULL,
    `channel_id` BIGINT UNSIGNED DEFAULT NULL,
    `channel_name` VARCHAR(128) DEFAULT NULL,
    `requested_model` VARCHAR(128) DEFAULT NULL COMMENT '用户请求的模型名',
    `actual_model` VARCHAR(128) DEFAULT NULL COMMENT '实际发送的模型名',
    `protocol_type` ENUM('openai', 'anthropic', 'google') DEFAULT NULL,
    `request_type` VARCHAR(32) DEFAULT 'chat',
    `billing_type` VARCHAR(20) DEFAULT 'token',
    `is_stream` TINYINT DEFAULT 0,
    `input_tokens` INT DEFAULT 0,
    `output_tokens` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `raw_input_tokens` INT DEFAULT 0,
    `raw_output_tokens` INT DEFAULT 0,
    `raw_total_tokens` INT DEFAULT 0,
    `image_credits_charged` DECIMAL(12, 3) DEFAULT 0,
    `image_count` INT DEFAULT 0,
    `image_size` VARCHAR(16) DEFAULT NULL COMMENT 'Google 生图分辨率档位',
    `response_time_ms` INT DEFAULT NULL,
    `cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Request body cache status',
    `cache_hit_segments` INT NOT NULL DEFAULT 0,
    `cache_miss_segments` INT NOT NULL DEFAULT 0,
    `cache_bypass_segments` INT NOT NULL DEFAULT 0,
    `cache_reused_tokens` INT NOT NULL DEFAULT 0,
    `cache_new_tokens` INT NOT NULL DEFAULT 0,
    `cache_reused_chars` INT NOT NULL DEFAULT 0,
    `cache_new_chars` INT NOT NULL DEFAULT 0,
    `logical_input_tokens` INT DEFAULT 0,
    `upstream_input_tokens` INT DEFAULT 0,
    `upstream_cache_read_input_tokens` INT DEFAULT 0,
    `upstream_cache_creation_input_tokens` INT DEFAULT 0,
    `upstream_cache_creation_5m_input_tokens` INT DEFAULT 0,
    `upstream_cache_creation_1h_input_tokens` INT DEFAULT 0,
    `upstream_prompt_cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Anthropic prompt cache status',
    `conversation_session_id` VARCHAR(64) DEFAULT NULL COMMENT 'Conversation session id',
    `conversation_match_status` VARCHAR(20) DEFAULT NULL COMMENT 'Conversation match status',
    `compression_mode` VARCHAR(32) DEFAULT NULL COMMENT 'Conversation compaction mode',
    `compression_status` VARCHAR(64) DEFAULT NULL COMMENT 'Conversation compaction status',
    `original_estimated_input_tokens` INT DEFAULT 0,
    `compressed_estimated_input_tokens` INT DEFAULT 0,
    `compression_saved_estimated_tokens` INT DEFAULT 0,
    `compression_ratio` DECIMAL(10, 4) DEFAULT 0,
    `compression_fallback_reason` TEXT DEFAULT NULL,
    `upstream_session_mode` VARCHAR(20) DEFAULT NULL COMMENT 'Upstream session mode',
    `upstream_session_id` VARCHAR(128) DEFAULT NULL COMMENT 'Upstream session id',
    `status` ENUM('success', 'error', 'timeout') NOT NULL DEFAULT 'success',
    `error_message` TEXT DEFAULT NULL,
    `client_ip` VARCHAR(45) DEFAULT NULL,
    `subscription_cycle_id` BIGINT UNSIGNED DEFAULT NULL,
    `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd',
    `quota_consumed_amount` DECIMAL(20, 6) DEFAULT 0,
    `quota_limit_snapshot` DECIMAL(20, 6) DEFAULT 0,
    `quota_used_after` DECIMAL(20, 6) DEFAULT 0,
    `quota_cycle_date` DATE DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_request_id` (`request_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_channel_id` (`channel_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_status` (`status`),
    KEY `idx_requested_model` (`requested_model`),
    KEY `idx_conversation_session_id` (`conversation_session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求日志表';

-- ============================================================
-- 9. request_cache_summary - 请求体缓存摘要表
-- ============================================================
CREATE TABLE `request_cache_summary` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `request_id` VARCHAR(36) NOT NULL COMMENT 'Request UUID',
    `user_id` BIGINT UNSIGNED DEFAULT NULL,
    `requested_model` VARCHAR(128) DEFAULT NULL,
    `protocol_type` VARCHAR(20) DEFAULT NULL,
    `request_format` VARCHAR(32) DEFAULT NULL COMMENT 'anthropic_messages/openai_chat/responses',
    `cache_status` VARCHAR(20) NOT NULL DEFAULT 'BYPASS',
    `hit_segment_count` INT NOT NULL DEFAULT 0,
    `miss_segment_count` INT NOT NULL DEFAULT 0,
    `bypass_segment_count` INT NOT NULL DEFAULT 0,
    `reused_tokens` INT NOT NULL DEFAULT 0,
    `new_tokens` INT NOT NULL DEFAULT 0,
    `reused_chars` INT NOT NULL DEFAULT 0,
    `new_chars` INT NOT NULL DEFAULT 0,
    `ttl_seconds` INT NOT NULL DEFAULT 0,
    `details_json` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_request_id` (`request_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_requested_model` (`requested_model`),
    KEY `idx_cache_status` (`cache_status`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求体缓存摘要表';

-- ============================================================
-- 10. system_config - 系统配置表
-- ============================================================
CREATE TABLE `system_config` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `config_key` VARCHAR(128) NOT NULL,
    `config_value` TEXT NOT NULL,
    `config_type` ENUM('string', 'number', 'boolean', 'json') NOT NULL DEFAULT 'string',
    `description` VARCHAR(512) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_config_key` (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ============================================================
-- 10. operation_log - 操作日志表
-- ============================================================
CREATE TABLE `operation_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED DEFAULT NULL,
    `username` VARCHAR(64) DEFAULT NULL,
    `action` VARCHAR(64) NOT NULL,
    `target_type` VARCHAR(64) DEFAULT NULL,
    `target_id` BIGINT UNSIGNED DEFAULT NULL,
    `description` TEXT DEFAULT NULL,
    `ip_address` VARCHAR(45) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_action` (`action`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- ============================================================
-- 11. user_balance - 用户余额表
-- ============================================================
CREATE TABLE `user_balance` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `balance` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '余额(美元)',
    `total_recharged` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '总充值',
    `total_consumed` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '总消费',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户余额表';

-- ============================================================
-- 11.1 user_image_balance - 用户图片积分余额表
-- ============================================================
CREATE TABLE `user_image_balance` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `balance` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '图片积分余额',
    `total_recharged` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '总充值图片积分',
    `total_consumed` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '总消耗图片积分',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_image_balance_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户图片积分余额表';

-- ============================================================
-- 12. consumption_record - 消费记录表
-- ============================================================
CREATE TABLE `consumption_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `request_id` VARCHAR(36) DEFAULT NULL,
    `model_name` VARCHAR(128) DEFAULT NULL,
    `input_tokens` INT DEFAULT 0,
    `output_tokens` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `raw_input_tokens` INT DEFAULT 0,
    `raw_output_tokens` INT DEFAULT 0,
    `raw_total_tokens` INT DEFAULT 0,
    `logical_input_tokens` INT DEFAULT 0,
    `upstream_input_tokens` INT DEFAULT 0,
    `upstream_cache_read_input_tokens` INT DEFAULT 0,
    `upstream_cache_creation_input_tokens` INT DEFAULT 0,
    `upstream_prompt_cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Anthropic prompt cache status',
    `input_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `output_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `balance_before` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `balance_after` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `billing_mode` VARCHAR(20) DEFAULT NULL COMMENT 'balance=按量计费, subscription=套餐计费',
    `subscription_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '关联套餐ID',
    `subscription_cycle_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '关联套餐周期ID',
    `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd',
    `quota_consumed_amount` DECIMAL(20, 6) DEFAULT 0,
    `quota_limit_snapshot` DECIMAL(20, 6) DEFAULT 0,
    `quota_used_after` DECIMAL(20, 6) DEFAULT 0,
    `quota_cycle_date` DATE DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_request_id` (`request_id`),
    KEY `idx_billing_mode` (`billing_mode`),
    KEY `idx_subscription_id` (`subscription_id`),
    KEY `idx_subscription_cycle_id` (`subscription_cycle_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消费记录表';

-- ============================================================
-- 12.1 subscription_plan - 套餐模板表
-- ============================================================
CREATE TABLE `subscription_plan` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `plan_code` VARCHAR(64) NOT NULL COMMENT '套餐编码',
    `plan_name` VARCHAR(64) NOT NULL COMMENT '套餐名称',
    `plan_kind` VARCHAR(20) NOT NULL DEFAULT 'unlimited' COMMENT 'unlimited/daily_quota',
    `duration_mode` VARCHAR(20) NOT NULL DEFAULT 'custom',
    `duration_days` INT NOT NULL DEFAULT 1,
    `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd',
    `quota_value` DECIMAL(20, 6) DEFAULT 0,
    `reset_period` VARCHAR(20) NOT NULL DEFAULT 'day',
    `reset_timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    `sort_order` INT NOT NULL DEFAULT 0,
    `status` VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active/inactive',
    `description` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_subscription_plan_code` (`plan_code`),
    KEY `idx_subscription_plan_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐模板表';

-- ============================================================
-- 12.2 user_subscription - 用户套餐记录表
-- ============================================================
CREATE TABLE `user_subscription` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `plan_id` BIGINT UNSIGNED DEFAULT NULL,
    `plan_code_snapshot` VARCHAR(64) DEFAULT NULL COMMENT '套餐编码快照',
    `plan_name` VARCHAR(64) NOT NULL COMMENT '套餐名称',
    `plan_type` VARCHAR(20) NOT NULL COMMENT '套餐类型',
    `plan_kind_snapshot` VARCHAR(20) DEFAULT NULL COMMENT 'unlimited/daily_quota',
    `duration_days_snapshot` INT DEFAULT 0,
    `quota_metric` VARCHAR(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd',
    `quota_value` DECIMAL(20, 6) DEFAULT 0,
    `reset_period` VARCHAR(20) DEFAULT 'day',
    `reset_timezone` VARCHAR(64) DEFAULT 'Asia/Shanghai',
    `activation_mode` VARCHAR(20) DEFAULT 'append',
    `start_time` DATETIME NOT NULL COMMENT '开始时间',
    `end_time` DATETIME NOT NULL COMMENT '结束时间',
    `status` VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active/expired/cancelled',
    `created_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '创建者（管理员ID）',
    `activated_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_subscription_user_id` (`user_id`),
    KEY `idx_user_subscription_plan_id` (`plan_id`),
    KEY `idx_user_subscription_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户套餐记录表';

-- ============================================================
-- 12.3 subscription_usage_cycle - 套餐每日额度周期表
-- ============================================================
CREATE TABLE `subscription_usage_cycle` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `subscription_id` BIGINT UNSIGNED NOT NULL,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `cycle_date` DATE NOT NULL COMMENT '业务日期',
    `cycle_start_at` DATETIME NOT NULL,
    `cycle_end_at` DATETIME NOT NULL,
    `quota_metric` VARCHAR(20) NOT NULL COMMENT 'total_tokens/cost_usd',
    `quota_limit` DECIMAL(20, 6) NOT NULL DEFAULT 0,
    `used_amount` DECIMAL(20, 6) NOT NULL DEFAULT 0,
    `request_count` INT NOT NULL DEFAULT 0,
    `last_request_id` VARCHAR(36) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_subscription_cycle_date` (`subscription_id`, `cycle_date`),
    KEY `idx_subscription_usage_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐每日额度周期表';

-- ============================================================
-- 12.4 image_credit_record - 图片积分流水表
-- ============================================================
CREATE TABLE `image_credit_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `request_id` VARCHAR(36) DEFAULT NULL,
    `model_name` VARCHAR(128) DEFAULT NULL,
    `change_amount` DECIMAL(12, 3) NOT NULL COMMENT '正数=充值，负数=扣减',
    `balance_before` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `balance_after` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `multiplier` DECIMAL(12, 3) NOT NULL DEFAULT 1,
    `image_size` VARCHAR(16) DEFAULT NULL COMMENT 'Google 生图分辨率档位',
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

-- ============================================================
-- 13. conversation_session - 会话状态表
-- ============================================================
CREATE TABLE `conversation_session` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `session_id` VARCHAR(64) NOT NULL,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `requested_model` VARCHAR(128) DEFAULT NULL,
    `protocol_type` VARCHAR(20) DEFAULT NULL,
    `channel_id` BIGINT UNSIGNED DEFAULT NULL,
    `system_hash` VARCHAR(64) NOT NULL,
    `tools_hash` VARCHAR(64) NOT NULL,
    `message_count` INT NOT NULL DEFAULT 0,
    `last_message_hash` VARCHAR(64) DEFAULT NULL,
    `compression_mode` VARCHAR(32) DEFAULT 'shadow',
    `upstream_session_mode` VARCHAR(20) DEFAULT 'stateless',
    `upstream_session_id` VARCHAR(128) DEFAULT NULL,
    `state_version` INT NOT NULL DEFAULT 1,
    `status` VARCHAR(20) NOT NULL DEFAULT 'active',
    `last_shadow_saved_tokens` INT NOT NULL DEFAULT 0,
    `cooldown_until` DATETIME DEFAULT NULL,
    `last_active_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_session_id` (`session_id`),
    KEY `idx_user_model_proto` (`user_id`, `requested_model`, `protocol_type`),
    KEY `idx_system_tools_hash` (`system_hash`, `tools_hash`),
    KEY `idx_status` (`status`),
    KEY `idx_last_active_at` (`last_active_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话状态表';

-- ============================================================
-- 14. conversation_checkpoint - 会话检查点表
-- ============================================================
CREATE TABLE `conversation_checkpoint` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `session_id` VARCHAR(64) NOT NULL,
    `checkpoint_seq` INT NOT NULL DEFAULT 1,
    `source_turn_start` INT NOT NULL DEFAULT 0,
    `source_turn_end` INT NOT NULL DEFAULT 0,
    `source_hash` VARCHAR(64) NOT NULL,
    `summary_json` TEXT NOT NULL,
    `summary_token_estimate` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_session_id` (`session_id`),
    KEY `idx_source_hash` (`source_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话检查点表';

-- ============================================================
-- 预置数据
-- ============================================================

-- 默认管理员账户 (密码: admin123)
INSERT INTO `sys_user` (`username`, `email`, `password_hash`, `role`, `status`)
VALUES ('admin', 'admin@example.com', '$2b$12$12TrajxYt22jQ3fm6EcpLOmOUZNhL676ooVq2ekIlyARRgG78LBUq', 'admin', 1);

-- 管理员余额
INSERT INTO `user_balance` (`user_id`, `balance`, `total_recharged`, `total_consumed`)
VALUES (1, 100.000000, 100.000000, 0);

-- 管理员图片积分余额
INSERT INTO `user_image_balance` (`user_id`, `balance`, `total_recharged`, `total_consumed`)
VALUES (1, 0.000, 0.000, 0.000);

-- 预置 Gemini 图片模型
INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `image_credit_multiplier`, `enabled`, `description`
) VALUES
('gemini-2.5-flash-image', 'Gemini 2.5 Flash Image', 'image', 'google', NULL, 0, 0, 'image_credit', 1, 1, 'Google Gemini 2.5 Flash 图片生成（按图片积分计费）'),
('gemini-3.1-flash-image-preview', 'Gemini 3.1 Flash Image Preview', 'image', 'google', NULL, 0, 0, 'image_credit', 2, 1, 'Google Gemini 3.1 Flash 图片生成（按图片积分计费）'),
('gemini-3-pro-image-preview', 'Gemini 3 Pro Image Preview', 'image', 'google', NULL, 0, 0, 'image_credit', 3, 1, 'Google Gemini 3 Pro 图片生成（按图片积分计费）');

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `image_credit_multiplier`, `enabled`, `description`
) VALUES
('gpt-image-2', 'GPT Image 2', 'image', 'openai', NULL, 0, 0, 'image_credit', 0.5, 1, 'OpenAI 兼容图片生成模型 GPT Image 2（按图片积分计费）');

-- 预置 Grok 文本模型
INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `image_credit_multiplier`, `enabled`, `description`
) VALUES
('grok-4.20-0309-non-reasoning', 'Grok 4.20 0309 Non-Reasoning', 'chat', 'openai', 128000, 2.000000, 6.000000, 'token', 1, 1, 'xAI Grok 4.20 0309 非推理版（官方定价 2/6）'),
('grok-4.20-0309', 'Grok 4.20 0309', 'chat', 'openai', 128000, 2.000000, 6.000000, 'token', 1, 1, 'xAI Grok 4.20 0309（按 4.20 主档推断定价 2/6）'),
('grok-4.20-0309-reasoning', 'Grok 4.20 0309 Reasoning', 'chat', 'openai', 128000, 2.000000, 6.000000, 'token', 1, 1, 'xAI Grok 4.20 0309 推理版（官方定价 2/6）'),
('grok-4.20-fast', 'Grok 4.20 Fast', 'chat', 'openai', 128000, 0.200000, 0.500000, 'token', 1, 1, 'xAI Grok 4.20 Fast（参照 4.1 fast 档推断定价 0.2/0.5）'),
('grok-4.20-auto', 'Grok 4.20 Auto', 'chat', 'openai', 128000, 2.000000, 6.000000, 'token', 1, 1, 'xAI Grok 4.20 Auto（按 4.20 主档推断定价 2/6）'),
('grok-4.20-expert', 'Grok 4.20 Expert', 'chat', 'openai', 128000, 2.000000, 6.000000, 'token', 1, 1, 'xAI Grok 4.20 Expert（按 4.20 高阶档推断定价 2/6）')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `protocol_type` = VALUES(`protocol_type`),
    `max_tokens` = VALUES(`max_tokens`),
    `input_price_per_million` = VALUES(`input_price_per_million`),
    `output_price_per_million` = VALUES(`output_price_per_million`),
    `billing_type` = VALUES(`billing_type`),
    `image_credit_multiplier` = VALUES(`image_credit_multiplier`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '1K', 1, 1.000, 1, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-2.5-flash-image';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '512', 1, 1.000, 0, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '1K', 1, 2.000, 1, 20
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '2K', 1, 3.000, 0, 30
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '4K', 1, 4.000, 0, 40
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3.1-flash-image-preview';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '1K', 1, 3.000, 1, 10
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3-pro-image-preview';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '2K', 1, 4.500, 0, 20
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3-pro-image-preview';

INSERT INTO `model_image_resolution_rule` (`unified_model_id`, `resolution_code`, `enabled`, `credit_cost`, `is_default`, `sort_order`)
SELECT um.id, '4K', 1, 6.000, 0, 30
FROM `unified_model` um
WHERE um.`model_name` = 'gemini-3-pro-image-preview';

-- 可选：Google Gemini 官方渠道与模型映射
-- 将 @google_api_key 从 NULL 改成真实密钥后再执行 init.sql，可自动创建渠道与映射。
SET @google_api_key = NULL;
SET @google_channel_name = 'Google Gemini Official';
SET @google_base_url = 'https://generativelanguage.googleapis.com';

INSERT INTO `channel` (
    `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
    `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
    @google_channel_name, @google_base_url, @google_api_key, 'google', 'google-official', 'x-goog-api-key',
    1, 1, 0, 1, 100, 0, 'Google Gemini 图片生成渠道'
FROM DUAL
WHERE @google_api_key IS NOT NULL;

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-2.5-flash-image', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @google_channel_name AND ch.`base_url` = @google_base_url
WHERE @google_api_key IS NOT NULL AND um.`model_name` = 'gemini-2.5-flash-image';

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-3.1-flash-image-preview', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @google_channel_name AND ch.`base_url` = @google_base_url
WHERE @google_api_key IS NOT NULL AND um.`model_name` = 'gemini-3.1-flash-image-preview';

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-3-pro-image-preview', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @google_channel_name AND ch.`base_url` = @google_base_url
WHERE @google_api_key IS NOT NULL AND um.`model_name` = 'gemini-3-pro-image-preview';

SET @google_api_key = NULL;
SET @google_channel_name = NULL;
SET @google_base_url = NULL;

-- 可选：Google Vertex 图片渠道与模型映射
-- 将 @vertex_api_key 从 NULL 改成真实密钥后再执行 init.sql，可自动创建 Vertex 渠道与推荐映射。
SET @vertex_api_key = NULL;
SET @vertex_channel_name = 'Google Vertex Image';
SET @vertex_base_url = 'https://aiplatform.googleapis.com';

INSERT INTO `channel` (
    `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
    `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `health_check_model`, `description`
)
SELECT
    @vertex_channel_name, @vertex_base_url, @vertex_api_key, 'google', 'google-vertex-image', 'x-goog-api-key',
    2, 1, 0, 1, 100, 0, 'gemini-2.5-flash', 'Google Vertex 图片生成渠道'
FROM DUAL
WHERE @vertex_api_key IS NOT NULL;

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @vertex_channel_name AND ch.`base_url` = @vertex_base_url
WHERE @vertex_api_key IS NOT NULL AND um.`model_name` = 'gemini-2.5-flash-image';

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-3.1-flash-image-preview', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @vertex_channel_name AND ch.`base_url` = @vertex_base_url
WHERE @vertex_api_key IS NOT NULL AND um.`model_name` = 'gemini-3.1-flash-image-preview';

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gemini-3-pro-image-preview', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @vertex_channel_name AND ch.`base_url` = @vertex_base_url
WHERE @vertex_api_key IS NOT NULL AND um.`model_name` = 'gemini-3-pro-image-preview';

SET @vertex_api_key = NULL;
SET @vertex_channel_name = NULL;
SET @vertex_base_url = NULL;

-- 可选：ChatGPT Image 兼容图片渠道与模型映射
-- 将 @chatgpt_image_api_key 从 NULL 改成真实密钥后再执行 init.sql，可自动创建渠道与映射。
SET @chatgpt_image_api_key = NULL;
SET @chatgpt_image_channel_name = 'ChatGPT Image Compatible';
SET @chatgpt_image_base_url = 'http://43.156.153.12:3000';

INSERT INTO `channel` (
    `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
    `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
    @chatgpt_image_channel_name, @chatgpt_image_base_url, @chatgpt_image_api_key, 'openai', 'openai-image-compatible', 'authorization',
    10, 1, 0, 1, 100, 0, 'OpenAI 兼容图片生成渠道，固定上游模型 gpt-image-2'
FROM DUAL
WHERE @chatgpt_image_api_key IS NOT NULL;

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, 'gpt-image-2', 1
FROM `unified_model` um
JOIN `channel` ch ON ch.`name` = @chatgpt_image_channel_name AND ch.`base_url` = @chatgpt_image_base_url
WHERE @chatgpt_image_api_key IS NOT NULL AND um.`model_name` = 'gpt-image-2';

SET @chatgpt_image_api_key = NULL;
SET @chatgpt_image_channel_name = NULL;
SET @chatgpt_image_base_url = NULL;

-- 可选：Grok 文本渠道与模型映射
-- 将 @grok_api_key 从 NULL 改成真实密钥后再执行 init.sql，可自动创建 Grok OpenAI / Anthropic 双渠道。
SET @grok_api_key = NULL;
SET @grok_base_url = 'http://167.88.186.145:8000/v1';
SET @grok_openai_channel_name = 'Grok OpenAI';
SET @grok_anthropic_channel_name = 'Grok Anthropic';

INSERT INTO `channel` (
    `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
    `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
    @grok_openai_channel_name, @grok_base_url, @grok_api_key, 'openai', 'default', 'authorization',
    6, 1, 0, 1, 100, 0, 'Grok 文本渠道（OpenAI Chat / Responses）'
FROM DUAL
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel`
    WHERE `name` = @grok_openai_channel_name AND `base_url` = @grok_base_url
  );

INSERT INTO `channel` (
    `name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`,
    `priority`, `enabled`, `health_check_enabled`, `is_healthy`, `health_score`, `failure_count`, `description`
)
SELECT
    @grok_anthropic_channel_name, @grok_base_url, @grok_api_key, 'anthropic', 'default', 'authorization',
    6, 1, 0, 1, 100, 0, 'Grok 文本渠道（Anthropic Messages）'
FROM DUAL
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel`
    WHERE `name` = @grok_anthropic_channel_name AND `base_url` = @grok_base_url
  );

INSERT INTO `model_channel_mapping` (`unified_model_id`, `channel_id`, `actual_model_name`, `enabled`)
SELECT um.id, ch.id, grok.model_name, 1
FROM (
    SELECT 'grok-4.20-0309-non-reasoning' AS model_name
    UNION ALL SELECT 'grok-4.20-0309'
    UNION ALL SELECT 'grok-4.20-0309-reasoning'
    UNION ALL SELECT 'grok-4.20-fast'
    UNION ALL SELECT 'grok-4.20-auto'
    UNION ALL SELECT 'grok-4.20-expert'
) grok
JOIN `unified_model` um ON um.`model_name` = grok.`model_name`
JOIN `channel` ch
  ON ch.`base_url` = @grok_base_url
 AND ch.`name` IN (@grok_openai_channel_name, @grok_anthropic_channel_name)
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `model_channel_mapping` m
    WHERE m.`unified_model_id` = um.id AND m.`channel_id` = ch.id
  );

SET @grok_api_key = NULL;
SET @grok_base_url = NULL;
SET @grok_openai_channel_name = NULL;
SET @grok_anthropic_channel_name = NULL;

-- 预置系统配置
INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
('health_check_interval', '300', 'number', '健康检查间隔(秒)'),
('circuit_breaker_threshold', '5', 'number', '熔断器触发阈值(连续失败次数)'),
('circuit_breaker_recovery', '600', 'number', '熔断恢复时间(秒)'),
('health_check_test_message', '你好', 'string', '健康检查测试消息'),
('request_timeout', '30', 'number', '请求超时时间(秒)'),
('max_retry_count', '3', 'number', '最大重试次数'),
('api_base_url', 'https://your-domain.com', 'string', 'API基础地址，用于快速开始页面展示给用户的接入地址'),
('request_body_cache_enabled', 'false', 'boolean', '是否启用请求体分段缓存分析'),
('request_body_cache_user_visible', 'false', 'boolean', '用户端是否显示缓存读取/创建信息'),
('request_body_cache_ttl_seconds', '1800', 'number', '请求体缓存 TTL（秒）'),
('request_body_cache_min_chars', '256', 'number', '最小缓存片段字符数阈值'),
('request_body_cache_formats', 'anthropic_messages,openai_chat,responses', 'string', '启用请求体缓存分析的请求格式'),
('anthropic_prompt_cache_enabled', 'false', 'boolean', '是否启用 Anthropic Prompt Cache'),
('anthropic_prompt_cache_history_enabled', 'true', 'boolean', '是否启用 Anthropic Prompt Cache 历史自动缓存'),
('anthropic_prompt_cache_static_ttl', '5m', 'string', 'Anthropic Prompt Cache 静态前缀 TTL（5m/1h）'),
('anthropic_prompt_cache_history_ttl', '5m', 'string', 'Anthropic Prompt Cache 历史前缀 TTL（5m/1h）'),
('anthropic_prompt_cache_beta_header', 'extended-cache-ttl-2025-04-11', 'string', 'Anthropic Prompt Cache 1h TTL beta header'),
('anthropic_prompt_cache_user_visible', 'false', 'boolean', '用户端是否显示 Anthropic Prompt Cache 读写详情'),
('anthropic_prompt_cache_billing_mode', 'logical', 'string', 'Anthropic Prompt Cache 计费口径：logical 或 actual_upstream'),
('conversation_state_compaction_enabled', 'false', 'boolean', '是否启用会话状态压缩'),
('conversation_state_compaction_stage', 'shadow', 'string', '会话状态压缩阶段：off/shadow/non_stream_active/stream_shadow/stream_active'),
('conversation_state_compaction_mode', 'safe_history', 'string', '会话状态压缩模式：off/safe_history/stateful_preferred'),
('conversation_state_compaction_recent_turns', '6', 'number', '会话压缩时保留的最近精确 turn 数'),
('conversation_state_compaction_trigger_tokens', '12000', 'number', '触发会话历史压缩的估算 token 阈值'),
('conversation_state_compaction_summary_max_tokens', '1500', 'number', '会话检查点摘要最大估算 token'),
('conversation_state_session_ttl_seconds', '86400', 'number', '会话状态 TTL（秒）'),
('conversation_state_match_window', '20', 'number', '会话匹配时最多回看最近多少个候选会话'),
('conversation_state_match_tail_tolerance_messages', '2', 'number', '会话匹配时允许尾部改写/重排的最大消息数'),
('conversation_state_match_min_shared_prefix', '8', 'number', '会话匹配时判定尾部改写所需的最小公共前缀消息数'),
('conversation_state_failure_cooldown_seconds', '600', 'number', '压缩失败后的会话冷却时间（秒）'),
('conversation_state_user_visible', 'false', 'boolean', '用户端是否显示会话压缩收益'),
('conversation_state_async_checkpoint_enabled', 'true', 'boolean', '是否启用异步会话检查点构建'),
('conversation_state_tool_compaction_enabled', 'false', 'boolean', '是否启用实验性的 tools/system 压缩');
