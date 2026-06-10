-- 用户推广链接、注册绑定与充值返现

DROP PROCEDURE IF EXISTS `upgrade_user_promotion_20260610`;

DELIMITER $$

CREATE PROCEDURE `upgrade_user_promotion_20260610`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'user_promotion_link'
    ) THEN
        CREATE TABLE `user_promotion_link` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `user_id` BIGINT UNSIGNED NOT NULL,
            `agent_id` BIGINT UNSIGNED DEFAULT NULL,
            `site_scope` VARCHAR(16) NOT NULL DEFAULT 'platform' COMMENT 'platform/agent',
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'user_promotion_relation'
    ) THEN
        CREATE TABLE `user_promotion_relation` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `promoter_user_id` BIGINT UNSIGNED NOT NULL,
            `promoter_agent_id` BIGINT UNSIGNED DEFAULT NULL,
            `invite_code` VARCHAR(32) NOT NULL,
            `invite_link_id` BIGINT UNSIGNED NOT NULL,
            `invited_user_id` BIGINT UNSIGNED NOT NULL,
            `invited_agent_id` BIGINT UNSIGNED DEFAULT NULL,
            `site_scope` VARCHAR(16) NOT NULL DEFAULT 'platform' COMMENT 'platform/agent',
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
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'user_promotion_reward'
    ) THEN
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
    END IF;
END$$

DELIMITER ;

CALL `upgrade_user_promotion_20260610`();
DROP PROCEDURE IF EXISTS `upgrade_user_promotion_20260610`;
