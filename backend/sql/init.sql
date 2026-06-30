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
    `token_version` BIGINT NOT NULL DEFAULT 0 COMMENT '登录令牌版本，递增后旧JWT失效',
    `avatar` VARCHAR(512) DEFAULT NULL,
    `last_login_at` DATETIME DEFAULT NULL,
    `last_login_ip` VARCHAR(45) DEFAULT NULL,
    `redemption_reset_count` BIGINT NOT NULL DEFAULT 0 COMMENT '兑换码资格重置次数',
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
-- 2.1 agent_daily_limit - 代理每日授信额度配置
-- ============================================================
CREATE TABLE `agent_daily_limit` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `resource_type` VARCHAR(32) NOT NULL COMMENT 'balance/image_credit/subscription',
    `plan_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '套餐资源对应 plan_id',
    `plan_id_key` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'NULL plan_id 唯一键占位',
    `daily_limit` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '每日授信额度',
    `status` VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_daily_limit_resource` (`agent_id`, `resource_type`, `plan_id_key`),
    KEY `idx_agent_daily_limit_agent` (`agent_id`),
    KEY `idx_agent_daily_limit_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理每日授信额度配置';

-- ============================================================
-- 2.2 agent_daily_limit_usage - 代理每日授信额度使用量
-- ============================================================
CREATE TABLE `agent_daily_limit_usage` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `usage_date` DATE NOT NULL COMMENT '北京时间业务日期',
    `resource_type` VARCHAR(32) NOT NULL COMMENT 'balance/image_credit/subscription',
    `plan_id` BIGINT UNSIGNED DEFAULT NULL,
    `plan_id_key` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `used_amount` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '当日已使用授信额度',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_daily_usage_resource` (`agent_id`, `usage_date`, `resource_type`, `plan_id_key`),
    KEY `idx_agent_daily_usage_date` (`usage_date`),
    KEY `idx_agent_daily_usage_agent` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理每日授信额度使用量';

