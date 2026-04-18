ALTER TABLE `channel`
ADD COLUMN `health_check_model` VARCHAR(128) DEFAULT NULL COMMENT '健康检查优先使用的模型名'
AFTER `circuit_breaker_until`;
