-- Apply to the selected application database before deploying the new ORM.
-- Idempotent MySQL 8 upgrade; never changes historical token usage or fees.
SET SESSION lock_wait_timeout = 5;

-- Local cache simulation: durable rules and immutable decisions.
CREATE TABLE IF NOT EXISTS cache_simulation_rule (
	id BIGINT NOT NULL AUTO_INCREMENT,
	user_id BIGINT NOT NULL,
	group_id BIGINT NOT NULL,
	enabled SMALLINT NOT NULL DEFAULT 1,
	generation BIGINT NOT NULL DEFAULT 1,
	operator_id BIGINT NOT NULL,
	created_at DATETIME NOT NULL DEFAULT now(),
	updated_at DATETIME NOT NULL DEFAULT now(),
	PRIMARY KEY (id),
	CONSTRAINT uk_cache_simulation_pair UNIQUE (user_id, group_id),
	KEY `ix_cache_simulation_rule_group_id` (`group_id`),
	KEY `ix_cache_simulation_rule_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cache_simulation_decision (
	id BIGINT NOT NULL AUTO_INCREMENT,
	request_id VARCHAR(36) NOT NULL,
	decision_id VARCHAR(36) NOT NULL,
	user_id BIGINT NOT NULL,
	user_api_key_id BIGINT,
	group_id BIGINT NOT NULL,
	unified_model_id BIGINT NOT NULL,
	username_snapshot VARCHAR(64) NOT NULL,
	group_name_snapshot VARCHAR(128) NOT NULL,
	requested_model VARCHAR(128) NOT NULL,
	protocol VARCHAR(20) NOT NULL,
	rule_id BIGINT NOT NULL,
	rule_generation BIGINT NOT NULL,
	config_version BIGINT NOT NULL,
	enable_epoch BIGINT NOT NULL,
	session_digest VARCHAR(64),
	identity_source VARCHAR(32) NOT NULL,
	identity_confidence VARCHAR(20) NOT NULL,
	usage_source VARCHAR(64) NOT NULL,
	decision_status VARCHAR(20) NOT NULL DEFAULT 'draft',
	accounting_status VARCHAR(20) NOT NULL DEFAULT 'pending',
	state_delivery VARCHAR(20) NOT NULL DEFAULT 'pending',
	outcome VARCHAR(20) NOT NULL DEFAULT 'skipped',
	reason VARCHAR(64),
	coefficient INTEGER,
	transferred_tokens BIGINT NOT NULL DEFAULT 0,
	total_tokens BIGINT NOT NULL,
	context_tokens BIGINT NOT NULL,
	original_cost DECIMAL(20, 10) NOT NULL DEFAULT 0,
	effective_cost DECIMAL(20, 10) NOT NULL DEFAULT 0,
	fee_delta DECIMAL(20, 10) NOT NULL DEFAULT 0,
	window_id VARCHAR(36),
	window_started_at DATETIME,
	window_expires_at DATETIME,
	usage_json TEXT NOT NULL,
	snapshot_json MEDIUMTEXT NOT NULL,
	proposed_state_json MEDIUMTEXT,
	reservation_json TEXT,
	decision_hash VARCHAR(64),
	receipt_json TEXT,
	recovery_attempts INTEGER NOT NULL DEFAULT 0,
	next_retry_at DATETIME,
	last_error VARCHAR(512),
	settled_at DATETIME,
	created_at DATETIME NOT NULL DEFAULT now(),
	updated_at DATETIME NOT NULL DEFAULT now(),
	PRIMARY KEY (id),
	UNIQUE (request_id),
	UNIQUE (decision_id),
	KEY `idx_cache_sim_records` (`outcome`, `accounting_status`, `id`),
	KEY `idx_cache_sim_recovery` (`decision_status`, `accounting_status`, `next_retry_at`),
	KEY `idx_cache_sim_user_group` (`user_id`, `group_id`, `id`),
	KEY `ix_cache_simulation_decision_session_digest` (`session_digest`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='request_log' AND column_name='usage_accounting_version'), 'SELECT 1', 'ALTER TABLE `request_log` ADD COLUMN `usage_accounting_version` SMALLINT NOT NULL DEFAULT 0 COMMENT ''0 legacy; 1 explicit billable buckets'', ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='request_log' AND column_name='billable_cache_creation_input_tokens'), 'SELECT 1', 'ALTER TABLE `request_log` ADD COLUMN `billable_cache_creation_input_tokens` INT NULL, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='request_log' AND column_name='cache_simulation_decision_id'), 'SELECT 1', 'ALTER TABLE `request_log` ADD COLUMN `cache_simulation_decision_id` VARCHAR(36) NULL, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='request_log' AND column_name='cache_simulation_applied'), 'SELECT 1', 'ALTER TABLE `request_log` ADD COLUMN `cache_simulation_applied` SMALLINT NOT NULL DEFAULT 0, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='request_log' AND column_name='failure_stage'), 'SELECT 1', 'ALTER TABLE `request_log` ADD COLUMN `failure_stage` VARCHAR(32) NULL, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='request_log' AND index_name='ix_request_log_cache_simulation_decision_id'), 'SELECT 1', 'ALTER TABLE `request_log` ADD INDEX `ix_request_log_cache_simulation_decision_id` (`cache_simulation_decision_id`), ALGORITHM=INPLACE, LOCK=NONE');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='consumption_record' AND column_name='usage_accounting_version'), 'SELECT 1', 'ALTER TABLE `consumption_record` ADD COLUMN `usage_accounting_version` SMALLINT NOT NULL DEFAULT 0 COMMENT ''0 legacy; 1 explicit billable buckets'', ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='consumption_record' AND column_name='billable_cache_creation_input_tokens'), 'SELECT 1', 'ALTER TABLE `consumption_record` ADD COLUMN `billable_cache_creation_input_tokens` INT NULL, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='consumption_record' AND column_name='cache_simulation_decision_id'), 'SELECT 1', 'ALTER TABLE `consumption_record` ADD COLUMN `cache_simulation_decision_id` VARCHAR(36) NULL, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='consumption_record' AND column_name='cache_simulation_applied'), 'SELECT 1', 'ALTER TABLE `consumption_record` ADD COLUMN `cache_simulation_applied` SMALLINT NOT NULL DEFAULT 0, ALGORITHM=INSTANT');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;

SET @cache_sim_ddl = IF(EXISTS (SELECT 1 FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='consumption_record' AND index_name='ix_consumption_record_cache_simulation_decision_id'), 'SELECT 1', 'ALTER TABLE `consumption_record` ADD INDEX `ix_consumption_record_cache_simulation_decision_id` (`cache_simulation_decision_id`), ALGORITHM=INPLACE, LOCK=NONE');
PREPARE cache_sim_stmt FROM @cache_sim_ddl;
EXECUTE cache_sim_stmt;
DEALLOCATE PREPARE cache_sim_stmt;


INSERT INTO system_config (config_key, config_value, config_type, description)
VALUES ('cache_simulation_config', '{"enabled":false,"ttl_seconds":300,"version":1,"enable_epoch":1}', 'json', '模拟缓存：请在专用管理页面编辑')
ON DUPLICATE KEY UPDATE config_key = 'cache_simulation_config';