-- ============================================================
-- 2.3 agent_settlement_record - 代理授信销售待结算记录
-- ============================================================
CREATE TABLE `agent_settlement_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `target_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `business_date` DATE NOT NULL COMMENT '北京时间业务日期',
    `resource_type` VARCHAR(32) NOT NULL COMMENT 'balance/image_credit/subscription/redemption_code',
    `plan_id` BIGINT UNSIGNED DEFAULT NULL,
    `plan_code_snapshot` VARCHAR(64) DEFAULT NULL,
    `plan_name_snapshot` VARCHAR(128) DEFAULT NULL,
    `plan_kind_snapshot` VARCHAR(32) DEFAULT NULL,
    `duration_days_snapshot` INT DEFAULT NULL,
    `quota_metric_snapshot` VARCHAR(32) DEFAULT NULL,
    `quota_value_snapshot` DECIMAL(20, 6) DEFAULT NULL,
    `quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '销售数量/金额',
    `settled_quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0 COMMENT '已结算数量/金额',
    `unit_amount` DECIMAL(20, 6) DEFAULT NULL COMMENT '预留结算单价',
    `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/partial/settled/cancelled',
    `source_action` VARCHAR(64) NOT NULL,
    `related_subscription_id` BIGINT UNSIGNED DEFAULT NULL,
    `related_balance_record_id` BIGINT UNSIGNED DEFAULT NULL,
    `related_image_record_id` BIGINT UNSIGNED DEFAULT NULL,
    `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `remark` VARCHAR(255) DEFAULT NULL,
    `settled_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_settlement_agent_date` (`agent_id`, `business_date`),
    KEY `idx_agent_settlement_status` (`status`),
    KEY `idx_agent_settlement_resource` (`resource_type`, `plan_id`),
    KEY `idx_agent_settlement_user` (`target_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理授信销售待结算记录';

-- ============================================================
-- 2.3.1 agent_subscription_sale_record - 代理套餐销售返现核销记录
-- ============================================================
CREATE TABLE `agent_subscription_sale_record` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `order_id` BIGINT UNSIGNED NOT NULL,
    `order_no` VARCHAR(64) NOT NULL,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `subscription_id` BIGINT UNSIGNED DEFAULT NULL,
    `plan_id` BIGINT UNSIGNED DEFAULT NULL,
    `plan_code_snapshot` VARCHAR(64) DEFAULT NULL,
    `plan_name_snapshot` VARCHAR(128) NOT NULL,
    `plan_kind_snapshot` VARCHAR(32) DEFAULT NULL,
    `duration_days_snapshot` INT DEFAULT NULL,
    `sale_price_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `agent_cost_price_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `agent_rebate_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `payment_channel` VARCHAR(32) NOT NULL,
    `payment_status` VARCHAR(16) NOT NULL DEFAULT 'paid',
    `rebate_status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/settled/void',
    `settled_at` DATETIME DEFAULT NULL,
    `settled_by` BIGINT UNSIGNED DEFAULT NULL,
    `settlement_remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_subscription_sale_order` (`order_no`),
    KEY `idx_agent_subscription_sale_agent_status` (`agent_id`, `rebate_status`),
    KEY `idx_agent_subscription_sale_created` (`created_at`),
    KEY `idx_agent_subscription_sale_plan` (`plan_id`),
    KEY `idx_agent_subscription_sale_user` (`user_id`),
    KEY `idx_agent_subscription_sale_subscription` (`subscription_id`),
    KEY `idx_agent_subscription_sale_settled_by` (`settled_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理套餐销售返现核销记录表';

-- ============================================================
-- 2.4 agent_settlement_batch - 代理结算批次
-- ============================================================
CREATE TABLE `agent_settlement_batch` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `agent_id` BIGINT UNSIGNED NOT NULL,
    `resource_type` VARCHAR(32) NOT NULL,
    `plan_id` BIGINT UNSIGNED DEFAULT NULL,
    `business_start_date` DATE DEFAULT NULL,
    `business_end_date` DATE DEFAULT NULL,
    `settled_quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0,
    `operator_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_settlement_batch_agent` (`agent_id`),
    KEY `idx_agent_settlement_batch_resource` (`resource_type`, `plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理结算批次';

-- ============================================================
-- 2.5 agent_settlement_batch_item - 代理结算批次明细
-- ============================================================
CREATE TABLE `agent_settlement_batch_item` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `settlement_record_id` BIGINT UNSIGNED NOT NULL,
    `settled_quantity` DECIMAL(20, 6) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_agent_settlement_batch_item_batch` (`batch_id`),
    KEY `idx_agent_settlement_batch_item_record` (`settlement_record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理结算批次明细';

-- ============================================================
-- 3. channel - 渠道（模型提供商）表
-- ============================================================
CREATE TABLE `channel` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(128) NOT NULL,
    `base_url` VARCHAR(512) NOT NULL,
    `api_key` TEXT NOT NULL COMMENT '加密存储的API Key',
    `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai',
    `provider_variant` VARCHAR(32) NOT NULL DEFAULT 'default' COMMENT '渠道子类型: default/openai-image-compatible/openai-image-native-size/openai-image-modelinvoke/geek2api-image/cpa-grok-video/zz1cc-video/google-official/google-vertex-image',
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
    `model_type` ENUM('chat', 'embedding', 'image', 'video') NOT NULL DEFAULT 'chat',
    `model_series` VARCHAR(32) NOT NULL DEFAULT 'other' COMMENT '模型系列:gpt/claude/grok/gemini/other',
    `protocol_type` ENUM('openai', 'anthropic', 'google') NOT NULL DEFAULT 'openai',
    `max_tokens` INT DEFAULT NULL,
    `input_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万输入Token单价(美元)',
    `output_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万输出Token单价(美元)',
    `cache_creation_price_per_million` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '每百万缓存创建Token单价(美元)',
    `billing_type` VARCHAR(20) NOT NULL DEFAULT 'token' COMMENT 'token/request/image_credit/free',
    `request_price` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '按请求次数计费的单次请求价格(美元)',
    `image_credit_multiplier` DECIMAL(12, 3) NOT NULL DEFAULT 1 COMMENT '图片请求默认扣减倍率；视频模型表示每秒媒体积分单价',
    `long_context_billing_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '是否启用超过256k上下文2倍计费',
    `security_monitor_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '是否启用安全风控监控',
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `description` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_model_name` (`model_name`),
    KEY `idx_model_type` (`model_type`),
    KEY `idx_model_series` (`model_series`),
    KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统一模型定义表';

-- ============================================================
-- 4.1 model_price_adjustment_rule - 模型分类价格调控规则表
-- ============================================================
CREATE TABLE `model_price_adjustment_rule` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(128) NOT NULL,
    `model_series` VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'gpt/claude/grok/gemini/other/all',
    `model_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'chat/image/video/embedding/completion/all',
    `billing_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'token/request/image_credit/free/all',
    `multiplier` DECIMAL(12, 6) NOT NULL DEFAULT 1 COMMENT '价格调控倍率',
    `schedule_type` VARCHAR(20) NOT NULL DEFAULT 'always' COMMENT 'always/daily_time',
    `start_time` TIME DEFAULT NULL COMMENT '每日开始时间，北京时间',
    `end_time` TIME DEFAULT NULL COMMENT '每日结束时间，北京时间',
    `priority` INT NOT NULL DEFAULT 100 COMMENT '优先级，数字小优先',
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `description` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_price_adjustment_match` (`enabled`, `model_series`, `model_type`, `billing_type`, `priority`),
    KEY `idx_price_adjustment_schedule` (`schedule_type`, `start_time`, `end_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型分类价格调控规则表';

-- ============================================================
-- 4.2 user_price_adjustment_rule - 用户专属模型价格调控规则表
-- ============================================================
CREATE TABLE `user_price_adjustment_rule` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(128) NOT NULL COMMENT '规则名称',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `model_series` VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'gpt/claude/grok/gemini/other/all',
    `model_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'chat/image/video/embedding/completion/all',
    `billing_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT 'token/request/image_credit/free/all',
    `multiplier` DECIMAL(12, 6) NOT NULL DEFAULT 1 COMMENT '用户专属价格倍率',
    `schedule_type` VARCHAR(20) NOT NULL DEFAULT 'always' COMMENT 'always/daily_time',
    `start_time` TIME DEFAULT NULL COMMENT '每日开始时间，北京时间',
    `end_time` TIME DEFAULT NULL COMMENT '每日结束时间，北京时间',
    `priority` INT NOT NULL DEFAULT 100 COMMENT '优先级，数字小优先',
    `enabled` TINYINT NOT NULL DEFAULT 1,
    `description` TEXT DEFAULT NULL,
    `created_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '创建管理员ID',
    `updated_by` BIGINT UNSIGNED DEFAULT NULL COMMENT '最后更新管理员ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_price_adjustment_user` (`user_id`, `enabled`),
    KEY `idx_user_price_adjustment_match` (`user_id`, `enabled`, `model_series`, `model_type`, `billing_type`, `priority`),
    KEY `idx_user_price_adjustment_schedule` (`schedule_type`, `start_time`, `end_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户专属模型价格调控规则表';

-- ============================================================
-- 4.3 video_task_billing_snapshot - 异步视频任务计费快照表
-- ============================================================
CREATE TABLE `video_task_billing_snapshot` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `video_id` VARCHAR(128) NOT NULL COMMENT '上游视频任务ID',
    `request_id` VARCHAR(36) DEFAULT NULL COMMENT '创建请求ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `channel_id` BIGINT UNSIGNED NOT NULL COMMENT '渠道ID',
    `requested_model` VARCHAR(128) DEFAULT NULL,
    `actual_model` VARCHAR(128) DEFAULT NULL,
    `billing_type` VARCHAR(20) DEFAULT 'image_credit',
    `charged_credits` DECIMAL(12, 3) DEFAULT 0,
    `model_multiplier` DECIMAL(12, 3) DEFAULT 1,
    `video_size` VARCHAR(16) DEFAULT NULL,
    `video_seconds` INT DEFAULT 0,
    `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
    `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL,
    `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL,
    `billed` TINYINT NOT NULL DEFAULT 0,
    `billed_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_video_task_billing_video_id` (`video_id`),
    KEY `idx_video_task_user` (`user_id`, `created_at`),
    KEY `idx_video_task_billed` (`billed`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异步视频任务计费快照表';

-- ============================================================
-- 5. model_channel_mapping - 模型-渠道映射表
-- ============================================================
CREATE TABLE `model_channel_mapping` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `unified_model_id` BIGINT UNSIGNED NOT NULL,
    `channel_id` BIGINT UNSIGNED NOT NULL,
    `actual_model_name` VARCHAR(128) NOT NULL COMMENT '该渠道中的实际模型名称',
    `default_reasoning_effort` VARCHAR(16) DEFAULT NULL COMMENT '默认推理强度: minimal/low/medium/high/xhigh',
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
    `billable_input_tokens` INT DEFAULT 0,
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
    `billable_cache_read_input_tokens` INT DEFAULT 0,
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
    `service_tier` VARCHAR(32) DEFAULT NULL COMMENT 'Responses service tier snapshot',
    `cache_read_cost` DECIMAL(12, 6) DEFAULT 0,
    `cache_creation_cost` DECIMAL(12, 6) DEFAULT 0,
    `input_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0,
    `output_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0,
    `cache_creation_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0,
    `request_price_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '按请求计费单次价格快照',
    `global_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '系统全局价格倍率快照',
    `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '分类/用户价格调控倍率快照',
    `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL COMMENT '倍率来源:user/global/default',
    `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL COMMENT '命中倍率规则ID快照',
    `price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
    `fast_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
    `context_tokens_snapshot` INT DEFAULT 0 COMMENT '计费上下文Token快照',
    `context_token_threshold_snapshot` INT DEFAULT 262144 COMMENT '长上下文计费阈值快照',
    `context_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '长上下文价格倍率快照',
    `token_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_request_id` (`request_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_channel_id` (`channel_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_status` (`status`),
    KEY `idx_requested_model` (`requested_model`),
    KEY `idx_conversation_session_id` (`conversation_session_id`),
    KEY `idx_request_log_user_id_id` (`user_id`, `id`),
    KEY `idx_request_log_requested_model_id` (`requested_model`, `id`),
    KEY `idx_request_log_status_id` (`status`, `id`),
    KEY `idx_request_log_created_at_id` (`created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求日志表';

-- ============================================================
-- 9. security_request_snapshot - 安全风控请求快照表
-- ============================================================
CREATE TABLE `security_request_snapshot` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `snapshot_id` VARCHAR(36) NOT NULL COMMENT 'Security snapshot UUID',
    `request_id` VARCHAR(36) DEFAULT NULL COMMENT 'Proxy request UUID',
    `user_id` BIGINT UNSIGNED DEFAULT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `user_api_key_id` BIGINT UNSIGNED DEFAULT NULL,
    `requested_model` VARCHAR(128) DEFAULT NULL,
    `protocol_type` VARCHAR(32) DEFAULT NULL,
    `request_type` VARCHAR(32) DEFAULT 'chat',
    `client_ip` VARCHAR(45) DEFAULT NULL,
    `request_hash` CHAR(64) NOT NULL,
    `report_token_hash` CHAR(64) DEFAULT NULL,
    `request_preview` TEXT DEFAULT NULL,
    `request_body_json` LONGTEXT DEFAULT NULL,
    `extracted_text` MEDIUMTEXT DEFAULT NULL,
    `is_truncated` TINYINT NOT NULL DEFAULT 0,
    `body_size_bytes` INT NOT NULL DEFAULT 0,
    `retention_status` VARCHAR(20) NOT NULL DEFAULT 'temporary',
    `risk_level` VARCHAR(20) NOT NULL DEFAULT 'none',
    `risk_categories_json` TEXT DEFAULT NULL,
    `expires_at` DATETIME DEFAULT NULL,
    `purged_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_security_snapshot_id` (`snapshot_id`),
    KEY `idx_security_snapshot_request_id` (`request_id`),
    KEY `idx_security_snapshot_user_created` (`user_id`, `created_at`),
    KEY `idx_security_snapshot_retention_expires` (`retention_status`, `expires_at`),
    KEY `idx_security_snapshot_risk_level` (`risk_level`),
    KEY `idx_security_snapshot_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全风控请求快照表';

-- ============================================================
-- 10. security_risk_event - 安全风控风险事件表
-- ============================================================
CREATE TABLE `security_risk_event` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `event_id` VARCHAR(36) NOT NULL COMMENT 'Security event UUID',
    `snapshot_id` VARCHAR(36) DEFAULT NULL,
    `snapshot_db_id` BIGINT UNSIGNED DEFAULT NULL,
    `request_id` VARCHAR(36) DEFAULT NULL,
    `user_id` BIGINT UNSIGNED DEFAULT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `requested_model` VARCHAR(128) DEFAULT NULL,
    `protocol_type` VARCHAR(32) DEFAULT NULL,
    `event_source` VARCHAR(32) NOT NULL DEFAULT 'keyword',
    `risk_level` VARCHAR(20) NOT NULL DEFAULT 'medium',
    `category` VARCHAR(64) NOT NULL,
    `action` VARCHAR(32) NOT NULL DEFAULT 'review',
    `matched_rules_json` TEXT DEFAULT NULL,
    `reason` TEXT DEFAULT NULL,
    `response_excerpt` MEDIUMTEXT DEFAULT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'open',
    `reviewer_id` BIGINT UNSIGNED DEFAULT NULL,
    `review_note` TEXT DEFAULT NULL,
    `reviewed_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_security_event_id` (`event_id`),
    KEY `idx_security_event_snapshot_id` (`snapshot_id`),
    KEY `idx_security_event_snapshot_db_id` (`snapshot_db_id`),
    KEY `idx_security_event_request_id` (`request_id`),
    KEY `idx_security_event_status_created` (`status`, `created_at`),
    KEY `idx_security_event_level_created` (`risk_level`, `created_at`),
    KEY `idx_security_event_category_created` (`category`, `created_at`),
    KEY `idx_security_event_user_created` (`user_id`, `created_at`),
    KEY `idx_security_event_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全风控风险事件表';

-- ============================================================
-- 11. request_cache_summary - 请求体缓存摘要表
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
-- 10.1 platform_announcement - 平台公告表
-- ============================================================
CREATE TABLE `platform_announcement` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `title` VARCHAR(128) NOT NULL,
    `content` TEXT NOT NULL,
    `status` VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/published/offline',
    `show_popup` TINYINT NOT NULL DEFAULT 1 COMMENT '1=登录开屏弹出,0=仅公告中心展示',
    `sort_order` INT NOT NULL DEFAULT 0,
    `published_at` DATETIME DEFAULT NULL,
    `created_by_user_id` BIGINT UNSIGNED DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_platform_announcement_status` (`status`),
    KEY `idx_platform_announcement_popup` (`show_popup`),
    KEY `idx_platform_announcement_sort` (`sort_order`, `id`),
    KEY `idx_platform_announcement_creator` (`created_by_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='平台公告表';

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
    `billable_input_tokens` INT DEFAULT 0,
    `raw_input_tokens` INT DEFAULT 0,
    `raw_output_tokens` INT DEFAULT 0,
    `raw_total_tokens` INT DEFAULT 0,
    `logical_input_tokens` INT DEFAULT 0,
    `upstream_input_tokens` INT DEFAULT 0,
    `upstream_cache_read_input_tokens` INT DEFAULT 0,
    `billable_cache_read_input_tokens` INT DEFAULT 0,
    `upstream_cache_creation_input_tokens` INT DEFAULT 0,
    `upstream_prompt_cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Anthropic prompt cache status',
    `input_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `cache_read_cost` DECIMAL(12, 6) DEFAULT 0,
    `cache_creation_cost` DECIMAL(12, 6) DEFAULT 0,
    `output_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_cost` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `input_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0,
    `output_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0,
    `cache_creation_price_per_million_snapshot` DECIMAL(12, 6) DEFAULT 0,
    `request_price_snapshot` DECIMAL(12, 6) DEFAULT 0 COMMENT '按请求计费单次价格快照',
    `global_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '系统全局价格倍率快照',
    `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '分类/用户价格调控倍率快照',
    `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL COMMENT '倍率来源:user/global/default',
    `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL COMMENT '命中倍率规则ID快照',
    `price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
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
    `service_tier` VARCHAR(32) DEFAULT NULL COMMENT 'Responses service tier snapshot',
    `fast_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
    `context_tokens_snapshot` INT DEFAULT 0 COMMENT '计费上下文Token快照',
    `context_token_threshold_snapshot` INT DEFAULT 262144 COMMENT '长上下文计费阈值快照',
    `context_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '长上下文价格倍率快照',
    `token_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1,
    `operator_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '人工操作用户ID',
    `remark` VARCHAR(255) DEFAULT NULL COMMENT '用户可见备注',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_request_id` (`request_id`),
    KEY `idx_consumption_operator_id` (`operator_id`),
    KEY `idx_billing_mode` (`billing_mode`),
    KEY `idx_subscription_id` (`subscription_id`),
    KEY `idx_subscription_cycle_id` (`subscription_cycle_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_consumption_user_created_id` (`user_id`, `created_at`, `id`),
    KEY `idx_consumption_subscription_created_id` (`subscription_id`, `created_at`, `id`)
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
    `sale_price_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '用户在线购买售价 RMB',
    `agent_cost_price_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '代理拿货价 RMB',
    `online_sale_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '是否允许用户前台在线购买',
    `sort_order` INT NOT NULL DEFAULT 0,
    `status` VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active/inactive',
    `description` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_subscription_plan_code` (`plan_code`),
    KEY `idx_subscription_plan_online_sale` (`online_sale_enabled`, `status`),
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
    `adjustment_price_multiplier_snapshot` DECIMAL(12, 6) DEFAULT 1 COMMENT '分类/用户价格调控倍率快照',
    `price_adjustment_source_snapshot` VARCHAR(20) DEFAULT NULL COMMENT '倍率来源:user/global/default',
    `price_adjustment_rule_id_snapshot` BIGINT UNSIGNED DEFAULT NULL COMMENT '命中倍率规则ID快照',
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
-- 12.4.1 payment_recharge_order - 在线充值订单表
-- ============================================================
CREATE TABLE `payment_recharge_order` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `order_no` VARCHAR(64) NOT NULL,
    `payment_channel` VARCHAR(32) NOT NULL DEFAULT 'alipay',
    `recharge_type` VARCHAR(32) NOT NULL DEFAULT 'balance' COMMENT '充值类型: balance/image_credit/subscription',
    `user_id` BIGINT UNSIGNED NOT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `site_scope` VARCHAR(16) NOT NULL DEFAULT 'platform',
    `source_host` VARCHAR(255) DEFAULT NULL,
    `return_url_snapshot` VARCHAR(512) DEFAULT NULL,
    `amount_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '用户支付人民币金额',
    `credited_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '用户到账美元余额',
    `credited_image_credits` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '到账图片积分',
    `agent_settlement_rate` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '代理内部结算比例，单位：1 RMB 对应多少 USD',
    `agent_income_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '代理现金分润人民币',
    `subscription_plan_id` BIGINT UNSIGNED DEFAULT NULL,
    `subscription_id` BIGINT UNSIGNED DEFAULT NULL,
    `plan_code_snapshot` VARCHAR(64) DEFAULT NULL,
    `plan_name_snapshot` VARCHAR(128) DEFAULT NULL,
    `plan_kind_snapshot` VARCHAR(32) DEFAULT NULL,
    `duration_days_snapshot` INT DEFAULT NULL,
    `quota_metric_snapshot` VARCHAR(32) DEFAULT NULL,
    `quota_value_snapshot` DECIMAL(20, 6) DEFAULT NULL,
    `subscription_activation_mode` VARCHAR(20) NOT NULL DEFAULT 'append',
    `subscription_sale_price_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `subscription_agent_cost_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `subscription_agent_rebate_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/closed/failed',
    `subject` VARCHAR(128) NOT NULL,
    `body` TEXT DEFAULT NULL,
    `alipay_trade_no` VARCHAR(64) DEFAULT NULL,
    `wechat_transaction_id` VARCHAR(64) DEFAULT NULL,
    `wechat_code_url` TEXT DEFAULT NULL,
    `trade_status` VARCHAR(32) DEFAULT NULL,
    `buyer_logon_id` VARCHAR(128) DEFAULT NULL,
    `buyer_user_id` VARCHAR(64) DEFAULT NULL,
    `expired_at` DATETIME DEFAULT NULL,
    `closed_at` DATETIME DEFAULT NULL,
    `paid_at` DATETIME DEFAULT NULL,
    `notify_raw` TEXT DEFAULT NULL,
    `return_raw` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_payment_recharge_order_no` (`order_no`),
    UNIQUE KEY `uk_payment_recharge_alipay_trade_no` (`alipay_trade_no`),
    UNIQUE KEY `uk_payment_recharge_wechat_transaction_id` (`wechat_transaction_id`),
    KEY `idx_payment_recharge_type` (`recharge_type`),
    KEY `idx_payment_recharge_user_status` (`user_id`, `status`),
    KEY `idx_payment_recharge_agent_status` (`agent_id`, `status`),
    KEY `idx_payment_recharge_subscription_plan` (`subscription_plan_id`),
    KEY `idx_payment_recharge_subscription_id` (`subscription_id`),
    KEY `idx_payment_recharge_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='在线充值订单表';

-- ============================================================
-- 12.4.2 payment_recharge_settlement - 在线充值入账幂等表
-- ============================================================
CREATE TABLE `payment_recharge_settlement` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `order_id` BIGINT UNSIGNED NOT NULL,
    `order_no` VARCHAR(64) NOT NULL,
    `asset_type` VARCHAR(32) NOT NULL DEFAULT 'balance' COMMENT '入账资产: balance/image_credit/subscription',
    `user_id` BIGINT UNSIGNED NOT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `amount_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '用户支付人民币金额',
    `credited_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0 COMMENT '到账美元余额',
    `credited_image_credits` DECIMAL(12, 3) NOT NULL DEFAULT 0 COMMENT '到账图片积分',
    `status` VARCHAR(16) NOT NULL DEFAULT 'settling' COMMENT 'settling/applied',
    `applied_at` DATETIME DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_payment_recharge_settlement_order_asset` (`order_no`, `asset_type`),
    KEY `idx_payment_recharge_settlement_order_id` (`order_id`),
    KEY `idx_payment_recharge_settlement_user_id` (`user_id`),
    KEY `idx_payment_recharge_settlement_agent_id` (`agent_id`),
    KEY `idx_payment_recharge_settlement_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='在线充值入账幂等表';

-- ============================================================
-- 12.5 user_promotion_link - 用户推广链接表
-- ============================================================
CREATE TABLE `user_promotion_link` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `site_scope` VARCHAR(16) NOT NULL DEFAULT 'platform',
    `site_host` VARCHAR(255) DEFAULT NULL,
    `invite_code` VARCHAR(32) NOT NULL,
    `status` VARCHAR(16) NOT NULL DEFAULT 'active',
    `register_count` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `recharge_user_count` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `total_reward_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_reward_image_credits` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_promotion_link_code` (`invite_code`),
    UNIQUE KEY `uk_user_promotion_link_user` (`user_id`),
    KEY `idx_user_promotion_link_agent` (`agent_id`),
    KEY `idx_user_promotion_link_scope` (`site_scope`),
    KEY `idx_user_promotion_link_status` (`status`),
    KEY `idx_user_promotion_link_host` (`site_host`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户推广链接表';

-- ============================================================
-- 12.6 user_promotion_relation - 用户推广绑定关系表
-- ============================================================
CREATE TABLE `user_promotion_relation` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `promoter_user_id` BIGINT UNSIGNED NOT NULL,
    `promoter_agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `invite_code` VARCHAR(32) NOT NULL,
    `invite_link_id` BIGINT UNSIGNED NOT NULL,
    `invited_user_id` BIGINT UNSIGNED NOT NULL,
    `invited_agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `site_scope` VARCHAR(16) NOT NULL DEFAULT 'platform',
    `site_host` VARCHAR(255) DEFAULT NULL,
    `first_recharged_at` DATETIME DEFAULT NULL,
    `total_recharge_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `total_reward_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `total_reward_image_credits` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_promotion_relation_invited` (`invited_user_id`),
    KEY `idx_user_promotion_relation_promoter` (`promoter_user_id`),
    KEY `idx_user_promotion_relation_promoter_agent` (`promoter_agent_id`),
    KEY `idx_user_promotion_relation_code` (`invite_code`),
    KEY `idx_user_promotion_relation_link` (`invite_link_id`),
    KEY `idx_user_promotion_relation_invited_agent` (`invited_agent_id`),
    KEY `idx_user_promotion_relation_scope` (`site_scope`),
    KEY `idx_user_promotion_relation_first_recharged` (`first_recharged_at`),
    KEY `idx_user_promotion_relation_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户推广绑定关系表';

-- ============================================================
-- 12.7 user_promotion_reward - 用户推广充值返现记录表
-- ============================================================
CREATE TABLE `user_promotion_reward` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `relation_id` BIGINT UNSIGNED NOT NULL,
    `promoter_user_id` BIGINT UNSIGNED NOT NULL,
    `promoter_agent_id` BIGINT UNSIGNED DEFAULT NULL,
    `invited_user_id` BIGINT UNSIGNED NOT NULL,
    `invite_code` VARCHAR(32) NOT NULL,
    `order_id` BIGINT UNSIGNED NOT NULL,
    `order_no` VARCHAR(64) NOT NULL,
    `recharge_type` VARCHAR(32) NOT NULL DEFAULT 'balance',
    `amount_cny` DECIMAL(12, 2) NOT NULL DEFAULT 0,
    `credited_usd` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `credited_image_credits` DECIMAL(12, 3) NOT NULL DEFAULT 0,
    `reward_asset_type` VARCHAR(32) NOT NULL DEFAULT 'balance',
    `reward_amount` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `reward_rate` DECIMAL(12, 6) NOT NULL DEFAULT 0,
    `status` VARCHAR(16) NOT NULL DEFAULT 'applied',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_promotion_reward_order_asset` (`order_no`, `reward_asset_type`),
    KEY `idx_user_promotion_reward_relation` (`relation_id`),
    KEY `idx_user_promotion_reward_promoter` (`promoter_user_id`),
    KEY `idx_user_promotion_reward_promoter_agent` (`promoter_agent_id`),
    KEY `idx_user_promotion_reward_invited` (`invited_user_id`),
    KEY `idx_user_promotion_reward_code` (`invite_code`),
    KEY `idx_user_promotion_reward_order_id` (`order_id`),
    KEY `idx_user_promotion_reward_recharge_type` (`recharge_type`),
    KEY `idx_user_promotion_reward_asset` (`reward_asset_type`),
    KEY `idx_user_promotion_reward_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户推广充值返现记录表';

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
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`, `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('gemini-2.5-flash-image', 'Gemini 2.5 Flash Image', 'image', 'gemini', 'google', NULL, 0, 0, 'image_credit', 0, 1, 0, 1, 'Google Gemini 2.5 Flash 图片生成（按图片积分计费）'),
('gemini-3.1-flash-image-preview', 'Gemini 3.1 Flash Image Preview', 'image', 'gemini', 'google', NULL, 0, 0, 'image_credit', 0, 2, 0, 1, 'Google Gemini 3.1 Flash 图片生成（按图片积分计费）'),
('gemini-3-pro-image-preview', 'Gemini 3 Pro Image Preview', 'image', 'gemini', 'google', NULL, 0, 0, 'image_credit', 0, 3, 0, 1, 'Google Gemini 3 Pro 图片生成（按图片积分计费）');

INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`, `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('gpt-image-2', 'GPT Image 2', 'image', 'gpt', 'openai', NULL, 0, 0, 'image_credit', 0, 0.5, 1, 1, 'OpenAI 兼容图片生成模型 GPT Image 2（按图片积分计费）');

-- 预置 Grok 视频模型
INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`, `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('grok-imagine-video', 'Grok Imagine Video', 'video', 'grok', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'Grok Imagine 视频生成模型（按媒体积分计费，默认 0.5 积分/秒，需映射到 grok2api 渠道）')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `model_series` = VALUES(`model_series`),
    `protocol_type` = VALUES(`protocol_type`),
    `billing_type` = VALUES(`billing_type`),
    `request_price` = VALUES(`request_price`),
    `image_credit_multiplier` = VALUES(`image_credit_multiplier`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

-- 预置 zz1cc 视频模型
INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`, `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('video-ds-2.0', 'video-ds-2.0', 'video', 'other', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'zz1cc video-ds-2.0 视频生成模型（按媒体积分计费，默认 0.5 积分/秒，需映射到 zz1cc-video 渠道）'),
('video-ds-2.0-fast', 'video-ds-2.0-fast', 'video', 'other', 'openai', NULL, 0, 0, 'image_credit', 0, 0.500, 0, 1, 'zz1cc video-ds-2.0-fast 视频生成模型（按媒体积分计费，默认 0.5 积分/秒，需映射到 zz1cc-video 渠道）')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `model_series` = VALUES(`model_series`),
    `protocol_type` = VALUES(`protocol_type`),
    `billing_type` = VALUES(`billing_type`),
    `request_price` = VALUES(`request_price`),
    `image_credit_multiplier` = VALUES(`image_credit_multiplier`),
    `enabled` = VALUES(`enabled`),
    `description` = VALUES(`description`);

-- 预置 Grok 文本模型
INSERT INTO `unified_model` (
    `model_name`, `display_name`, `model_type`, `model_series`, `protocol_type`, `max_tokens`,
    `input_price_per_million`, `output_price_per_million`, `billing_type`, `request_price`, `image_credit_multiplier`, `security_monitor_enabled`, `enabled`, `description`
) VALUES
('grok-4.20-0309-non-reasoning', 'Grok 4.20 0309 Non-Reasoning', 'chat', 'grok', 'openai', 128000, 2.000000, 6.000000, 'token', 0, 1, 0, 1, 'xAI Grok 4.20 0309 非推理版（官方定价 2/6）'),
('grok-4.20-0309', 'Grok 4.20 0309', 'chat', 'grok', 'openai', 128000, 2.000000, 6.000000, 'token', 0, 1, 0, 1, 'xAI Grok 4.20 0309（按 4.20 主档推断定价 2/6）'),
('grok-4.20-0309-reasoning', 'Grok 4.20 0309 Reasoning', 'chat', 'grok', 'openai', 128000, 2.000000, 6.000000, 'token', 0, 1, 0, 1, 'xAI Grok 4.20 0309 推理版（官方定价 2/6）'),
('grok-4.20-fast', 'Grok 4.20 Fast', 'chat', 'grok', 'openai', 128000, 0.200000, 0.500000, 'token', 0, 1, 0, 1, 'xAI Grok 4.20 Fast（参照 4.1 fast 档推断定价 0.2/0.5）'),
('grok-4.20-auto', 'Grok 4.20 Auto', 'chat', 'grok', 'openai', 128000, 2.000000, 6.000000, 'token', 0, 1, 0, 1, 'xAI Grok 4.20 Auto（按 4.20 主档推断定价 2/6）'),
('grok-4.20-expert', 'Grok 4.20 Expert', 'chat', 'grok', 'openai', 128000, 2.000000, 6.000000, 'token', 0, 1, 0, 1, 'xAI Grok 4.20 Expert（按 4.20 高阶档推断定价 2/6）')
ON DUPLICATE KEY UPDATE
    `display_name` = VALUES(`display_name`),
    `model_type` = VALUES(`model_type`),
    `model_series` = VALUES(`model_series`),
    `protocol_type` = VALUES(`protocol_type`),
    `max_tokens` = VALUES(`max_tokens`),
    `input_price_per_million` = VALUES(`input_price_per_million`),
    `output_price_per_million` = VALUES(`output_price_per_million`),
    `billing_type` = VALUES(`billing_type`),
    `request_price` = VALUES(`request_price`),
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
SET @chatgpt_image_base_url = 'http://43.128.147.93:3000';

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
('max_retry_count', '3', 'number', '上游失败重试次数'),
('promotion_reward_rate', '0.2', 'number', '推广返利比例，小数形式：0.2=20%，0=关闭'),
('api_base_url', 'https://your-domain.com', 'string', 'API基础地址，用于快速开始页面展示给用户的接入地址'),
('request_body_cache_enabled', 'false', 'boolean', '是否启用请求体分段缓存分析'),
('request_body_cache_user_visible', 'false', 'boolean', '用户端是否显示缓存读取/创建信息'),
('request_body_cache_ttl_seconds', '1800', 'number', '请求体缓存 TTL（秒）'),
('request_body_cache_min_chars', '256', 'number', '最小缓存片段字符数阈值'),
('request_body_cache_formats', 'anthropic_messages,openai_chat,responses', 'string', '启用请求体缓存分析的请求格式'),
('security_detection_enabled', 'true', 'boolean', '是否启用安全风控输入检测'),
('security_snapshot_enabled', 'true', 'boolean', '是否短期保存安全风控请求快照'),
('security_snapshot_ttl_seconds', '1800', 'number', '无风险请求快照完整内容保留秒数'),
('security_flagged_retention_days', '30', 'number', '风险请求快照保留天数'),
('security_keyword_block_enabled', 'true', 'boolean', '是否启用关键词高风险阻断'),
('security_output_scan_enabled', 'true', 'boolean', '是否启用非流式输出安全检测'),
('security_stream_output_scan_enabled', 'true', 'boolean', '是否启用流式输出风险标记检测'),
('security_model_prompt_enabled', 'false', 'boolean', '是否向文本模型注入安全拒绝提示词'),
('security_block_message', '请求可能涉及违规或高风险内容，已被安全策略拦截。你可以改为询问合法合规的学习、防护或排查建议。', 'string', '安全风控阻断提示文案'),
('security_fail_closed_enabled', 'false', 'boolean', '风控服务异常时是否阻断主请求'),
('security_snapshot_max_body_bytes', '262144', 'number', '安全风控快照最大保存字节数'),
('security_scan_max_text_chars', '20000', 'number', '安全风控最大扫描文本字符数'),
('security_public_report_enabled', 'true', 'boolean', '是否启用公网免登录风险上报接口'),
('security_public_report_rate_limit_per_minute', '60', 'number', '公网风险上报接口每 IP 每分钟限制'),
('anthropic_prompt_cache_enabled', 'false', 'boolean', '是否启用 Anthropic Prompt Cache'),
('anthropic_prompt_cache_history_enabled', 'true', 'boolean', '是否启用 Anthropic Prompt Cache 历史自动缓存'),
('anthropic_prompt_cache_static_ttl', '5m', 'string', 'Anthropic Prompt Cache 静态前缀 TTL（5m/1h）'),
('anthropic_prompt_cache_history_ttl', '5m', 'string', 'Anthropic Prompt Cache 历史前缀 TTL（5m/1h）'),
('anthropic_prompt_cache_beta_header', 'extended-cache-ttl-2025-04-11', 'string', 'Anthropic Prompt Cache 1h TTL beta header'),
('anthropic_prompt_cache_user_visible', 'false', 'boolean', '用户端是否显示 Anthropic Prompt Cache 读写详情'),
('anthropic_prompt_cache_billing_mode', 'logical', 'string', 'Anthropic Prompt Cache 计费口径：logical 或 actual_upstream'),
('anthropic_prompt_cache_override_min_logical_tokens', '10000', 'number', '覆盖低效用户 cache_control 的最小逻辑输入 token 阈值'),
('anthropic_prompt_cache_override_quick_fail_consecutive', '2', 'number', '连续低命中多少次后立即覆盖用户 cache_control'),
('anthropic_prompt_cache_override_recovery_hit_ratio', '0.50', 'number', '连续恢复命中率达到该值后才停止覆盖用户 cache_control'),
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
