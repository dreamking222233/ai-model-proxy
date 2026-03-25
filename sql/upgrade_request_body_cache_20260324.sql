-- ============================================================
-- 请求体分段缓存分析 - 数据库升级脚本
-- 日期: 2026-03-24
-- 目标:
-- 1. 为 request_log 增加缓存摘要字段
-- 2. 新建 request_cache_summary 表
-- 3. 新增系统配置项
-- ============================================================

SET @schema_name = DATABASE();

-- ============================================================
-- request_log 新增缓存摘要字段
-- ============================================================

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_status'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Request body cache status' AFTER `response_time_ms`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_hit_segments'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_hit_segments` INT NOT NULL DEFAULT 0 AFTER `cache_status`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_miss_segments'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_miss_segments` INT NOT NULL DEFAULT 0 AFTER `cache_hit_segments`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_bypass_segments'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_bypass_segments` INT NOT NULL DEFAULT 0 AFTER `cache_miss_segments`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_reused_tokens'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_reused_tokens` INT NOT NULL DEFAULT 0 AFTER `cache_bypass_segments`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_new_tokens'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_new_tokens` INT NOT NULL DEFAULT 0 AFTER `cache_reused_tokens`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_reused_chars'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_reused_chars` INT NOT NULL DEFAULT 0 AFTER `cache_new_tokens`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS(
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = @schema_name
          AND TABLE_NAME = 'request_log'
          AND COLUMN_NAME = 'cache_new_chars'
    ),
    'SELECT 1',
    "ALTER TABLE `request_log` ADD COLUMN `cache_new_chars` INT NOT NULL DEFAULT 0 AFTER `cache_reused_chars`"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================
-- request_cache_summary 表
-- ============================================================

CREATE TABLE IF NOT EXISTS `request_cache_summary` (
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
-- system_config 新增缓存配置
-- ============================================================

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
VALUES
    ('request_body_cache_enabled', 'false', 'boolean', '是否启用请求体分段缓存分析'),
    ('request_body_cache_user_visible', 'false', 'boolean', '用户端是否显示缓存读取/创建信息'),
    ('request_body_cache_ttl_seconds', '1800', 'number', '请求体缓存 TTL（秒）'),
    ('request_body_cache_min_chars', '256', 'number', '最小缓存片段字符数阈值'),
    ('request_body_cache_formats', 'anthropic_messages,openai_chat,responses', 'string', '启用请求体缓存分析的请求格式')
ON DUPLICATE KEY UPDATE
    `config_value` = VALUES(`config_value`),
    `config_type` = VALUES(`config_type`),
    `description` = VALUES(`description`);
