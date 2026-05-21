SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 删除所有旧视图，避免重建时与历史对象冲突
SET @views = NULL;
SELECT GROUP_CONCAT('`', table_name, '`') INTO @views
FROM information_schema.views
WHERE table_schema = DATABASE();
SET @views = IF(@views IS NOT NULL, CONCAT('DROP VIEW IF EXISTS ', @views), 'SELECT 1');
PREPARE stmt FROM @views;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------
-- Table structure for agent
-- ----------------------------
DROP TABLE IF EXISTS `agent`;
CREATE TABLE `agent` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `agent_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_user_id` bigint unsigned DEFAULT NULL,
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `frontend_domain` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `api_domain` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `site_title` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `site_subtitle` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `announcement_title` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `announcement_content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `support_wechat` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `support_qq` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quickstart_api_base_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `allow_self_register` tinyint NOT NULL DEFAULT '1',
  `online_recharge_enabled` smallint NOT NULL DEFAULT '1' COMMENT '代理站在线充值开关 1=开启 0=关闭',
  `theme_config_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_code` (`agent_code`),
  UNIQUE KEY `uk_agent_frontend_domain` (`frontend_domain`),
  UNIQUE KEY `uk_agent_api_domain` (`api_domain`),
  KEY `idx_agent_status` (`status`),
  KEY `idx_agent_owner_user_id` (`owner_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理站点表';

-- ----------------------------
-- Table structure for agent_balance
-- ----------------------------
DROP TABLE IF EXISTS `agent_balance`;
CREATE TABLE `agent_balance` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `balance` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `total_recharged` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `total_allocated` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `total_reclaimed` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_balance_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理余额池';

