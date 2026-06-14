-- 平台公告管理

DROP PROCEDURE IF EXISTS `upgrade_platform_announcements_20260614`;

DELIMITER $$

CREATE PROCEDURE `upgrade_platform_announcements_20260614`()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'platform_announcement'
    ) THEN
        CREATE TABLE `platform_announcement` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `title` VARCHAR(128) NOT NULL,
            `content` TEXT NOT NULL,
            `status` VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/published/offline',
            `show_popup` TINYINT NOT NULL DEFAULT 1 COMMENT '1=登录开屏弹出,0=仅公告中心展示',
            `sort_order` INT NOT NULL DEFAULT 0,
            `published_at` DATETIME DEFAULT NULL,
            `created_by_user_id` BIGINT UNSIGNED DEFAULT NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_platform_announcement_status` (`status`),
            KEY `idx_platform_announcement_popup` (`show_popup`),
            KEY `idx_platform_announcement_sort` (`sort_order`, `id`),
            KEY `idx_platform_announcement_creator` (`created_by_user_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='平台公告表';
    END IF;
END$$

DELIMITER ;

CALL `upgrade_platform_announcements_20260614`();
DROP PROCEDURE IF EXISTS `upgrade_platform_announcements_20260614`;
