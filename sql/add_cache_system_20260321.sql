-- ============================================================
-- AI 请求缓存系统 - 数据库迁移脚本
-- 创建时间: 2026-03-21
-- 说明: 添加缓存日志表和用户缓存统计字段
-- 修复: 优化字段类型和索引
-- ============================================================

-- 1. 创建缓存日志表
CREATE TABLE IF NOT EXISTS `cache_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `cache_key` VARCHAR(64) NOT NULL COMMENT 'Cache Key (SHA256)',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `model` VARCHAR(100) NOT NULL COMMENT '模型名称',
    `prompt_tokens` INT NOT NULL COMMENT 'Prompt Tokens',
    `completion_tokens` INT NOT NULL COMMENT 'Completion Tokens',
    `cache_status` ENUM('HIT', 'MISS', 'BYPASS') NOT NULL COMMENT '缓存状态',
    `saved_tokens` INT DEFAULT 0 COMMENT '节省的 Tokens',
    `saved_cost` DECIMAL(10, 6) DEFAULT 0.00 COMMENT '节省的费用',
    `ttl` INT NOT NULL COMMENT '缓存时长（秒）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_cache_key` (`cache_key`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_cache_status` (`cache_status`),
    KEY `idx_user_created` (`user_id`, `created_at`),
    KEY `idx_user_status_created` (`user_id`, `cache_status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='缓存日志表';

-- 2. 为 sys_user 表添加缓存相关字段
ALTER TABLE `sys_user`
ADD COLUMN `enable_cache` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用缓存（1=启用，0=禁用）' AFTER `status`,
ADD COLUMN `cache_hit_count` BIGINT NOT NULL DEFAULT 0 COMMENT '缓存命中次数' AFTER `enable_cache`,
ADD COLUMN `cache_saved_tokens` BIGINT NOT NULL DEFAULT 0 COMMENT '累计节省 Tokens' AFTER `cache_hit_count`,
ADD COLUMN `cache_billing_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '缓存计费开关（1=按缓存后计费，0=按原始计费）' AFTER `cache_saved_tokens`;

-- 3. 验证表结构
SELECT 'cache_log 表创建成功' AS message;
SELECT 'sys_user 表字段添加成功' AS message;

-- 4. 显示新增字段
SHOW COLUMNS FROM `sys_user` LIKE 'enable_cache';
SHOW COLUMNS FROM `sys_user` LIKE 'cache_hit_count';
SHOW COLUMNS FROM `sys_user` LIKE 'cache_saved_tokens';
SHOW COLUMNS FROM `sys_user` LIKE 'cache_billing_enabled';
