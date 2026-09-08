-- Allow subscription plans to restrict quota to explicit unified_model IDs.
-- Idempotent MySQL 8+. Existing all_models / selected_series rows stay unchanged.
DELIMITER $$
CREATE PROCEDURE upgrade_selected_models_20260908()
BEGIN
  DECLARE n INT DEFAULT 0;
  SELECT COUNT(*) INTO n FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='subscription_plan' AND column_name='allowed_model_ids';
  IF n=0 THEN ALTER TABLE subscription_plan ADD COLUMN allowed_model_ids TEXT NULL; END IF;
  SELECT COUNT(*) INTO n FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='user_subscription' AND column_name='allowed_model_ids_snapshot';
  IF n=0 THEN ALTER TABLE user_subscription ADD COLUMN allowed_model_ids_snapshot TEXT NULL; END IF;
END$$
DELIMITER ;
CALL upgrade_selected_models_20260908();
DROP PROCEDURE upgrade_selected_models_20260908;

CREATE TABLE IF NOT EXISTS subscription_plan_model (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  plan_id BIGINT NOT NULL,
  unified_model_id BIGINT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_plan_model (plan_id, unified_model_id),
  KEY idx_plan_model_id (unified_model_id, plan_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS user_subscription_model (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  subscription_id BIGINT NOT NULL,
  unified_model_id BIGINT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_subscription_model (subscription_id, unified_model_id),
  KEY idx_subscription_model_id (unified_model_id, subscription_id)
) ENGINE=InnoDB;
