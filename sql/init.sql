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
    `role` VARCHAR(16) NOT NULL DEFAULT 'user',
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID，NULL=平台直营',
    `created_by_user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '创建者用户ID',
    `source_domain` VARCHAR(255) DEFAULT NULL COMMENT '注册来源域名',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '1=正常, 0=禁用',
    `cache_enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用缓存（1=启用，0=禁用）',
    `cache_hit_count` BIGINT NOT NULL DEFAULT 0 COMMENT '缓存命中次数',
    `cache_saved_tokens` BIGINT NOT NULL DEFAULT 0 COMMENT '累计节省 Tokens',
    `cache_billing_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '缓存计费开关（1=按缓存后计费，0=按原始计费）',
    `avatar` VARCHAR(512) DEFAULT NULL,
    `last_login_at` DATETIME DEFAULT NULL,
    `last_login_ip` VARCHAR(45) DEFAULT NULL,
    `subscription_type` VARCHAR(16) NOT NULL DEFAULT 'balance' COMMENT 'balance=按量计费, unlimited/quota=套餐缓存态',
    `subscription_expires_at` DATETIME DEFAULT NULL COMMENT '套餐过期时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_email` (`email`),
    KEY `idx_agent_id` (`agent_id`),
    KEY `idx_role` (`role`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- ============================================================
-- 2. agent - 代理站点表
-- ============================================================
CREATE TABLE `agent` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_code` VARCHAR(64) NOT NULL,
    `agent_name` VARCHAR(128) NOT NULL,
    `owner_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `status` VARCHAR(16) NOT NULL DEFAULT 'active',
    `frontend_domain` VARCHAR(255) DEFAULT NULL,
    `api_domain` VARCHAR(255) DEFAULT NULL,
    `site_title` VARCHAR(128) DEFAULT NULL,
    `site_subtitle` VARCHAR(255) DEFAULT NULL,
    `announcement_title` VARCHAR(128) DEFAULT NULL,
    `announcement_content` TEXT DEFAULT NULL,
    `support_wechat` VARCHAR(128) DEFAULT NULL,
    `support_qq` VARCHAR(64) DEFAULT NULL,
    `quickstart_api_base_url` VARCHAR(512) DEFAULT NULL,
    `allow_self_register` TINYINT NOT NULL DEFAULT 1,
    `theme_config_json` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_code` (`agent_code`),
    UNIQUE KEY `uk_agent_frontend_domain` (`frontend_domain`),
    UNIQUE KEY `uk_agent_api_domain` (`api_domain`),
    KEY `idx_agent_status` (`status`),
    KEY `idx_agent_owner_user_id` (`owner_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理站点表';

-- ============================================================
-- 3. user_api_key - 用户 API Key 表
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
    `total_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '总消费(美元)',
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
-- 4. agent_balance - 代理余额池
-- ============================================================
CREATE TABLE `agent_balance` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `balance` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_recharged` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_allocated` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_reclaimed` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_balance_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理余额池';

-- ============================================================
-- 5. agent_balance_record - 代理余额流水
-- ============================================================
CREATE TABLE `agent_balance_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `target_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `related_code_id` BIGINT UNSIGNED DEFAULT NULL,
    `action_type` VARCHAR(32) NOT NULL,
    `change_amount` DECIMAL(12, 6) NOT NULL COMMENT '正数流入，负数流出',
    `balance_before` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `balance_after` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_balance_record_agent_id` (`agent_id`),
    KEY `idx_agent_balance_record_target_user_id` (`target_user_id`),
    KEY `idx_agent_balance_record_action_type` (`action_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理余额流水';

-- ============================================================
-- 6. agent_image_balance - 代理图片积分池
-- ============================================================
CREATE TABLE `agent_image_balance` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `balance` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `total_recharged` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `total_allocated` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `total_reclaimed` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_image_balance_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理图片积分池';

-- ============================================================
-- 7. agent_image_credit_record - 代理图片积分流水
-- ============================================================
CREATE TABLE `agent_image_credit_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `target_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `action_type` VARCHAR(32) NOT NULL,
    `change_amount` DECIMAL(12, 3) NOT NULL COMMENT '正数流入，负数流出',
    `balance_before` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `balance_after` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_image_credit_record_agent_id` (`agent_id`),
    KEY `idx_agent_image_credit_record_target_user_id` (`target_user_id`),
    KEY `idx_agent_image_credit_record_action_type` (`action_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理图片积分流水';

-- ============================================================
-- 8. agent_subscription_inventory - 代理套餐库存
-- ============================================================
CREATE TABLE `agent_subscription_inventory` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `plan_id` BIGINT UNSIGNED NOT NULL,
    `total_granted` INT NOT NULL DEFAULT 0,
    `total_used` INT NOT NULL DEFAULT 0,
    `remaining_count` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_subscription_inventory` (`agent_id`, `plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理套餐库存';

-- ============================================================
-- 9. agent_subscription_inventory_record - 代理套餐库存流水
-- ============================================================
CREATE TABLE `agent_subscription_inventory_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `plan_id` BIGINT UNSIGNED NOT NULL,
    `target_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `action_type` VARCHAR(32) NOT NULL,
    `change_count` INT NOT NULL COMMENT '正数增加，负数扣减',
    `remaining_before` INT NOT NULL DEFAULT 0,
    `remaining_after` INT NOT NULL DEFAULT 0,
    `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_subscription_inventory_record_agent_id` (`agent_id`),
    KEY `idx_agent_subscription_inventory_record_plan_id` (`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理套餐库存流水';

-- ============================================================
-- 10. agent_redemption_amount_rule - 代理兑换码固定面额规则
-- ============================================================
CREATE TABLE `agent_redemption_amount_rule` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT 'NULL=全局规则',
    `amount` DECIMAL(12, 6) NOT NULL,
    `status` VARCHAR(16) NOT NULL DEFAULT 'active',
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_redemption_rule_agent_id` (`agent_id`),
    KEY `idx_agent_redemption_rule_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理兑换码固定面额规则';

-- ============================================================
-- 11. channel - 渠道（模型提供商）表
-- ============================================================
CREATE TABLE `channel` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(128) NOT NULL,
    `base_url` VARCHAR(512) NOT NULL,
    `api_key` TEXT NOT NULL COMMENT '加密存储的API Key',
    `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai',
    `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default' COMMENT 'Provider subtype: default/google-official/google-vertex-image',
    `auth_header_type` VARCHAR(32) NOT NULL DEFAULT 'x-api-key' COMMENT 'Auth header type: x-api-key, anthropic-api-key, authorization, x-goog-api-key',
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
    `protocol_type` ENUM('openai', 'anthropic') NOT NULL DEFAULT 'openai',
    `max_tokens` INT DEFAULT NULL,
    `input_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万输入Token单价(美元)',
    `output_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万输出Token单价(美元)',
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
-- 6. cache_log - 缓存日志表
-- ============================================================
CREATE TABLE `cache_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `cache_key` VARCHAR(64) NOT NULL COMMENT 'Cache Key (SHA256)',
    `user_id` BIGINT UNSIGNED NOT NULL,
    `model` VARCHAR(100) NOT NULL,
    `prompt_tokens` INT NOT NULL,
    `completion_tokens` INT NOT NULL,
    `cache_status` ENUM('HIT', 'MISS', 'BYPASS') NOT NULL,
    `saved_tokens` INT DEFAULT 0,
    `saved_cost` DECIMAL(10, 6) DEFAULT 0.00,
    `ttl` INT NOT NULL COMMENT '缓存时长(秒)',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_cache_key` (`cache_key`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_cache_status` (`cache_status`),
    KEY `idx_user_created` (`user_id`, `created_at`),
    KEY `idx_user_status_created` (`user_id`, `cache_status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='缓存日志表';

-- ============================================================
-- 7. request_log - 请求日志表
-- ============================================================
CREATE TABLE `request_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `request_id` VARCHAR(36) NOT NULL COMMENT 'UUID',
    `user_id` BIGINT UNSIGNED DEFAULT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID',
    `user_api_key_id` BIGINT UNSIGNED DEFAULT NULL,
    `channel_id` BIGINT UNSIGNED DEFAULT NULL,
    `channel_name` VARCHAR(128) DEFAULT NULL,
    `requested_model` VARCHAR(128) DEFAULT NULL COMMENT '用户请求的模型名',
    `actual_model` VARCHAR(128) DEFAULT NULL COMMENT '实际发送的模型名',
    `protocol_type` ENUM('openai', 'anthropic') DEFAULT NULL,
    `request_type` VARCHAR(32) DEFAULT 'chat',
    `billing_type` VARCHAR(20) DEFAULT 'token',
    `is_stream` TINYINT DEFAULT 0,
    `input_tokens` INT DEFAULT 0,
    `output_tokens` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `raw_input_tokens` INT DEFAULT 0,
    `raw_output_tokens` INT DEFAULT 0,
    `raw_total_tokens` INT DEFAULT 0,
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
    KEY `idx_agent_id` (`agent_id`),
    KEY `idx_channel_id` (`channel_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_status` (`status`),
    KEY `idx_requested_model` (`requested_model`),
    KEY `idx_conversation_session_id` (`conversation_session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求日志表';

-- ============================================================
-- 8. request_cache_summary - 请求体缓存摘要表
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
-- 9. system_config - 系统配置表
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
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `username` VARCHAR(64) DEFAULT NULL,
    `action` VARCHAR(64) NOT NULL,
    `target_type` VARCHAR(64) DEFAULT NULL,
    `target_id` BIGINT UNSIGNED DEFAULT NULL,
    `description` TEXT DEFAULT NULL,
    `ip_address` VARCHAR(45) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_operation_agent_id` (`agent_id`),
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
-- 12. user_image_balance - 用户图片积分余额表
-- ============================================================
CREATE TABLE `user_image_balance` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `balance` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '图片积分余额',
    `total_recharged` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '总充值',
    `total_consumed` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '总消费',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_image_balance_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户图片积分余额表';

-- ============================================================
-- 13. consumption_record - 消费记录表
-- ============================================================
CREATE TABLE `consumption_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID',
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
    KEY `idx_consumption_agent_id` (`agent_id`),
    KEY `idx_request_id` (`request_id`),
    KEY `idx_billing_mode` (`billing_mode`),
    KEY `idx_subscription_id` (`subscription_id`),
    KEY `idx_subscription_cycle_id` (`subscription_cycle_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消费记录表';

-- ============================================================
-- 14. image_credit_record - 图片积分流水表
-- ============================================================
CREATE TABLE `image_credit_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID',
    `request_id` VARCHAR(36) DEFAULT NULL,
    `model_name` VARCHAR(128) DEFAULT NULL,
    `change_amount` DECIMAL(12, 3) NOT NULL COMMENT '正数充值，负数扣减',
    `balance_before` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `balance_after` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `multiplier` DECIMAL(12, 3) NOT NULL DEFAULT 1,
    `image_size` VARCHAR(16) DEFAULT NULL,
    `action_type` VARCHAR(20) NOT NULL DEFAULT 'request' COMMENT 'request/recharge/deduct',
    `operator_id` BIGINT UNSIGNED DEFAULT NULL,
    `remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_image_credit_record_user_id` (`user_id`),
    KEY `idx_image_credit_record_agent_id` (`agent_id`),
    KEY `idx_image_credit_record_request_id` (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图片积分流水表';

-- ============================================================
-- 14.1 subscription_plan - 套餐模板表
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
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID',
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
    KEY `idx_user_subscription_agent_id` (`agent_id`),
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
-- 15. cache_log - 缓存日志表
-- ============================================================
CREATE TABLE `cache_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `cache_key` VARCHAR(64) NOT NULL COMMENT 'Cache Key (SHA256)',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `model` VARCHAR(100) NOT NULL COMMENT '模型名称',
    `prompt_tokens` INT NOT NULL COMMENT 'Prompt Tokens',
    `completion_tokens` INT NOT NULL COMMENT 'Completion Tokens',
    `cache_status` ENUM('HIT', 'MISS', 'BYPASS') NOT NULL COMMENT '缓存状态',
    `saved_tokens` INT DEFAULT 0 COMMENT '节省的 Tokens',
    `saved_cost` DECIMAL(10, 6) DEFAULT 0.00 COMMENT '节省的费用',
    `ttl` INT NOT NULL COMMENT '缓存时长（秒）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_cache_key` (`cache_key`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_cache_status` (`cache_status`),
    KEY `idx_user_created` (`user_id`, `created_at`),
    KEY `idx_user_status_created` (`user_id`, `cache_status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='缓存日志表';

-- ============================================================
-- 16. redemption_code - 兑换码表
-- ============================================================
CREATE TABLE `redemption_code` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `code` VARCHAR(32) NOT NULL COMMENT '兑换码',
    `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID，NULL=平台兑换码',
    `amount` DECIMAL(12, 6) NOT NULL COMMENT '兑换金额(美元)',
    `amount_rule_snapshot` VARCHAR(64) DEFAULT NULL COMMENT '面额规则快照',
    `code_scope` VARCHAR(16) NOT NULL DEFAULT 'platform' COMMENT 'platform/agent',
    `status` ENUM('unused', 'used', 'expired') NOT NULL DEFAULT 'unused' COMMENT '状态',
    `created_by` BIGINT UNSIGNED NOT NULL COMMENT '创建者(管理员ID)',
    `used_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '使用者(用户ID)',
    `used_at` DATETIME DEFAULT NULL COMMENT '使用时间',
    `expires_at` DATETIME DEFAULT NULL COMMENT '过期时间',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_redemption_agent_id` (`agent_id`),
    KEY `idx_status` (`status`),
    KEY `idx_created_by` (`created_by`),
    KEY `idx_used_by` (`used_by`),
    KEY `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='兑换码表';

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

-- 预置系统配置
INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
('health_check_interval', '300', 'number', '健康检查间隔(秒)'),
('circuit_breaker_threshold', '5', 'number', '熔断器触发阈值(连续失败次数)'),
('circuit_breaker_recovery', '600', 'number', '熔断恢复时间(秒)'),
('health_check_test_message', '你好', 'string', '健康检查测试消息'),
('request_timeout', '30', 'number', '请求超时时间(秒)'),
('max_retry_count', '3', 'number', '最大重试次数'),
('api_base_url', 'https://your-domain.com', 'string', 'API基础地址，用于快速开始页面展示给用户的接入地址'),
('platform_site_name', '小乐AI', 'string', '平台直营站点名称'),
('platform_site_subtitle', '一站式 AI 模型调用服务，让智能触手可及', 'string', '平台直营站点副标题'),
('platform_announcement_title', '平台公告', 'string', '平台直营站点公告标题'),
('platform_announcement_content', '尊敬的用户，欢迎使用 AI 模型中转平台！\n\n支持Claude和GPT及Gemini全系列模型!\n\n新用户注册，立即赠送 $5 体验额度', 'string', '平台直营站点公告内容'),
('platform_support_wechat', 'Q-Free-M', 'string', '平台直营站点微信联系方式'),
('platform_support_qq', '2222006406', 'string', '平台直营站点QQ联系方式'),
('platform_allow_register', 'true', 'boolean', '平台直营站点是否允许自助注册'),
('max_context_tokens', '200000', 'number', '最大上下文Token数量限制'),
('max_message_length', '500000', 'number', '单条消息最大字符数限制'),
('price_multiplier', '1.0', 'number', '价格倍率（1.0=原价，2.0=2倍价格）'),
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

-- ============================================================
-- 预置渠道配置
-- ============================================================
-- 注意: 以下 API Key 为示例数据，部署时请替换为实际的 API Key
INSERT INTO `channel` (`id`, `name`, `base_url`, `api_key`, `protocol_type`, `priority`, `enabled`, `description`) VALUES
(4, 'api.kxaug.xyz-Claude', 'https://api.kxaug.xyz/v1', 'sk-YOUR-API-KEY-HERE', 'openai', 2, 1, '主力渠道 - Claude模型'),
(5, 'api.kxaug.xyz-GPT', 'https://api.kxaug.xyz/v1', 'sk-YOUR-API-KEY-HERE', 'openai', 2, 1, '主力渠道 - GPT/Codex模型'),
(6, 'pay.kxaug.xyz-Claude', 'https://pay.kxaug.xyz/v1', 'sk-YOUR-API-KEY-HERE', 'openai', 3, 1, '备用渠道 - Claude模型'),
(7, 'pay.kxaug.xyz-GPT', 'https://pay.kxaug.xyz/v1', 'sk-YOUR-API-KEY-HERE', 'openai', 3, 1, '备用渠道 - GPT/Codex模型'),
(8, 'mmaqq.top', 'https://mmaqq.top/v1', 'sk-YOUR-API-KEY-HERE', 'openai', 4, 1, '保底渠道 - 全模型'),
(9, '43.156.153.12-Claude', 'http://43.156.153.12:8080/v1', 'sk-qeBTyXmKefPLsYPBbX9Xk1hmW94EemEp', 'anthropic', 1, 1, '自建渠道，支持 claude-haiku-4.5, claude-sonnet-4.5, claude-sonnet-4'),
(10, '43.156.153.12-codex', 'http://43.156.153.12:8317/v1', 'sk-YOUR-API-KEY-HERE', 'openai', 1, 1, 'GPT-5 Codex 系列模型渠道'),
(11, '43.156.153.12-codex转claude', 'http://43.156.153.12:8317/v1', 'sk-YOUR-API-KEY-HERE', 'anthropic', 1, 1, 'Anthropic 协议入口，内部转发到 Codex Responses / gpt-5.4，供 Claude Code 使用');

-- ============================================================
-- 预置统一模型配置
-- ============================================================
INSERT INTO `unified_model` (`id`, `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`, `input_price_per_million`, `output_price_per_million`, `enabled`, `description`) VALUES
(3, 'claude-haiku-4-5-20251001', 'Claude Haiku 4.5', 'chat', 'openai', 8192, 3.000000, 15.000000, 0, 'Claude Haiku 4.5 (2025-10-01)'),
(4, 'claude-sonnet-4-5', 'Claude Sonnet 4.5', 'chat', 'openai', 8192, 4.000000, 20.000000, 1, 'Claude Sonnet 4.5 (2025-09-29)'),
(5, 'claude-haiku-4-5', 'Claude Haiku 4.5', 'chat', 'openai', 8192, 3.000000, 15.000000, 1, 'Claude Haiku 4.5 最新版'),
(6, 'claude-sonnet-4-6', 'Claude Sonnet 4.6', 'chat', 'openai', 8192, 4.000000, 20.000000, 0, 'Claude Sonnet 4.6'),
(7, 'gpt-5.1', 'GPT-5.1', 'chat', 'openai', 32768, 2.000000, 8.000000, 1, 'OpenAI GPT-5.1'),
(8, 'gpt-5.2', 'GPT-5.2', 'chat', 'openai', 32768, 3.000000, 12.000000, 1, 'OpenAI GPT-5.2'),
(9, 'gpt-5.1-codex', 'GPT-5.1 Codex', 'chat', 'openai', 32768, 3.000000, 12.000000, 1, 'OpenAI GPT-5.1 Codex'),
(10, 'gpt-5.2-codex', 'GPT-5.2 Codex', 'chat', 'openai', 32768, 5.000000, 20.000000, 1, 'OpenAI GPT-5.2 Codex'),
(11, 'gpt-5.3-codex', 'GPT-5.3 Codex', 'chat', 'openai', 32768, 5.000000, 20.000000, 1, 'OpenAI GPT-5.3 Codex'),
(12, 'gpt-5.4', 'GPT-5.4', 'chat', 'openai', 32768, 5.000000, 20.000000, 1, 'OpenAI GPT-5.4'),
(13, 'gemini-2.5-flash', 'Gemini 2.5 Flash', 'chat', 'openai', 65536, 0.150000, 0.600000, 1, 'Google Gemini 2.5 Flash'),
(28, 'gpt-5.1-codex-mini', 'GPT-5.1 Codex Mini', 'chat', 'openai', 128000, 0.500000, 1.500000, 1, 'GPT-5.1 Codex Mini - 轻量级代码模型'),
(29, 'gpt-5', 'GPT-5', 'chat', 'openai', 128000, 2.500000, 7.500000, 1, 'GPT-5 - 基础模型'),
(30, 'gpt-5.1-codex-max', 'GPT-5.1 Codex Max', 'chat', 'openai', 128000, 4.000000, 12.000000, 1, 'GPT-5.1 Codex Max - 高性能代码模型'),
(31, 'gpt-5.4-mini', 'GPT-5.4 Mini', 'chat', 'openai', 128000, 0.800000, 2.400000, 1, 'GPT-5.4 Mini - 轻量级模型'),
(32, 'gpt-5-codex', 'GPT-5 Codex', 'chat', 'openai', 128000, 3.000000, 9.000000, 1, 'GPT-5 Codex - 代码专用模型'),
(33, 'gpt-5-codex-mini', 'GPT-5 Codex Mini', 'chat', 'openai', 128000, 0.600000, 1.800000, 1, 'GPT-5 Codex Mini - 轻量级代码模型'),
(34, 'claude-opus-4-6', 'Claude Opus 4.6', 'chat', 'anthropic', 32768, 5.000000, 20.000000, 1, 'Claude Opus 4.6 alias exposed via Anthropic and routed to GPT-5.4 high reasoning on Codex Responses'),
(26, 'claude-sonnet-4-5-thinking', 'Claude Sonnet 4.5 Thinking', 'chat', 'openai', 8192, 3.000000, 15.000000, 1, 'Claude Sonnet 4.5 with extended thinking capability'),
(27, 'claude-haiku-4-5-thinking', 'Claude Haiku 4.5 Thinking', 'chat', 'openai', 8192, 0.800000, 4.000000, 1, 'Claude Haiku 4.5 with extended thinking capability');

INSERT INTO `unified_model` (`id`, `model_name`, `display_name`, `model_type`, `protocol_type`, `max_tokens`, `input_price_per_million`, `output_price_per_million`, `enabled`, `description`) VALUES
(35, 'grok-4.20-0309-non-reasoning', 'Grok 4.20 0309 Non-Reasoning', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 0309 非推理版（官方定价 2/6）'),
(36, 'grok-4.20-0309', 'Grok 4.20 0309', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 0309（按 4.20 主档推断定价 2/6）'),
(37, 'grok-4.20-0309-reasoning', 'Grok 4.20 0309 Reasoning', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 0309 推理版（官方定价 2/6）'),
(38, 'grok-4.20-fast', 'Grok 4.20 Fast', 'chat', 'openai', 128000, 0.200000, 0.500000, 1, 'xAI Grok 4.20 Fast（参照 4.1 fast 档推断定价 0.2/0.5）'),
(39, 'grok-4.20-auto', 'Grok 4.20 Auto', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 Auto（按 4.20 主档推断定价 2/6）'),
(40, 'grok-4.20-expert', 'Grok 4.20 Expert', 'chat', 'openai', 128000, 2.000000, 6.000000, 1, 'xAI Grok 4.20 Expert（按 4.20 高阶档推断定价 2/6）')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `protocol_type` = VALUES(`protocol_type`),
    `max_tokens` = VALUES(`max_tokens`),
    `input_price_per_million` = VALUES(`input_price_per_million`),
    `output_price_per_million` = VALUES(`output_price_per_million`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

-- ============================================================
-- 预置模型-渠道映射配置
-- ============================================================
INSERT INTO `model_channel_mapping` (`id`, `unified_model_id`, `channel_id`, `actual_model_name`, `enabled`) VALUES
-- Claude Haiku 4.5 (旧版本) 映射
(2, 3, 4, 'claude-haiku-4-5-20251001', 1),
(3, 3, 6, 'claude-haiku-4-5-20251001', 1),
(4, 3, 8, 'claude-haiku-4-5-20251001', 1),
-- Claude Sonnet 4.5 映射
(5, 4, 4, 'claude-sonnet-4-5-20250929', 1),
(6, 4, 6, 'claude-sonnet-4-5-20250929', 1),
(21, 4, 9, 'claude-sonnet-4.5', 1),
(23, 4, 8, 'claude-sonnet-4-5', 1),
-- Claude Haiku 4.5 (最新版) 映射
(7, 5, 8, 'claude-haiku-4-5', 1),
(18, 5, 4, 'claude-haiku-4-5-20251001', 1),
(19, 5, 6, 'claude-haiku-4-5-20251001', 1),
(20, 5, 9, 'claude-haiku-4.5', 1),
-- Claude Sonnet 4.6 映射
(8, 6, 8, 'claude-sonnet-4-6', 1),
(22, 6, 9, 'claude-sonnet-4', 1),
-- GPT 5.1 映射
(9, 7, 5, 'gpt-5.1', 1),
-- GPT 5.2 映射
(10, 8, 5, 'gpt-5.2', 1),
(11, 8, 7, 'gpt-5.2', 1),
-- GPT 5.1 Codex 映射
(12, 9, 5, 'gpt-5.1-codex', 1),
-- GPT 5.2 Codex 映射
(13, 10, 5, 'gpt-5.2-codex', 1),
(14, 10, 7, 'gpt-5.2-codex', 1),
-- GPT 5.3 Codex 映射
(15, 11, 7, 'gpt-5.3-codex', 1),
-- GPT 5.4 映射
(16, 12, 7, 'gpt-5.4', 1),
-- Gemini 2.5 Flash 映射
(17, 13, 8, 'gemini-2.5-flash', 1),
-- 43.156.153.12-codex 渠道映射（Responses API）
(53, 28, 10, 'responses:gpt-5.1-codex-mini', 1),
(54, 8, 10, 'responses:gpt-5.2', 1),
(55, 10, 10, 'responses:gpt-5.2-codex', 1),
(56, 11, 10, 'responses:gpt-5.3-codex', 1),
(57, 29, 10, 'responses:gpt-5', 1),
(58, 7, 10, 'responses:gpt-5.1', 1),
(59, 30, 10, 'responses:gpt-5.1-codex-max', 1),
(60, 12, 10, 'responses:gpt-5.4', 1),
(61, 31, 10, 'responses:gpt-5.4-mini', 1),
(62, 32, 10, 'responses:gpt-5-codex', 1),
(63, 33, 10, 'responses:gpt-5-codex-mini', 1),
(64, 9, 10, 'responses:gpt-5.1-codex', 1),
-- 43.156.153.12-codex转claude 渠道映射（Anthropic-facing / Responses-backed）
(65, 34, 11, 'responses:gpt-5.4', 1),
-- Claude Sonnet 4.5 Thinking 映射
(51, 26, 9, 'claude-sonnet-4-5-thinking', 1),
-- Claude Haiku 4.5 Thinking 映射
(52, 27, 9, 'claude-haiku-4-5-thinking', 1);

-- 可选：Grok 文本渠道与模型映射
SET @grok_api_key = NULL;
SET @grok_base_url = 'http://167.88.186.145:8000/v1';
SET @grok_openai_channel_name = 'Grok OpenAI';
SET @grok_anthropic_channel_name = 'Grok Anthropic';

INSERT INTO `channel` (`name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`, `priority`, `enabled`, `health_check_enabled`, `description`)
SELECT
    @grok_openai_channel_name,
    @grok_base_url,
    @grok_api_key,
    'openai',
    'default',
    'authorization',
    6,
    1,
    0,
    'Grok 文本渠道（OpenAI Chat / Responses）'
FROM DUAL
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel` WHERE `name` = @grok_openai_channel_name AND `base_url` = @grok_base_url
  );

INSERT INTO `channel` (`name`, `base_url`, `api_key`, `protocol_type`, `provider_variant`, `auth_header_type`, `priority`, `enabled`, `health_check_enabled`, `description`)
SELECT
    @grok_anthropic_channel_name,
    @grok_base_url,
    @grok_api_key,
    'anthropic',
    'default',
    'authorization',
    6,
    1,
    0,
    'Grok 文本渠道（Anthropic Messages）'
FROM DUAL
WHERE @grok_api_key IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM `channel` WHERE `name` = @grok_anthropic_channel_name AND `base_url` = @grok_base_url
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

-- ============================================================
-- 预置模型覆盖规则配置
-- ============================================================
INSERT INTO `model_override_rule` (`name`, `rule_type`, `source_pattern`, `target_unified_model_id`, `enabled`, `priority`) VALUES
('claude-sonnet-4.5 → sonnet-4-5', 'redirect_specific', 'claude-sonnet-4.5', 4, 1, 1),
('haiku-20251001 → haiku-4-5', 'redirect_specific', 'claude-haiku-4-5-20251001', 5, 1, 2),
('sonnet-4-5-20250929 → sonnet-4-5', 'redirect_specific', 'claude-sonnet-4-5-20250929', 4, 1, 3),
('sonnet-4-6 → sonnet-4-5', 'redirect_specific', 'claude-sonnet-4-6', 4, 1, 4),
('sonnet-4 → sonnet-4-5', 'redirect_specific', 'claude-sonnet-4', 4, 1, 5),
('sonnet-4-20250514 → sonnet-4-5', 'redirect_specific', 'claude-sonnet-4-20250514', 4, 1, 6),
('claude-3.5-sonnet → sonnet-4-5', 'redirect_specific', 'claude-3.5-sonnet', 4, 1, 7),
('claude-3-5-sonnet → sonnet-4-5', 'redirect_specific', 'claude-3-5-sonnet', 4, 1, 8),
('claude-3-5-sonnet-* → sonnet-4-5', 'redirect_specific', 'claude-3-5-sonnet-*', 4, 1, 9),
('claude-3-5-haiku → haiku-4-5', 'redirect_specific', 'claude-3-5-haiku', 5, 1, 10),
('claude-3-5-haiku-* → haiku-4-5', 'redirect_specific', 'claude-3-5-haiku-*', 5, 1, 11),
('claude-3.5-haiku → haiku-4-5', 'redirect_specific', 'claude-3.5-haiku', 5, 1, 12);
