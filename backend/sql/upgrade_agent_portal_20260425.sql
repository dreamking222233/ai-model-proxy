DROP PROCEDURE IF EXISTS `upgrade_agent_portal_20260425`;

DELIMITER $$

CREATE PROCEDURE `upgrade_agent_portal_20260425`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'user_image_balance'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'image_credit_record'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_balance'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_balance_record'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_image_balance'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_image_credit_record'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_subscription_inventory'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_subscription_inventory_record'
    ) THEN
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'agent_redemption_amount_rule'
    ) THEN
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
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'sys_user' AND column_name = 'role'
    ) THEN
        ALTER TABLE `sys_user` MODIFY COLUMN `role` VARCHAR(16) NOT NULL DEFAULT 'user';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'sys_user' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `sys_user` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID，NULL=平台直营' AFTER `role`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'sys_user' AND index_name = 'idx_agent_id'
    ) THEN
        ALTER TABLE `sys_user` ADD INDEX `idx_agent_id` (`agent_id`);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'sys_user' AND column_name = 'created_by_user_id'
    ) THEN
        ALTER TABLE `sys_user` ADD COLUMN `created_by_user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '创建者用户ID' AFTER `agent_id`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'sys_user' AND column_name = 'source_domain'
    ) THEN
        ALTER TABLE `sys_user` ADD COLUMN `source_domain` VARCHAR(255) DEFAULT NULL COMMENT '注册来源域名' AFTER `created_by_user_id`;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `request_log` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID' AFTER `user_id`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'request_log' AND index_name = 'idx_agent_id'
    ) THEN
        ALTER TABLE `request_log` ADD INDEX `idx_agent_id` (`agent_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'operation_log' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `operation_log` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL AFTER `user_id`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'operation_log' AND index_name = 'idx_operation_agent_id'
    ) THEN
        ALTER TABLE `operation_log` ADD INDEX `idx_operation_agent_id` (`agent_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `consumption_record` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID' AFTER `user_id`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'consumption_record' AND index_name = 'idx_consumption_agent_id'
    ) THEN
        ALTER TABLE `consumption_record` ADD INDEX `idx_consumption_agent_id` (`agent_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'image_credit_record' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `image_credit_record` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID' AFTER `user_id`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'image_credit_record' AND index_name = 'idx_image_credit_record_agent_id'
    ) THEN
        ALTER TABLE `image_credit_record` ADD INDEX `idx_image_credit_record_agent_id` (`agent_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `user_subscription` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID' AFTER `user_id`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'user_subscription' AND index_name = 'idx_user_subscription_agent_id'
    ) THEN
        ALTER TABLE `user_subscription` ADD INDEX `idx_user_subscription_agent_id` (`agent_id`);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'redemption_code' AND column_name = 'agent_id'
    ) THEN
        ALTER TABLE `redemption_code` ADD COLUMN `agent_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '所属代理ID，NULL=平台兑换码' AFTER `code`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'redemption_code' AND index_name = 'idx_redemption_agent_id'
    ) THEN
        ALTER TABLE `redemption_code` ADD INDEX `idx_redemption_agent_id` (`agent_id`);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'redemption_code' AND column_name = 'amount_rule_snapshot'
    ) THEN
        ALTER TABLE `redemption_code` ADD COLUMN `amount_rule_snapshot` VARCHAR(64) DEFAULT NULL COMMENT '面额规则快照' AFTER `amount`;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'redemption_code' AND column_name = 'code_scope'
    ) THEN
        ALTER TABLE `redemption_code` ADD COLUMN `code_scope` VARCHAR(16) NOT NULL DEFAULT 'platform' COMMENT 'platform/agent' AFTER `amount_rule_snapshot`;
    END IF;

    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_site_name', '小乐AI', 'string', '平台直营站点名称'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_site_name');
    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_site_subtitle', '一站式 AI 模型调用服务，让智能触手可及', 'string', '平台直营站点副标题'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_site_subtitle');
    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_announcement_title', '平台公告', 'string', '平台直营站点公告标题'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_announcement_title');
    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_announcement_content', '尊敬的用户，欢迎使用 AI 模型中转平台！\n\n支持Claude和GPT及Gemini全系列模型!\n\n新用户注册，立即赠送 $5 体验额度', 'string', '平台直营站点公告内容'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_announcement_content');
    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_support_wechat', 'Q-Free-M', 'string', '平台直营站点微信联系方式'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_support_wechat');
    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_support_qq', '2222006406', 'string', '平台直营站点QQ联系方式'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_support_qq');
    INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`)
    SELECT 'platform_allow_register', 'true', 'boolean', '平台直营站点是否允许自助注册'
    WHERE NOT EXISTS (SELECT 1 FROM `system_config` WHERE `config_key` = 'platform_allow_register');
END$$

DELIMITER ;

CALL `upgrade_agent_portal_20260425`();

DROP PROCEDURE IF EXISTS `upgrade_agent_portal_20260425`;
