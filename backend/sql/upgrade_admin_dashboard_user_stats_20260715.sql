-- 管理端 Dashboard 今日用户统计查询索引
-- 适用于已部署数据库；重复执行不会重复创建索引。

DROP PROCEDURE IF EXISTS `upgrade_admin_dashboard_user_stats_20260715`;

DELIMITER $$

CREATE PROCEDURE `upgrade_admin_dashboard_user_stats_20260715`()
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'sys_user'
          AND index_name = 'idx_sys_user_role_created_at'
    ) THEN
        ALTER TABLE `sys_user`
            ADD INDEX `idx_sys_user_role_created_at` (`role`, `created_at`);
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'sys_user'
          AND column_name = 'agent_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'sys_user'
          AND index_name = 'idx_sys_user_agent_role_created_at'
    ) THEN
        ALTER TABLE `sys_user`
            ADD INDEX `idx_sys_user_agent_role_created_at` (`agent_id`, `role`, `created_at`);
    END IF;
END$$

DELIMITER ;

CALL `upgrade_admin_dashboard_user_stats_20260715`();
DROP PROCEDURE IF EXISTS `upgrade_admin_dashboard_user_stats_20260715`;
