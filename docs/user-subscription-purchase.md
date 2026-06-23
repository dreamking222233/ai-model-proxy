# 用户套餐在线选购

## 功能范围

- 管理端 `admin/subscription` 的套餐模板支持配置用户售价、代理拿货价、前台购买开关。
- 用户端 `user/recharge` 支持在余额充值、图片积分充值之外选择套餐购买。
- 线上购买套餐支付成功后统一复用 `SubscriptionService.activate_plan_subscription`，固定以 `append` 方式追加开通。
- 代理名下用户购买套餐后生成代理套餐销售记录，管理员可在 `admin/subscription-sales` 查看并核销，代理可在 `agent/subscription-sales` 查看销售数据。

## 关键业务规则

- 套餐订单金额以后端 `subscription_plan.sale_price_cny` 为准，前端不参与定价。
- 前台只展示 `status=active`、`online_sale_enabled=1`、`sale_price_cny>0` 的套餐。
- 代理用户购买套餐时，套餐必须满足 `agent_cost_price_cny>0` 且 `agent_cost_price_cny<=sale_price_cny`。
- 代理返现金额为 `sale_price_cny - agent_cost_price_cny`，写入订单快照和 `agent_subscription_sale_record`，不复用 `payment_recharge_order.agent_income_cny`。
- 套餐订单不进入余额充值、图片积分充值、代理现金余额自动入账、推广充值返利路径。
- 套餐购买只新增标准 `user_subscription` 记录，不改动请求扣费主链路；系统仍按当前逻辑优先消耗套餐额度，额度不足时扣用户余额，套餐额度和余额都不足时停止使用。
- 限额套餐额度按北京时间 rolling 24 小时刷新，以当前 `user_subscription.start_time` 为刷新锚点；例如 16:30:31 开通，则下一次额度刷新时间为次日 16:30:31，不按自然日 0 点刷新。
- 管理端开通、代理端开通、用户端在线购买都复用同一套 `SubscriptionService` 周期计算和扣费逻辑。
- 用户端 `/user/balance` 套餐卡片展示下次刷新时间，来源于当前周期 `cycle_end_at`。

## 数据表

- `subscription_plan`
  - `sale_price_cny`：用户在线购买售价。
  - `agent_cost_price_cny`：代理拿货价。
  - `online_sale_enabled`：是否允许用户前台购买。
- `payment_recharge_order`
  - `recharge_type=subscription` 表示套餐订单。
  - 保存 `subscription_plan_id`、`subscription_id`、套餐模板快照、售价/拿货价/返现快照。
- `payment_recharge_settlement`
  - `asset_type=subscription` 用于套餐支付回调幂等，避免重复开通。
- `agent_subscription_sale_record`
  - 记录代理用户套餐购买后的待核销返现数据，按 `order_no` 唯一。

## 页面与接口

- 用户端
  - 页面：`/user/recharge`
  - 可购套餐接口：`GET /api/user/payment/subscription-plans`
  - 下单接口：`POST /api/user/payment/recharge-orders`，传 `recharge_type=subscription` 和 `subscription_plan_id`
- 管理端
  - 套餐模板：`/admin/subscription`
  - 代理套餐销售：`/admin/subscription-sales`
  - 接口前缀：`/api/admin/subscription-sales`
- 代理端
  - 套餐销售：`/agent/subscription-sales`
  - 接口前缀：`/api/agent/subscription-sales`

## 上线注意事项

已有数据库需执行：

```sql
source backend/sql/upgrade_user_subscription_purchase_20260622.sql;
```

新环境初始化脚本已同步：

- `backend/sql/init.sql`
- `backend/sql/initData.sql`
- `sql/initData.sql`
