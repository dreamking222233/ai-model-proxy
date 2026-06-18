-- 安全风控：违规请求快照与风险事件

DROP PROCEDURE IF EXISTS `upgrade_security_risk_detection_20260618`;

DELIMITER $$

CREATE PROCEDURE `upgrade_security_risk_detection_20260618`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'security_request_snapshot'
    ) THEN
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
            `request_preview` TEXT,
            `request_body_json` LONGTEXT,
            `extracted_text` MEDIUMTEXT,
            `is_truncated` TINYINT NOT NULL DEFAULT 0,
            `body_size_bytes` INT NOT NULL DEFAULT 0,
            `retention_status` VARCHAR(20) NOT NULL DEFAULT 'temporary',
            `risk_level` VARCHAR(20) NOT NULL DEFAULT 'none',
            `risk_categories_json` TEXT,
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'security_risk_event'
    ) THEN
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
            `matched_rules_json` TEXT,
            `reason` TEXT,
            `response_excerpt` MEDIUMTEXT,
            `status` VARCHAR(20) NOT NULL DEFAULT 'open',
            `reviewer_id` BIGINT UNSIGNED DEFAULT NULL,
            `review_note` TEXT,
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
    END IF;

    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
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
    ('security_public_report_rate_limit_per_minute', '60', 'number', '公网风险上报接口每 IP 每分钟限制')
    ON DUPLICATE KEY UPDATE
      `config_value` = VALUES(`config_value`),
      `config_type` = VALUES(`config_type`),
      `description` = VALUES(`description`);
END$$

DELIMITER ;

CALL `upgrade_security_risk_detection_20260618`();
DROP PROCEDURE IF EXISTS `upgrade_security_risk_detection_20260618`;
