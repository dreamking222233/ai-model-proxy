-- Promotional quota and model-series scope migration (idempotent MySQL 8+).
DELIMITER $$
CREATE PROCEDURE upgrade_bonus_quota_20260903()
BEGIN
  DECLARE n INT DEFAULT 0;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='unified_model' AND column_name='bonus_quota_enabled';
  IF n=0 THEN ALTER TABLE unified_model ADD COLUMN bonus_quota_enabled TINYINT NOT NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='unified_model' AND column_name='billing_config_version';
  IF n=0 THEN ALTER TABLE unified_model ADD COLUMN billing_config_version BIGINT NOT NULL DEFAULT 1; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='subscription_plan' AND column_name='model_scope';
  IF n=0 THEN ALTER TABLE subscription_plan ADD COLUMN model_scope VARCHAR(20) NOT NULL DEFAULT 'all_models'; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='subscription_plan' AND column_name='config_version';
  IF n=0 THEN ALTER TABLE subscription_plan ADD COLUMN config_version BIGINT NOT NULL DEFAULT 1; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='subscription_plan' AND column_name='model_series';
  IF n=0 THEN ALTER TABLE subscription_plan ADD COLUMN model_series TEXT NULL; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='user_subscription' AND column_name='model_scope_snapshot';
  IF n=0 THEN ALTER TABLE user_subscription ADD COLUMN model_scope_snapshot VARCHAR(20) NOT NULL DEFAULT 'all_models'; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='user_subscription' AND column_name='config_version_snapshot';
  IF n=0 THEN ALTER TABLE user_subscription ADD COLUMN config_version_snapshot BIGINT NOT NULL DEFAULT 1; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='user_subscription' AND column_name='model_series_snapshot';
  IF n=0 THEN ALTER TABLE user_subscription ADD COLUMN model_series_snapshot TEXT NULL; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='subscription_usage_cycle' AND column_name='reserved_amount';
  IF n=0 THEN ALTER TABLE subscription_usage_cycle ADD COLUMN reserved_amount DECIMAL(20,6) NOT NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='subscription_usage_cycle' AND column_name='version';
  IF n=0 THEN ALTER TABLE subscription_usage_cycle ADD COLUMN version BIGINT NOT NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='channel' AND column_name='video_billing_evidence_mode';
  IF n=0 THEN ALTER TABLE channel ADD COLUMN video_billing_evidence_mode VARCHAR(32) NOT NULL DEFAULT 'external_reconcile'; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='request_log' AND column_name='bonus_quota_consumed';
  IF n=0 THEN ALTER TABLE request_log ADD COLUMN bonus_quota_consumed DECIMAL(20,6) NULL DEFAULT 0; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='consumption_record' AND column_name='bonus_quota_consumed';
  IF n=0 THEN ALTER TABLE consumption_record ADD COLUMN bonus_quota_consumed DECIMAL(20,6) NULL DEFAULT 0; END IF;
END$$
DELIMITER ;
CALL upgrade_bonus_quota_20260903();
DROP PROCEDURE upgrade_bonus_quota_20260903;

CREATE TABLE IF NOT EXISTS subscription_plan_model_series (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  plan_id BIGINT NOT NULL,
  model_series VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_plan_model_series (plan_id, model_series),
  KEY idx_plan_series (model_series, plan_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS user_subscription_model_series (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  subscription_id BIGINT NOT NULL,
  model_series VARCHAR(32) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_subscription_model_series (subscription_id, model_series),
  KEY idx_subscription_series (model_series, subscription_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS subscription_bonus_grant (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  grant_request_id VARCHAR(64) NOT NULL UNIQUE,
  normalized_payload_hash VARCHAR(64), user_id BIGINT NOT NULL,
  agent_id BIGINT NULL, source_subscription_id BIGINT NOT NULL,
  duration_mode VARCHAR(20) NOT NULL, duration_days INT NULL,
  daily_quota_usd DECIMAL(20,6) NOT NULL, start_time DATETIME NOT NULL,
  end_time DATETIME NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'active',
  created_by BIGINT NULL, cancelled_by BIGINT NULL, cancel_reason VARCHAR(255),
  cancelled_at DATETIME NULL, remark TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_bonus_user_status (user_id, status, end_time)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS subscription_bonus_usage_cycle (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, bonus_grant_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL, cycle_index INT NOT NULL, cycle_date DATE NOT NULL,
  cycle_start_at DATETIME NOT NULL, cycle_end_at DATETIME NOT NULL,
  quota_limit_usd DECIMAL(20,6) NOT NULL, used_amount_usd DECIMAL(20,6) NOT NULL DEFAULT 0,
  reserved_amount_usd DECIMAL(20,6) NOT NULL DEFAULT 0, version BIGINT NOT NULL DEFAULT 0,
  request_count INT NOT NULL DEFAULT 0, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_bonus_cycle (bonus_grant_id, cycle_index), KEY idx_bonus_cycle_user (user_id, cycle_end_at)
) ENGINE=InnoDB;
