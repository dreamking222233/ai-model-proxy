## 任务概述

本次在现有支付宝在线充值能力基础上，完成了微信支付 `Native` 扫码支付的第一阶段接入，并同步将支付服务从“支付宝专用实现”重构为“统一充值入口 + 渠道分发”。

本轮已完成：

1. 用户端充值页支持选择 `支付宝` / `微信支付`
2. 后端创建订单请求支持 `payment_channel`
3. 统一订单表支持保存微信交易号与二维码链接
4. 后端支持微信 Native 下单、查单、通知处理骨架
5. 管理端支付明细页改为展示通用“支付流水号”
6. 支付入账逻辑按渠道分支，兼容代理分润与用户余额增加

本轮未完成的最后联调前提：

1. 补齐微信支付平台证书 / 平台公钥
2. 补齐当前系统正式 `notify_url`
3. 用真实商户配置联调微信异步通知

## 文件变更清单

- `backend/app/config.py`
- `backend/app/models/payment.py`
- `backend/app/schemas/payment.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/agent_cash_service.py`
- `backend/app/api/user/payment.py`
- `backend/app/api/public/payment.py`
- `backend/app/test/test_payment_recharge.py`
- `backend/sql/upgrade_alipay_recharge_20260516.sql`
- `backend/sql/upgrade_wechat_native_recharge_20260520.sql`
- `sql/initData.sql`
- `frontend/src/views/user/Recharge.vue`
- `frontend/src/views/admin/PaymentOrderManage.vue`

## 核心实现说明

### 1. 支付服务统一入口

`backend/app/services/payment_service.py`

重构点：

1. 新增 `payment_channel` 规范化与配置校验
2. `create_recharge_order(...)` 支持按渠道创建订单
3. `sync_order_status(...)` 统一查单入口，内部按 `alipay` / `wechat` 分发
4. `_apply_paid_order(...)` 改为按渠道校验并入账

支付宝保留原有能力：

1. 页面支付链接创建
2. 异步通知入账
3. 主动查单同步

微信新增能力：

1. `POST /v3/pay/transactions/native` 下单
2. `GET /v3/pay/transactions/out-trade-no/{out_trade_no}` 查单
3. `POST /api/public/payment/wechat/notify` 通知入口
4. 微信通知签名校验与 APIv3 解密骨架

### 2. 统一订单字段扩展

`payment_recharge_order` 新增：

1. `wechat_transaction_id`
2. `wechat_code_url`

前后端统一增加：

1. `payment_channel_text`
2. `channel_trade_no`

这样管理端和代理端可以统一展示支付流水号，而不再只适配支付宝。

### 3. 用户端充值页改造

`frontend/src/views/user/Recharge.vue`

已支持：

1. 选择支付宝或微信支付
2. 支付宝继续走新窗口支付
3. 微信支付弹出二维码支付框
4. 当前订单自动轮询同步状态
5. 支付成功后自动关闭微信二维码弹窗并刷新余额

### 4. 管理端支付明细页兼容微信

`frontend/src/views/admin/PaymentOrderManage.vue`

已调整：

1. 搜索提示改为“支付流水号”
2. 列名从“支付宝流水号”改为“支付流水号”
3. 支持显示支付宝交易号或微信交易号

## 数据库变更

### 升级老库

执行：

```sql
SOURCE backend/sql/upgrade_wechat_native_recharge_20260520.sql;
```

如果历史库还未执行支付宝在线充值基础升级，先执行：

```sql
SOURCE backend/sql/upgrade_alipay_recharge_20260516.sql;
SOURCE backend/sql/upgrade_wechat_native_recharge_20260520.sql;
```

### 新库初始化

根目录 `sql/initData.sql` 已同步微信支付订单字段。

## 当前仍需补充的配置

后端新增环境变量：

```env
WECHAT_PAY_ENABLED=true
WECHAT_PAY_SERVER_URL=https://api.mch.weixin.qq.com
WECHAT_PAY_APP_ID=
WECHAT_PAY_MCH_ID=
WECHAT_PAY_SERIAL_NO=
WECHAT_PAY_PRIVATE_KEY=
WECHAT_PAY_API_V3_KEY=
WECHAT_PAY_PLATFORM_CERT=
WECHAT_PAY_PLATFORM_PUBLIC_KEY=
WECHAT_PAY_NOTIFY_URL=https://api.xiaoleai.team/api/public/payment/wechat/notify
```

当前你已经提供了一部分：

1. `WECHAT_PAY_APP_ID`
2. `WECHAT_PAY_MCH_ID`
3. `WECHAT_PAY_SERIAL_NO`
4. `WECHAT_PAY_API_V3_KEY`

仍缺：

1. `WECHAT_PAY_PRIVATE_KEY` 当前系统可直接读取的 PEM 内容
2. `WECHAT_PAY_PLATFORM_CERT` 或平台公钥
3. 当前系统实际生效的微信通知地址

## 风险与待优化项

1. 当前前端二维码展示先使用了外部二维码图片服务 `api.qrserver.com`，适合先联调流程，但正式环境建议改为本地二维码库或后端生成二维码图片，避免依赖第三方外网服务。
2. 微信支付平台证书当前按单证书文本实现，后续若要支持证书轮换，建议增加按 `Wechatpay-Serial` 匹配的证书管理。
3. 本轮重点完成 Native 支付，未扩展 JSAPI / H5 / 小程序支付。

## 测试验证

已通过：

```bash
python -m py_compile backend/app/config.py backend/app/models/payment.py backend/app/schemas/payment.py backend/app/api/user/payment.py backend/app/api/public/payment.py backend/app/services/payment_service.py backend/app/services/agent_cash_service.py backend/app/test/test_payment_recharge.py
cd backend && python -m pytest app/test/test_payment_recharge.py
cd frontend && npm run lint -- src/views/user/Recharge.vue src/views/admin/PaymentOrderManage.vue src/api/payment.js
```

测试结果：

1. 支付测试 `8 passed`
2. 前端 lint 通过
