-- ============================================================
-- Conversation State Compaction 升级脚本
-- Date: 2026-03-25
-- ============================================================

-- 1. request_log 新增会话压缩影子字段

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'conversation_session_id'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `conversation_session_id` VARCHAR(64) DEFAULT NULL COMMENT 'Conversation session id' AFTER `upstream_prompt_cache_status`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND INDEX_NAME = 'idx_conversation_session_id'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD INDEX `idx_conversation_session_id` (`conversation_session_id`)"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'conversation_match_status'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `conversation_match_status` VARCHAR(20) DEFAULT NULL COMMENT 'Conversation match status' AFTER `conversation_session_id`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'compression_mode'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `compression_mode` VARCHAR(32) DEFAULT NULL COMMENT 'Conversation compaction mode' AFTER `conversation_match_status`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'compression_status'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `compression_status` VARCHAR(20) DEFAULT NULL COMMENT 'Conversation compaction status' AFTER `compression_mode`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

ALTER TABLE `request_log`
    MODIFY COLUMN `compression_status` VARCHAR(64) DEFAULT NULL COMMENT 'Conversation compaction status';

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'original_estimated_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `original_estimated_input_tokens` INT NOT NULL DEFAULT 0 AFTER `compression_status`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'compressed_estimated_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `compressed_estimated_input_tokens` INT NOT NULL DEFAULT 0 AFTER `original_estimated_input_tokens`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'compression_saved_estimated_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `compression_saved_estimated_tokens` INT NOT NULL DEFAULT 0 AFTER `compressed_estimated_input_tokens`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'compression_ratio'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `compression_ratio` DECIMAL(10,4) NOT NULL DEFAULT 0 AFTER `compression_saved_estimated_tokens`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'compression_fallback_reason'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `compression_fallback_reason` TEXT DEFAULT NULL AFTER `compression_ratio`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'upstream_session_mode'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_session_mode` VARCHAR(20) DEFAULT NULL COMMENT 'Upstream session mode' AFTER `compression_fallback_reason`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'request_log' AND COLUMN_NAME = 'upstream_session_id'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_session_id` VARCHAR(128) DEFAULT NULL COMMENT 'Upstream session id' AFTER `upstream_session_mode`"
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. 新增 conversation_session

CREATE TABLE IF NOT EXISTS `conversation_session` (
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

-- 3. 新增 conversation_checkpoint

CREATE TABLE IF NOT EXISTS `conversation_checkpoint` (
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

-- 4. system_config 新增 conversation_state 配置

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_compaction_enabled', 'false', 'boolean', '是否启用会话状态压缩'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_compaction_enabled');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_compaction_stage', 'shadow', 'string', '会话状态压缩阶段：off/shadow/non_stream_active/stream_shadow/stream_active'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_compaction_stage');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_compaction_mode', 'safe_history', 'string', '会话状态压缩模式：off/safe_history/stateful_preferred'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_compaction_mode');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_compaction_recent_turns', '6', 'number', '会话压缩时保留的最近精确 turn 数'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_compaction_recent_turns');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_compaction_trigger_tokens', '12000', 'number', '触发会话历史压缩的估算 token 阈值'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_compaction_trigger_tokens');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_compaction_summary_max_tokens', '1500', 'number', '会话检查点摘要最大估算 token'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_compaction_summary_max_tokens');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_session_ttl_seconds', '86400', 'number', '会话状态 TTL（秒）'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_session_ttl_seconds');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_match_window', '20', 'number', '会话匹配时最多回看最近多少个候选会话'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_match_window');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_match_tail_tolerance_messages', '2', 'number', '会话匹配时允许尾部改写/重排的最大消息数'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_match_tail_tolerance_messages');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_match_min_shared_prefix', '8', 'number', '会话匹配时判定尾部改写所需的最小公共前缀消息数'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_match_min_shared_prefix');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_failure_cooldown_seconds', '600', 'number', '压缩失败后的会话冷却时间（秒）'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_failure_cooldown_seconds');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_user_visible', 'false', 'boolean', '用户端是否显示会话压缩收益'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_user_visible');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_async_checkpoint_enabled', 'true', 'boolean', '是否启用异步会话检查点构建'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_async_checkpoint_enabled');

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'conversation_state_tool_compaction_enabled', 'false', 'boolean', '是否启用实验性的 tools/system 压缩'
WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'conversation_state_tool_compaction_enabled');
