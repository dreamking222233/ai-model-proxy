-- ============================================================
-- 代理端完整上线升级 SQL 汇总
-- 文件名：backend/sql/upgrade_agent_release_20260430.sql
-- 用途：与 sql/upgrade_agent_release_20260430.sql 同步保存，便于只部署 backend 目录时执行。
--
-- 推荐执行方式：
--   在项目根目录执行：
--   mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < sql/upgrade_agent_release_20260430.sql
--
-- 如果只上传 backend 目录：
--   cd backend
--   mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < sql/upgrade_agent_release_20260430.sql
--
-- 包含范围：
--   1. 代理端基础表、代理域名、代理用户归属、代理资产池、代理兑换码规则等。
--   2. 代理账号登录与共享 API 域名兼容数据修复。
--   3. 代理端后台套餐发放记录 agent_id 回填。
--   4. 代理结算系统：每日授信额度、额度使用量、待结算销售、结算批次。
--
-- 注意：
--   本文件依赖 MySQL 客户端 SOURCE 命令，各子 SQL 均按幂等方式编写，可重复执行。
-- ============================================================

SOURCE sql/upgrade_agent_portal_20260425.sql;
SOURCE sql/upgrade_agent_account_login_20260426.sql;
SOURCE sql/upgrade_agent_console_enhance_20260427.sql;
SOURCE sql/upgrade_agent_settlement_system_20260430.sql;

SELECT
    'agent release upgrade completed' AS message,
    NOW() AS executed_at;
