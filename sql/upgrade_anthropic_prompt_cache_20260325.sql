-- ============================================================
-- Anthropic Prompt Cache 升级脚本
-- Date: 2026-03-25
-- ============================================================

-- 1. request_log 新增 Anthropic Prompt Cache usage 字段

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'logical_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `logical_input_tokens` INT NOT NULL DEFAULT 0 AFTER `cache_new_chars`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'upstream_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_input_tokens` INT NOT NULL DEFAULT 0 AFTER `logical_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'upstream_cache_read_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_cache_read_input_tokens` INT NOT NULL DEFAULT 0 AFTER `upstream_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'upstream_cache_creation_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_cache_creation_input_tokens` INT NOT NULL DEFAULT 0 AFTER `upstream_cache_read_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'upstream_cache_creation_5m_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_cache_creation_5m_input_tokens` INT NOT NULL DEFAULT 0 AFTER `upstream_cache_creation_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'upstream_cache_creation_1h_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_cache_creation_1h_input_tokens` INT NOT NULL DEFAULT 0 AFTER `upstream_cache_creation_5m_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'request_log'
              AND COLUMN_NAME = 'upstream_prompt_cache_status'
        ),
        'SELECT 1',
        "ALTER TABLE `request_log` ADD COLUMN `upstream_prompt_cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Anthropic prompt cache status' AFTER `upstream_cache_creation_1h_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. consumption_record 新增 Anthropic Prompt Cache usage 字段

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'consumption_record'
              AND COLUMN_NAME = 'logical_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `consumption_record` ADD COLUMN `logical_input_tokens` INT NOT NULL DEFAULT 0 AFTER `total_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'consumption_record'
              AND COLUMN_NAME = 'upstream_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `consumption_record` ADD COLUMN `upstream_input_tokens` INT NOT NULL DEFAULT 0 AFTER `logical_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'consumption_record'
              AND COLUMN_NAME = 'upstream_cache_read_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `consumption_record` ADD COLUMN `upstream_cache_read_input_tokens` INT NOT NULL DEFAULT 0 AFTER `upstream_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'consumption_record'
              AND COLUMN_NAME = 'upstream_cache_creation_input_tokens'
        ),
        'SELECT 1',
        "ALTER TABLE `consumption_record` ADD COLUMN `upstream_cache_creation_input_tokens` INT NOT NULL DEFAULT 0 AFTER `upstream_cache_read_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'consumption_record'
              AND COLUMN_NAME = 'upstream_prompt_cache_status'
        ),
        'SELECT 1',
        "ALTER TABLE `consumption_record` ADD COLUMN `upstream_prompt_cache_status` VARCHAR(20) DEFAULT NULL COMMENT 'Anthropic prompt cache status' AFTER `upstream_cache_creation_input_tokens`"
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. system_config 新增 Anthropic Prompt Cache 配置

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_enabled', 'false', 'boolean', '是否启用 Anthropic Prompt Cache'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_enabled'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_history_enabled', 'true', 'boolean', '是否启用 Anthropic Prompt Cache 历史自动缓存'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_history_enabled'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_static_ttl', '5m', 'string', 'Anthropic Prompt Cache 静态前缀 TTL（5m/1h）'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_static_ttl'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_history_ttl', '5m', 'string', 'Anthropic Prompt Cache 历史前缀 TTL（5m/1h）'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_history_ttl'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_beta_header', 'extended-cache-ttl-2025-04-11', 'string', 'Anthropic Prompt Cache 1h TTL beta header'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_beta_header'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_user_visible', 'false', 'boolean', '用户端是否显示 Anthropic Prompt Cache 读写详情'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_user_visible'
);

INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
SELECT 'anthropic_prompt_cache_billing_mode', 'logical', 'string', 'Anthropic Prompt Cache 计费口径：logical 或 actual_upstream'
WHERE NOT EXISTS (
    SELECT 1 FROM `system_config` WHERE `config_key` = 'anthropic_prompt_cache_billing_mode'
);
