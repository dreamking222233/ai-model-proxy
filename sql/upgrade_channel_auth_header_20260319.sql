-- 添加渠道认证 header 类型支持
-- 日期：2026-03-19
-- 用途：支持不同渠道使用不同的认证 header（x-api-key, anthropic-api-key, authorization）

-- 1. 添加 auth_header_type 字段
ALTER TABLE `channel`
ADD COLUMN `auth_header_type` VARCHAR(32) NOT NULL DEFAULT 'x-api-key'
COMMENT 'Auth header type: x-api-key, anthropic-api-key, authorization'
AFTER `protocol_type`;

-- 2. 如果已经有 Anthropic 协议的渠道，可能需要修改为 anthropic-api-key
-- （根据实际情况调整，这里提供示例）
-- UPDATE `channel` SET `auth_header_type` = 'anthropic-api-key' WHERE `protocol_type` = 'anthropic';