-- ----------------------------
-- Table structure for agent_balance_record
-- ----------------------------
DROP TABLE IF EXISTS `agent_balance_record`;
CREATE TABLE `agent_balance_record` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `target_user_id` bigint unsigned DEFAULT NULL,
  `related_code_id` bigint unsigned DEFAULT NULL,
  `action_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `change_amount` decimal(12,6) NOT NULL COMMENT '正数流入，负数流出',
  `balance_before` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `balance_after` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_balance_record_agent_id` (`agent_id`),
  KEY `idx_agent_balance_record_target_user_id` (`target_user_id`),
  KEY `idx_agent_balance_record_action_type` (`action_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理余额流水';

-- ----------------------------
-- Table structure for agent_cash_balance
-- ----------------------------
DROP TABLE IF EXISTS `agent_cash_balance`;
CREATE TABLE `agent_cash_balance` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `balance` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '当前可提现人民币余额',
  `total_income` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '累计分润收入',
  `total_withdrawn` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '累计提现',
  `total_adjusted` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '累计人工调账',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_cash_balance_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理人民币现金余额表';

-- ----------------------------
-- Table structure for agent_cash_ledger
-- ----------------------------
DROP TABLE IF EXISTS `agent_cash_ledger`;
CREATE TABLE `agent_cash_ledger` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `order_id` bigint unsigned DEFAULT NULL,
  `withdrawal_id` bigint unsigned DEFAULT NULL,
  `action_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'recharge_commission/withdraw/manual_adjust',
  `change_amount` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '正数=增加，负数=减少',
  `balance_before` decimal(12,2) NOT NULL DEFAULT '0.00',
  `balance_after` decimal(12,2) NOT NULL DEFAULT '0.00',
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_cash_ledger_agent` (`agent_id`),
  KEY `idx_agent_cash_ledger_action` (`action_type`),
  KEY `idx_agent_cash_ledger_order` (`order_id`),
  KEY `idx_agent_cash_ledger_withdrawal` (`withdrawal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理人民币现金流水表';

-- ----------------------------
-- Table structure for agent_cash_withdrawal
-- ----------------------------
DROP TABLE IF EXISTS `agent_cash_withdrawal`;
CREATE TABLE `agent_cash_withdrawal` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `amount` decimal(12,2) NOT NULL DEFAULT '0.00',
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'completed' COMMENT 'completed',
  `transfer_method` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'offline_other' COMMENT 'alipay/wechat/bank/offline_other',
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_cash_withdrawal_agent` (`agent_id`),
  KEY `idx_agent_cash_withdrawal_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理现金提现记录表';

-- ----------------------------
-- Table structure for agent_daily_limit
-- ----------------------------
DROP TABLE IF EXISTS `agent_daily_limit`;
CREATE TABLE `agent_daily_limit` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `resource_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'balance/image_credit/subscription',
  `plan_id` bigint unsigned DEFAULT NULL COMMENT '套餐资源对应 plan_id',
  `plan_id_key` bigint unsigned NOT NULL DEFAULT '0' COMMENT 'NULL plan_id 唯一键占位',
  `daily_limit` decimal(20,6) NOT NULL DEFAULT '0.000000' COMMENT '每日授信额度',
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_daily_limit_resource` (`agent_id`,`resource_type`,`plan_id_key`),
  KEY `idx_agent_daily_limit_agent` (`agent_id`),
  KEY `idx_agent_daily_limit_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理每日授信额度配置';

-- ----------------------------
-- Table structure for agent_daily_limit_usage
-- ----------------------------
DROP TABLE IF EXISTS `agent_daily_limit_usage`;
CREATE TABLE `agent_daily_limit_usage` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `usage_date` date NOT NULL COMMENT '北京时间业务日期',
  `resource_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'balance/image_credit/subscription',
  `plan_id` bigint unsigned DEFAULT NULL,
  `plan_id_key` bigint unsigned NOT NULL DEFAULT '0',
  `used_amount` decimal(20,6) NOT NULL DEFAULT '0.000000' COMMENT '当日已使用授信额度',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_daily_usage_resource` (`agent_id`,`usage_date`,`resource_type`,`plan_id_key`),
  KEY `idx_agent_daily_usage_date` (`usage_date`),
  KEY `idx_agent_daily_usage_agent` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理每日授信额度使用量';

-- ----------------------------
-- Table structure for agent_image_balance
-- ----------------------------
DROP TABLE IF EXISTS `agent_image_balance`;
CREATE TABLE `agent_image_balance` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `balance` decimal(12,3) NOT NULL DEFAULT '0.000',
  `total_recharged` decimal(12,3) NOT NULL DEFAULT '0.000',
  `total_allocated` decimal(12,3) NOT NULL DEFAULT '0.000',
  `total_reclaimed` decimal(12,3) NOT NULL DEFAULT '0.000',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_image_balance_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理图片积分池';

-- ----------------------------
-- Table structure for agent_image_credit_record
-- ----------------------------
DROP TABLE IF EXISTS `agent_image_credit_record`;
CREATE TABLE `agent_image_credit_record` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `target_user_id` bigint unsigned DEFAULT NULL,
  `action_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `change_amount` decimal(12,3) NOT NULL COMMENT '正数流入，负数流出',
  `balance_before` decimal(12,3) NOT NULL DEFAULT '0.000',
  `balance_after` decimal(12,3) NOT NULL DEFAULT '0.000',
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_image_credit_record_agent_id` (`agent_id`),
  KEY `idx_agent_image_credit_record_target_user_id` (`target_user_id`),
  KEY `idx_agent_image_credit_record_action_type` (`action_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理图片积分流水';

-- ----------------------------
-- Table structure for agent_redemption_amount_rule
-- ----------------------------
DROP TABLE IF EXISTS `agent_redemption_amount_rule`;
CREATE TABLE `agent_redemption_amount_rule` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned DEFAULT NULL COMMENT 'NULL=全局规则',
  `amount` decimal(12,6) NOT NULL,
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_redemption_rule_agent_id` (`agent_id`),
  KEY `idx_agent_redemption_rule_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理兑换码固定面额规则';

-- ----------------------------
-- Table structure for agent_settlement_batch
-- ----------------------------
DROP TABLE IF EXISTS `agent_settlement_batch`;
CREATE TABLE `agent_settlement_batch` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `resource_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `plan_id` bigint unsigned DEFAULT NULL,
  `business_start_date` date DEFAULT NULL,
  `business_end_date` date DEFAULT NULL,
  `settled_quantity` decimal(20,6) NOT NULL DEFAULT '0.000000',
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_settlement_batch_agent` (`agent_id`),
  KEY `idx_agent_settlement_batch_resource` (`resource_type`,`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理结算批次';

-- ----------------------------
-- Table structure for agent_settlement_batch_item
-- ----------------------------
DROP TABLE IF EXISTS `agent_settlement_batch_item`;
CREATE TABLE `agent_settlement_batch_item` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `batch_id` bigint unsigned NOT NULL,
  `settlement_record_id` bigint unsigned NOT NULL,
  `settled_quantity` decimal(20,6) NOT NULL DEFAULT '0.000000',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_settlement_batch_item_batch` (`batch_id`),
  KEY `idx_agent_settlement_batch_item_record` (`settlement_record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理结算批次明细';

-- ----------------------------
-- Table structure for agent_settlement_record
-- ----------------------------
DROP TABLE IF EXISTS `agent_settlement_record`;
CREATE TABLE `agent_settlement_record` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `target_user_id` bigint unsigned DEFAULT NULL,
  `business_date` date NOT NULL COMMENT '北京时间业务日期',
  `resource_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'balance/image_credit/subscription/redemption_code',
  `plan_id` bigint unsigned DEFAULT NULL,
  `plan_code_snapshot` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `plan_name_snapshot` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `plan_kind_snapshot` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `duration_days_snapshot` int DEFAULT NULL,
  `quota_metric_snapshot` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quota_value_snapshot` decimal(20,6) DEFAULT NULL,
  `quantity` decimal(20,6) NOT NULL DEFAULT '0.000000' COMMENT '销售数量/金额',
  `settled_quantity` decimal(20,6) NOT NULL DEFAULT '0.000000' COMMENT '已结算数量/金额',
  `unit_amount` decimal(20,6) DEFAULT NULL COMMENT '预留结算单价',
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending/partial/settled/cancelled',
  `source_action` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `related_subscription_id` bigint unsigned DEFAULT NULL,
  `related_balance_record_id` bigint unsigned DEFAULT NULL,
  `related_image_record_id` bigint unsigned DEFAULT NULL,
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `settled_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_settlement_agent_date` (`agent_id`,`business_date`),
  KEY `idx_agent_settlement_status` (`status`),
  KEY `idx_agent_settlement_resource` (`resource_type`,`plan_id`),
  KEY `idx_agent_settlement_user` (`target_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理授信销售待结算记录';

-- ----------------------------
-- Table structure for agent_subscription_inventory
-- ----------------------------
DROP TABLE IF EXISTS `agent_subscription_inventory`;
CREATE TABLE `agent_subscription_inventory` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `plan_id` bigint unsigned NOT NULL,
  `total_granted` int NOT NULL DEFAULT '0',
  `total_used` int NOT NULL DEFAULT '0',
  `remaining_count` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_subscription_inventory` (`agent_id`,`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理套餐库存';

-- ----------------------------
-- Table structure for agent_subscription_inventory_record
-- ----------------------------
DROP TABLE IF EXISTS `agent_subscription_inventory_record`;
CREATE TABLE `agent_subscription_inventory_record` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `agent_id` bigint unsigned NOT NULL,
  `plan_id` bigint unsigned NOT NULL,
  `target_user_id` bigint unsigned DEFAULT NULL,
  `action_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `change_count` int NOT NULL COMMENT '正数增加，负数扣减',
  `remaining_before` int NOT NULL DEFAULT '0',
  `remaining_after` int NOT NULL DEFAULT '0',
  `operator_user_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_agent_subscription_inventory_record_agent_id` (`agent_id`),
  KEY `idx_agent_subscription_inventory_record_plan_id` (`plan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='代理套餐库存流水';

-- ----------------------------
-- Table structure for cache_log
-- ----------------------------
DROP TABLE IF EXISTS `cache_log`;
CREATE TABLE `cache_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `cache_key` varchar(64) NOT NULL COMMENT 'Cache Key (SHA256)',
  `user_id` bigint unsigned NOT NULL COMMENT '用户ID',
  `model` varchar(100) NOT NULL COMMENT '模型名称',
  `prompt_tokens` int NOT NULL COMMENT 'Prompt Tokens',
  `completion_tokens` int NOT NULL COMMENT 'Completion Tokens',
  `cache_status` enum('HIT','MISS','BYPASS') NOT NULL COMMENT '缓存状态',
  `saved_tokens` int DEFAULT '0' COMMENT '节省的 Tokens',
  `saved_cost` decimal(10,6) DEFAULT '0.000000' COMMENT '节省的费用',
  `ttl` int NOT NULL COMMENT '缓存时长（秒）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_cache_key` (`cache_key`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_cache_status` (`cache_status`),
  KEY `idx_user_created` (`user_id`,`created_at`),
  KEY `idx_user_status_created` (`user_id`,`cache_status`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='缓存日志表';

-- ----------------------------
-- Table structure for channel
-- ----------------------------
DROP TABLE IF EXISTS `channel`;
CREATE TABLE `channel` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `base_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `api_key` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '加密存储的API Key',
  `protocol_type` enum('openai','anthropic','google') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'openai',
  `provider_variant` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'default' COMMENT '渠道子类型: default/google-official/google-vertex-image',
  `auth_header_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'x-api-key' COMMENT '鉴权头类型: authorization/x-api-key/anthropic-api-key/x-goog-api-key',
  `priority` int NOT NULL DEFAULT '10' COMMENT '优先级,1=最高',
  `enabled` tinyint NOT NULL DEFAULT '1',
  `health_check_enabled` tinyint NOT NULL DEFAULT '1' COMMENT '是否参与健康监控',
  `is_healthy` tinyint NOT NULL DEFAULT '1',
  `health_score` int NOT NULL DEFAULT '100' COMMENT '健康分0-100',
  `failure_count` int NOT NULL DEFAULT '0' COMMENT '连续失败次数',
  `circuit_breaker_until` datetime DEFAULT NULL COMMENT '熔断截止时间',
  `health_check_model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '健康检查优先使用的模型名',
  `last_health_check_at` datetime DEFAULT NULL,
  `last_success_at` datetime DEFAULT NULL,
  `last_failure_at` datetime DEFAULT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_priority` (`priority`),
  KEY `idx_is_healthy` (`is_healthy`),
  KEY `idx_protocol_type` (`protocol_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='渠道(模型提供商)表';

-- ----------------------------
-- Table structure for consumption_record
-- ----------------------------
DROP TABLE IF EXISTS `consumption_record`;
CREATE TABLE `consumption_record` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `agent_id` bigint unsigned DEFAULT NULL COMMENT '所属代理ID',
  `request_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `input_tokens` int DEFAULT '0',
  `output_tokens` int DEFAULT '0',
  `total_tokens` int DEFAULT '0',
  `billable_input_tokens` int DEFAULT '0',
  `raw_input_tokens` int DEFAULT '0',
  `raw_output_tokens` int DEFAULT '0',
  `raw_total_tokens` int DEFAULT '0',
  `logical_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_cache_read_input_tokens` int NOT NULL DEFAULT '0',
  `billable_cache_read_input_tokens` int DEFAULT '0',
  `upstream_cache_creation_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_prompt_cache_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Anthropic prompt cache status',
  `input_cost` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `cache_read_cost` decimal(12,6) DEFAULT '0.000000',
  `output_cost` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `total_cost` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `input_price_per_million_snapshot` decimal(12,6) DEFAULT '0.000000',
  `output_price_per_million_snapshot` decimal(12,6) DEFAULT '0.000000',
  `price_multiplier_snapshot` decimal(12,6) DEFAULT '1.000000',
  `fast_price_multiplier_snapshot` decimal(12,6) DEFAULT '1.000000',
  `token_multiplier_snapshot` decimal(12,6) DEFAULT '1.000000',
  `balance_before` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `balance_after` decimal(12,6) NOT NULL DEFAULT '0.000000',
  `billing_mode` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'balance=按量计费, subscription=套餐计费',
  `subscription_id` bigint unsigned DEFAULT NULL COMMENT '关联套餐ID',
  `subscription_cycle_id` bigint unsigned DEFAULT NULL COMMENT '关联套餐周期ID',
  `quota_metric` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'total_tokens/cost_usd',
  `quota_consumed_amount` decimal(20,6) DEFAULT '0.000000',
  `quota_limit_snapshot` decimal(20,6) DEFAULT '0.000000',
  `quota_used_after` decimal(20,6) DEFAULT '0.000000',
  `quota_cycle_date` date DEFAULT NULL,
  `service_tier` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Responses service tier snapshot',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_request_id` (`request_id`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_billing_mode` (`billing_mode`),
  KEY `idx_subscription_id` (`subscription_id`),
  KEY `idx_subscription_cycle_id` (`subscription_cycle_id`),
  KEY `idx_consumption_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消费记录表';

-- ----------------------------
-- Table structure for conversation_checkpoint
-- ----------------------------
DROP TABLE IF EXISTS `conversation_checkpoint`;
CREATE TABLE `conversation_checkpoint` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `checkpoint_seq` int NOT NULL DEFAULT '1',
  `source_turn_start` int NOT NULL DEFAULT '0',
  `source_turn_end` int NOT NULL DEFAULT '0',
  `source_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary_token_estimate` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_source_hash` (`source_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话检查点表';

-- ----------------------------
-- Table structure for conversation_session
-- ----------------------------
DROP TABLE IF EXISTS `conversation_session`;
CREATE TABLE `conversation_session` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` bigint unsigned NOT NULL,
  `requested_model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `protocol_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `channel_id` bigint unsigned DEFAULT NULL,
  `system_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tools_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_count` int NOT NULL DEFAULT '0',
  `last_message_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `compression_mode` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'shadow',
  `upstream_session_mode` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'stateless',
  `upstream_session_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `state_version` int NOT NULL DEFAULT '1',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `last_shadow_saved_tokens` int NOT NULL DEFAULT '0',
  `cooldown_until` datetime DEFAULT NULL,
  `last_active_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_user_model_proto` (`user_id`,`requested_model`,`protocol_type`),
  KEY `idx_system_tools_hash` (`system_hash`,`tools_hash`),
  KEY `idx_status` (`status`),
  KEY `idx_last_active_at` (`last_active_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话状态表';

-- ----------------------------
-- Table structure for health_check_log
-- ----------------------------
DROP TABLE IF EXISTS `health_check_log`;
CREATE TABLE `health_check_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` bigint unsigned NOT NULL,
  `channel_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('success','fail') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `response_time_ms` int DEFAULT NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `checked_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_checked_at` (`checked_at`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康检查记录表';

-- ----------------------------
-- Table structure for image_credit_record
-- ----------------------------
DROP TABLE IF EXISTS `image_credit_record`;
CREATE TABLE `image_credit_record` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `agent_id` bigint unsigned DEFAULT NULL COMMENT '所属代理ID',
  `request_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `change_amount` decimal(12,3) NOT NULL COMMENT '正数=充值，负数=扣减',
  `balance_before` decimal(12,3) NOT NULL DEFAULT '0.000',
  `balance_after` decimal(12,3) NOT NULL DEFAULT '0.000',
  `multiplier` decimal(12,3) NOT NULL DEFAULT '1.000',
  `image_size` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Google 生图分辨率档位',
  `action_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'request' COMMENT 'request/recharge/deduct',
  `operator_id` bigint unsigned DEFAULT NULL,
  `remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_image_credit_user_id` (`user_id`),
  KEY `idx_image_credit_request_id` (`request_id`),
  KEY `idx_image_credit_operator_id` (`operator_id`),
  KEY `idx_image_credit_created_at` (`created_at`),
  KEY `idx_image_credit_record_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图片积分流水表';

-- ----------------------------
-- Table structure for model_channel_mapping
-- ----------------------------
DROP TABLE IF EXISTS `model_channel_mapping`;
CREATE TABLE `model_channel_mapping` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `unified_model_id` bigint unsigned NOT NULL,
  `channel_id` bigint unsigned NOT NULL,
  `actual_model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '该渠道中的实际模型名称',
  `enabled` tinyint NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_channel` (`unified_model_id`,`channel_id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型-渠道映射表';

-- ----------------------------
-- Table structure for model_image_resolution_rule
-- ----------------------------
DROP TABLE IF EXISTS `model_image_resolution_rule`;
CREATE TABLE `model_image_resolution_rule` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `unified_model_id` bigint unsigned NOT NULL,
  `resolution_code` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '512/1K/2K/4K',
  `enabled` tinyint NOT NULL DEFAULT '1',
  `credit_cost` decimal(12,3) NOT NULL DEFAULT '1.000' COMMENT '该分辨率对应图片积分',
  `is_default` tinyint NOT NULL DEFAULT '0',
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_resolution_code` (`unified_model_id`,`resolution_code`),
  KEY `idx_resolution_model_id` (`unified_model_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型图片分辨率计费规则表';

-- ----------------------------
-- Table structure for model_override_rule
-- ----------------------------
DROP TABLE IF EXISTS `model_override_rule`;
CREATE TABLE `model_override_rule` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `rule_type` enum('redirect_all','redirect_specific') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_pattern` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '*=所有,或具体模型名',
  `target_unified_model_id` bigint unsigned NOT NULL,
  `enabled` tinyint NOT NULL DEFAULT '1',
  `priority` int NOT NULL DEFAULT '10' COMMENT '规则优先级,数字小优先',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_enabled_priority` (`enabled`,`priority`),
  KEY `idx_source_pattern` (`source_pattern`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型覆盖规则表';

-- ----------------------------
-- Table structure for operation_log
-- ----------------------------
DROP TABLE IF EXISTS `operation_log`;
CREATE TABLE `operation_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned DEFAULT NULL,
  `agent_id` bigint unsigned DEFAULT NULL,
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `action` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `target_id` bigint unsigned DEFAULT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ip_address` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_action` (`action`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_operation_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- ----------------------------
-- Table structure for payment_recharge_order
-- ----------------------------
DROP TABLE IF EXISTS `payment_recharge_order`;
CREATE TABLE `payment_recharge_order` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `order_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payment_channel` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'alipay',
  `recharge_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'balance' COMMENT '充值类型: balance/image_credit',
  `user_id` bigint unsigned NOT NULL,
  `agent_id` bigint unsigned DEFAULT NULL,
  `site_scope` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'platform',
  `source_host` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `return_url_snapshot` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `amount_cny` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '用户支付人民币金额',
  `credited_usd` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '用户到账美元余额',
  `credited_image_credits` decimal(12,3) NOT NULL DEFAULT '0.000' COMMENT '到账图片积分',
  `agent_settlement_rate` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '代理内部结算比例，单位：1 RMB 对应多少 USD',
  `agent_income_cny` decimal(12,2) NOT NULL DEFAULT '0.00' COMMENT '代理现金分润人民币',
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/closed/failed',
  `subject` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `body` text COLLATE utf8mb4_unicode_ci,
  `alipay_trade_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `wechat_transaction_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `wechat_code_url` text COLLATE utf8mb4_unicode_ci,
  `trade_status` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `buyer_logon_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `buyer_user_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `expired_at` datetime DEFAULT NULL,
  `closed_at` datetime DEFAULT NULL,
  `paid_at` datetime DEFAULT NULL,
  `notify_raw` text COLLATE utf8mb4_unicode_ci,
  `return_raw` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_payment_recharge_order_no` (`order_no`),
  UNIQUE KEY `uk_payment_recharge_alipay_trade_no` (`alipay_trade_no`),
  UNIQUE KEY `uk_payment_recharge_wechat_transaction_id` (`wechat_transaction_id`),
  KEY `idx_payment_recharge_type` (`recharge_type`),
  KEY `idx_payment_recharge_user_status` (`user_id`,`status`),
  KEY `idx_payment_recharge_agent_status` (`agent_id`,`status`),
  KEY `idx_payment_recharge_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='在线充值订单表';

-- ----------------------------
-- Table structure for redemption_code
-- ----------------------------
DROP TABLE IF EXISTS `redemption_code`;
CREATE TABLE `redemption_code` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '兑换码',
  `agent_id` bigint unsigned DEFAULT NULL COMMENT '所属代理ID，NULL=平台兑换码',
  `amount` decimal(12,6) NOT NULL COMMENT '兑换金额(美元)',
  `amount_rule_snapshot` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '面额规则快照',
  `code_scope` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'platform' COMMENT 'platform/agent',
  `status` enum('unused','used','expired') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'unused' COMMENT '状态',
  `created_by` bigint unsigned NOT NULL COMMENT '创建者(管理员ID)',
  `used_by` bigint unsigned DEFAULT NULL COMMENT '使用者(用户ID)',
  `used_at` datetime DEFAULT NULL COMMENT '使用时间',
  `expires_at` datetime DEFAULT NULL COMMENT '过期时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`),
  KEY `idx_status` (`status`),
  KEY `idx_created_by` (`created_by`),
  KEY `idx_used_by` (`used_by`),
  KEY `idx_expires_at` (`expires_at`),
  KEY `idx_redemption_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='兑换码表';

-- ----------------------------
-- Table structure for request_cache_summary
-- ----------------------------
DROP TABLE IF EXISTS `request_cache_summary`;
CREATE TABLE `request_cache_summary` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `request_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Request UUID',
  `user_id` bigint unsigned DEFAULT NULL,
  `requested_model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `protocol_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `request_format` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'anthropic_messages/openai_chat/responses',
  `cache_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BYPASS',
  `hit_segment_count` int NOT NULL DEFAULT '0',
  `miss_segment_count` int NOT NULL DEFAULT '0',
  `bypass_segment_count` int NOT NULL DEFAULT '0',
  `reused_tokens` int NOT NULL DEFAULT '0',
  `new_tokens` int NOT NULL DEFAULT '0',
  `reused_chars` int NOT NULL DEFAULT '0',
  `new_chars` int NOT NULL DEFAULT '0',
  `ttl_seconds` int NOT NULL DEFAULT '0',
  `details_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_request_id` (`request_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_requested_model` (`requested_model`),
  KEY `idx_cache_status` (`cache_status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求体缓存摘要表';

-- ----------------------------
-- Table structure for request_log
-- ----------------------------
DROP TABLE IF EXISTS `request_log`;
CREATE TABLE `request_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `request_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'UUID',
  `user_id` bigint unsigned DEFAULT NULL,
  `agent_id` bigint unsigned DEFAULT NULL COMMENT '所属代理ID',
  `user_api_key_id` bigint unsigned DEFAULT NULL,
  `channel_id` bigint unsigned DEFAULT NULL,
  `channel_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `requested_model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户请求的模型名',
  `actual_model` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '实际发送的模型名',
  `protocol_type` enum('openai','anthropic','google') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `request_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'chat',
  `billing_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'token',
  `is_stream` tinyint DEFAULT '0',
  `input_tokens` int DEFAULT '0',
  `output_tokens` int DEFAULT '0',
  `total_tokens` int DEFAULT '0',
  `billable_input_tokens` int DEFAULT '0',
  `raw_input_tokens` int DEFAULT '0',
  `raw_output_tokens` int DEFAULT '0',
  `raw_total_tokens` int DEFAULT '0',
  `image_credits_charged` decimal(12,3) DEFAULT '0.000',
  `image_count` int DEFAULT '0',
  `image_size` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Google 生图分辨率档位',
  `response_time_ms` int DEFAULT NULL,
  `cache_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Request body cache status',
  `cache_hit_segments` int NOT NULL DEFAULT '0',
  `cache_miss_segments` int NOT NULL DEFAULT '0',
  `cache_bypass_segments` int NOT NULL DEFAULT '0',
  `cache_reused_tokens` int NOT NULL DEFAULT '0',
  `cache_new_tokens` int NOT NULL DEFAULT '0',
  `cache_reused_chars` int NOT NULL DEFAULT '0',
  `cache_new_chars` int NOT NULL DEFAULT '0',
  `logical_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_cache_read_input_tokens` int NOT NULL DEFAULT '0',
  `billable_cache_read_input_tokens` int DEFAULT '0',
  `upstream_cache_creation_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_cache_creation_5m_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_cache_creation_1h_input_tokens` int NOT NULL DEFAULT '0',
  `upstream_prompt_cache_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Anthropic prompt cache status',
  `conversation_session_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Conversation session id',
  `conversation_match_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Conversation match status',
  `compression_mode` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Conversation compaction mode',
  `compression_status` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Conversation compaction status',
  `original_estimated_input_tokens` int NOT NULL DEFAULT '0',
  `compressed_estimated_input_tokens` int NOT NULL DEFAULT '0',
  `compression_saved_estimated_tokens` int NOT NULL DEFAULT '0',
  `compression_ratio` decimal(10,4) NOT NULL DEFAULT '0.0000',
  `compression_fallback_reason` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `upstream_session_mode` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Upstream session mode',
  `upstream_session_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Upstream session id',
  `status` enum('success','error','timeout') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'success',
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `client_ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subscription_cycle_id` bigint unsigned DEFAULT NULL,
  `quota_metric` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'total_tokens/cost_usd',
  `quota_consumed_amount` decimal(20,6) DEFAULT '0.000000',
  `quota_limit_snapshot` decimal(20,6) DEFAULT '0.000000',
  `quota_used_after` decimal(20,6) DEFAULT '0.000000',
  `quota_cycle_date` date DEFAULT NULL,
  `service_tier` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Responses service tier snapshot',
  `cache_read_cost` decimal(12,6) DEFAULT '0.000000',
  `input_price_per_million_snapshot` decimal(12,6) DEFAULT '0.000000',
  `output_price_per_million_snapshot` decimal(12,6) DEFAULT '0.000000',
  `price_multiplier_snapshot` decimal(12,6) DEFAULT '1.000000',
  `fast_price_multiplier_snapshot` decimal(12,6) DEFAULT '1.000000',
  `token_multiplier_snapshot` decimal(12,6) DEFAULT '1.000000',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_request_id` (`request_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_status` (`status`),
  KEY `idx_requested_model` (`requested_model`),
  KEY `idx_conversation_session_id` (`conversation_session_id`),
  KEY `idx_request_log_subscription_cycle_id` (`subscription_cycle_id`),
  KEY `idx_agent_id` (`agent_id`),
  KEY `idx_request_log_user_id_id` (`user_id`,`id`),
  KEY `idx_request_log_requested_model_id` (`requested_model`,`id`),
  KEY `idx_request_log_status_id` (`status`,`id`),
  KEY `idx_request_log_created_at_id` (`created_at`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求日志表';

-- ----------------------------
-- Table structure for subscription_plan
-- ----------------------------
DROP TABLE IF EXISTS `subscription_plan`;
CREATE TABLE `subscription_plan` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `plan_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '套餐编码',
  `plan_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '套餐名称',
  `plan_kind` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'unlimited' COMMENT 'unlimited/daily_quota',
  `duration_mode` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'custom',
  `duration_days` int NOT NULL DEFAULT '1',
  `quota_metric` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'total_tokens/cost_usd',
  `quota_value` decimal(20,6) DEFAULT '0.000000',
  `reset_period` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'day',
  `reset_timezone` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Asia/Shanghai',
  `sort_order` int NOT NULL DEFAULT '0',
  `status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT 'active/inactive',
  `description` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_subscription_plan_code` (`plan_code`),
  KEY `idx_subscription_plan_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐模板表';

-- ----------------------------
-- Table structure for subscription_usage_cycle
-- ----------------------------
DROP TABLE IF EXISTS `subscription_usage_cycle`;
CREATE TABLE `subscription_usage_cycle` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `subscription_id` bigint unsigned NOT NULL,
  `user_id` bigint unsigned NOT NULL,
  `cycle_date` date NOT NULL COMMENT '业务日期',
  `cycle_start_at` datetime NOT NULL,
  `cycle_end_at` datetime NOT NULL,
  `quota_metric` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'total_tokens/cost_usd',
  `quota_limit` decimal(20,6) NOT NULL DEFAULT '0.000000',
  `used_amount` decimal(20,6) NOT NULL DEFAULT '0.000000',
  `request_count` int NOT NULL DEFAULT '0',
  `last_request_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_subscription_cycle_date` (`subscription_id`,`cycle_date`),
  KEY `idx_subscription_usage_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='套餐每日额度周期表';

-- ----------------------------
-- Table structure for sys_user
-- ----------------------------
DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user',
  `agent_id` bigint unsigned DEFAULT NULL COMMENT '所属代理ID，NULL=平台直营',
  `created_by_user_id` bigint unsigned DEFAULT NULL COMMENT '创建者用户ID',
  `source_domain` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '注册来源域名',
  `status` tinyint NOT NULL DEFAULT '1' COMMENT '1=正常, 0=禁用',
  `cache_enabled` tinyint NOT NULL DEFAULT '1' COMMENT '是否启用缓存（1=启用，0=禁用）',
  `cache_hit_count` bigint NOT NULL DEFAULT '0' COMMENT '缓存命中次数',
  `cache_saved_tokens` bigint NOT NULL DEFAULT '0' COMMENT '累计节省 Tokens',
  `cache_billing_enabled` tinyint NOT NULL DEFAULT '0' COMMENT '缓存计费开关（1=按缓存后计费，0=按原始计费）',
  `avatar` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_login_at` datetime DEFAULT NULL,
  `last_login_ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `subscription_type` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'balance' COMMENT 'balance=按量计费, unlimited/quota=套餐缓存态',
  `subscription_expires_at` datetime DEFAULT NULL COMMENT '套餐过期时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_email` (`email`),
  KEY `idx_role` (`role`),
  KEY `idx_status` (`status`),
  KEY `idx_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- ----------------------------
-- Table structure for system_config
-- ----------------------------
DROP TABLE IF EXISTS `system_config`;
CREATE TABLE `system_config` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `config_key` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `config_value` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `config_type` enum('string','number','boolean','json') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'string',
  `description` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_config_key` (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ----------------------------
-- Table structure for unified_model
-- ----------------------------
DROP TABLE IF EXISTS `unified_model`;
CREATE TABLE `unified_model` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '统一模型名称,用户请求时使用',
  `display_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model_type` enum('chat','embedding','image') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'chat',
  `protocol_type` enum('openai','anthropic','google') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'openai',
  `max_tokens` int DEFAULT NULL,
  `input_price_per_million` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '每百万输入Token单价(美元)',
  `output_price_per_million` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '每百万输出Token单价(美元)',
  `billing_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'token' COMMENT 'token/image_credit/free',
  `image_credit_multiplier` decimal(12,3) NOT NULL DEFAULT '1.000' COMMENT '图片请求默认扣减倍率',
  `enabled` tinyint NOT NULL DEFAULT '1',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_name` (`model_name`),
  KEY `idx_model_type` (`model_type`),
  KEY `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统一模型定义表';

-- ----------------------------
-- Table structure for user_api_key
-- ----------------------------
DROP TABLE IF EXISTS `user_api_key`;
CREATE TABLE `user_api_key` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Key备注名称',
  `key_prefix` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '展示用前缀,如sk-xxxx',
  `key_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'SHA256哈希',
  `key_full` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '完整API Key明文',
  `status` enum('active','disabled','expired') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `expires_at` datetime DEFAULT NULL,
  `total_requests` bigint unsigned NOT NULL DEFAULT '0',
  `total_tokens` bigint unsigned NOT NULL DEFAULT '0',
  `total_cost` decimal(10,6) NOT NULL DEFAULT '0.000000',
  `last_used_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_key_hash` (`key_hash`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_key_prefix` (`key_prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户API Key表';

-- ----------------------------
-- Table structure for user_balance
-- ----------------------------
DROP TABLE IF EXISTS `user_balance`;
CREATE TABLE `user_balance` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `balance` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '余额(美元)',
  `total_recharged` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '总充值',
  `total_consumed` decimal(12,6) NOT NULL DEFAULT '0.000000' COMMENT '总消费',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户余额表';

-- ----------------------------
-- Table structure for user_image_balance
-- ----------------------------
DROP TABLE IF EXISTS `user_image_balance`;
CREATE TABLE `user_image_balance` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `balance` decimal(12,3) NOT NULL DEFAULT '0.000' COMMENT '图片积分余额',
  `total_recharged` decimal(12,3) NOT NULL DEFAULT '0.000' COMMENT '总充值图片积分',
  `total_consumed` decimal(12,3) NOT NULL DEFAULT '0.000' COMMENT '总消耗图片积分',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_image_balance_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户图片积分余额表';

-- ----------------------------
-- Table structure for user_subscription
-- ----------------------------
DROP TABLE IF EXISTS `user_subscription`;
CREATE TABLE `user_subscription` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint unsigned NOT NULL,
  `agent_id` bigint unsigned DEFAULT NULL COMMENT '所属代理ID',
  `plan_id` bigint unsigned DEFAULT NULL,
  `plan_code_snapshot` varchar(64) DEFAULT NULL COMMENT '套餐编码快照',
  `plan_name` varchar(64) NOT NULL COMMENT '套餐名称',
  `plan_type` varchar(20) NOT NULL COMMENT '套餐类型',
  `plan_kind_snapshot` varchar(20) DEFAULT NULL COMMENT 'unlimited/daily_quota',
  `duration_days_snapshot` int DEFAULT '0',
  `quota_metric` varchar(20) DEFAULT NULL COMMENT 'total_tokens/cost_usd',
  `quota_value` decimal(20,6) DEFAULT '0.000000',
  `reset_period` varchar(20) DEFAULT 'day',
  `reset_timezone` varchar(64) DEFAULT 'Asia/Shanghai',
  `activation_mode` varchar(20) DEFAULT 'append',
  `start_time` datetime NOT NULL COMMENT '开始时间',
  `end_time` datetime NOT NULL COMMENT '结束时间',
  `status` enum('active','expired','cancelled') DEFAULT 'active' COMMENT '状态',
  `created_by` bigint unsigned DEFAULT NULL COMMENT '创建者（管理员ID）',
  `activated_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_end_time` (`end_time`),
  KEY `idx_user_subscription_plan_id` (`plan_id`),
  KEY `idx_user_subscription_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户套餐记录表';

-- ============================================================
-- 最小系统初始化数据
-- ============================================================

-- 默认管理员账户 (密码: admin123)
INSERT INTO `sys_user` (`id`, `username`, `email`, `password_hash`, `role`, `status`)
VALUES (1, 'admin', 'admin@example.com', '$2b$12$12TrajxYt22jQ3fm6EcpLOmOUZNhL676ooVq2ekIlyARRgG78LBUq', 'admin', 1);

-- 管理员余额
INSERT INTO `user_balance` (`user_id`, `balance`, `total_recharged`, `total_consumed`)
VALUES (1, 100.000000, 100.000000, 0.000000);

-- 管理员图片积分余额
INSERT INTO `user_image_balance` (`user_id`, `balance`, `total_recharged`, `total_consumed`)
VALUES (1, 0.000, 0.000, 0.000);

-- 系统配置
INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
('health_check_interval', '300', 'number', '健康检查间隔(秒)'),
('circuit_breaker_threshold', '5', 'number', '熔断器触发阈值(连续失败次数)'),
('circuit_breaker_recovery', '600', 'number', '熔断恢复时间(秒)'),
('health_check_circuit_breaker_threshold', '8', 'number', '健康检查熔断阈值(连续失败次数)'),
('health_check_recent_success_grace_seconds', '1800', 'number', '最近成功请求宽限期(秒)'),
('image_channel_health_check_interval', '21600', 'number', '纯图片渠道健康检查间隔(秒)'),
('health_check_test_message', '你好', 'string', '健康检查测试消息'),
('request_timeout', '30', 'number', '请求超时时间(秒)'),
('max_retry_count', '3', 'number', '最大重试次数'),
('api_base_url', 'https://your-domain.com', 'string', 'API基础地址，用于快速开始页面展示给用户的接入地址'),
('platform_site_name', '小乐AI', 'string', '平台直营站点名称'),
('platform_site_subtitle', '一站式 AI 模型调用服务，让智能触手可及', 'string', '平台直营站点副标题'),
('platform_announcement_title', '平台公告', 'string', '平台直营站点公告标题'),
('platform_announcement_content', '尊敬的用户，欢迎使用 AI 模型中转平台！\n\n请先在管理后台完成渠道和模型配置后再开放给用户使用。', 'string', '平台直营站点公告内容'),
('platform_support_wechat', '', 'string', '平台直营站点微信联系方式'),
('platform_support_qq', '', 'string', '平台直营站点QQ联系方式'),
('platform_allow_register', 'true', 'boolean', '平台直营站点是否允许自助注册'),
('max_context_tokens', '200000', 'number', '最大上下文Token数量限制'),
('max_message_length', '500000', 'number', '单条消息最大字符数限制'),
('price_multiplier', '1.0', 'number', '价格倍率（1.0=原价，2.0=2倍价格）'),
('token_multiplier', '1.0', 'number', 'Token 统计倍率（1.0=原始Token）'),
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

SET FOREIGN_KEY_CHECKS = 1;
