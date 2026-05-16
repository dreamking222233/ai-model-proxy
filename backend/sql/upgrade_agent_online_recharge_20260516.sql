ALTER TABLE agent
    ADD COLUMN online_recharge_enabled SMALLINT NOT NULL DEFAULT 1 COMMENT '代理站在线充值开关 1=开启 0=关闭'
    AFTER allow_self_register;
