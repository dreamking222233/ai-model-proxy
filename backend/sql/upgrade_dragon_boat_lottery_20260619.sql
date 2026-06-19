-- 端午节抽奖活动

DROP PROCEDURE IF EXISTS `upgrade_dragon_boat_lottery_20260619`;

DELIMITER $$

CREATE PROCEDURE `upgrade_dragon_boat_lottery_20260619`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'dragon_boat_lottery_entry'
    ) THEN
        CREATE TABLE `dragon_boat_lottery_entry` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `user_id` BIGINT UNSIGNED NOT NULL,
            `username` VARCHAR(64) NOT NULL,
            `email` VARCHAR(128) NOT NULL,
            `agent_id` BIGINT UNSIGNED DEFAULT NULL,
            `qualification_type` VARCHAR(32) NOT NULL COMMENT 'subscription/recharge/consume',
            `qualification_detail` VARCHAR(255) DEFAULT NULL,
            `total_recharged_snapshot` DECIMAL(12,6) NOT NULL DEFAULT '0.000000',
            `total_consumed_snapshot` DECIMAL(12,6) NOT NULL DEFAULT '0.000000',
            `subscription_id_snapshot` BIGINT UNSIGNED DEFAULT NULL,
            `status` VARCHAR(16) NOT NULL DEFAULT 'registered' COMMENT 'registered/winner',
            `prize_rank` BIGINT UNSIGNED DEFAULT NULL,
            `prize_amount` DECIMAL(12,6) NOT NULL DEFAULT '0.000000',
            `drawn_by_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `drawn_at` DATETIME DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_dragon_boat_lottery_user` (`user_id`),
            UNIQUE KEY `uk_dragon_boat_lottery_prize_rank` (`prize_rank`),
            KEY `idx_dragon_boat_lottery_user_id` (`user_id`),
            KEY `idx_dragon_boat_lottery_agent_id` (`agent_id`),
            KEY `idx_dragon_boat_lottery_status` (`status`),
            KEY `idx_dragon_boat_lottery_prize_rank` (`prize_rank`),
            KEY `idx_dragon_boat_lottery_created_at` (`created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='端午节抽奖报名与中奖记录表';
    END IF;
END$$

DELIMITER ;

CALL `upgrade_dragon_boat_lottery_20260619`();
DROP PROCEDURE IF EXISTS `upgrade_dragon_boat_lottery_20260619`;
