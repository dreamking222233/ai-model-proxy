# 代理充值结算比例调整 Plan 评估

## 评估结论

方案整体可行，核心判断正确：当前余额/图片积分充值的代理分润由后端配置倍率驱动，管理端和代理端展示读取落库字段，不需要在前端重算。将代理结算倍率从 `10` 改为 `7`，能够影响后续新创建订单的 `agent_settlement_rate` 与 `agent_income_cny`，支付成功后也会按新订单金额进入代理现金余额。

但方案需要补强一个关键边界：`/user/recharge` 页面同时支持套餐购买，套餐返现不走 `RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE`，而是走 `subscription_plan.sale_price_cny - subscription_plan.agent_cost_price_cny`。如果业务口径中的“代理比例改为 1:7”也要求覆盖套餐，需要另行调整套餐模板的代理拿货价或设计按比例自动计算套餐拿货价的规则；仅执行当前 plan 不会改变套餐返现。

## 方案完整性检查

### 已覆盖且合理

1. 余额充值计算链路定位准确：
   - `PaymentService._calculate_amounts()`
   - `RECHARGE_USER_CNY_TO_USD_RATE`
   - `RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE`
   - `payment_recharge_order.agent_settlement_rate`
   - `payment_recharge_order.agent_income_cny`

2. 代理现金入账链路定位准确：
   - 支付成功后 `_apply_paid_order()`
   - `_credit_agent_cash_balance()`
   - `agent_cash_balance`
   - `agent_cash_ledger`

3. 前端影响判断合理：
   - `/admin/payment-orders`
   - `/admin/agent-cash`
   - `/agent/payments`
   这些页面主要展示后端返回的落库金额，不需要单独改分润公式。

4. 历史订单不重算的原则合理。历史订单已快照 `agent_settlement_rate` 和 `agent_income_cny`，并可能已经影响提现余额与流水，直接批量回改有财务风险。

5. 运行配置风险识别正确。`backend/.env` 会覆盖 `config.py` 默认值，生产环境也可能通过环境变量覆盖，必须同步改运行配置并重启服务。

## 需要修订或明确的点

### 1. 套餐返现边界必须写入最终方案

当前套餐购买逻辑：

```text
subscription_agent_rebate_cny = sale_price_cny - agent_cost_price_cny
```

因此：

- 修改 `RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE=7` 不会影响套餐订单。
- 修改 `RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE=7` 也不会影响套餐订单。
- 套餐订单支付成功后生成 `agent_subscription_sale_record`，状态为 `pending`，由管理端线下返现后核销。
- 套餐返现当前不会自动进入 `agent_cash_balance`。

建议将 plan 中“套餐在线购买不走该倍率，本次不调整套餐逻辑”提升为明确验收边界，并补充一个反例：

```text
套餐售价 100 元，代理拿货价 70 元，则代理返现仍为 30 元；
不会因为代理余额结算倍率从 1:10 改为 1:7 而变成 28.57 元。
```

业务已确认：套餐不用修改。

### 2. 图片积分同步按 1:7 调整

业务已确认：图片积分也按照 `1:7` 比例调整，即同步修改 `RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE=7`。

```text
用户充值 100 元图片积分
用户到账 500 积分
代理成本 500 / 7 = 71.43 元
代理分润 28.57 元
```

### 3. `backend/.env` 修改方式需要谨慎

Plan 中列出 `backend/.env` 是正确的，但 `.env` 通常不应作为提交内容。实施时应区分：

- `backend/app/config.py`：代码默认值，可提交。
- `backend/.env`：本地或服务器运行配置，作为部署操作记录，不建议提交。
- 生产环境变量：需要在部署文档或实施记录中列出实际变更项。

### 4. 接口级验证可能受支付配置限制

本地 `ALIPAY_ENABLED` / `WECHAT_PAY_ENABLED` 可能未开启，完整创建订单可能会触发支付配置校验或调用支付 SDK。建议把验证拆成两层：

1. 函数级验证 `_calculate_amounts()`，不依赖支付渠道。
2. 在支付配置可用环境中再验证完整下单与支付入账。

若本地支付配置不可用，不能因此阻塞本次比例公式验证。

### 5. 增加 `agent_settlement_rate` 展示不是必须，但有审计价值

Plan 判断“不是必要条件”是对的。考虑到历史订单 1:10、新订单 1:7 会同时存在，建议作为低风险增强项：

- 管理端 `/admin/payment-orders` 可增加“代理结算倍率”列。
- 代理端可不展示，避免引起终端运营解释成本。

这不是实施 1:7 的阻塞项。

## 技术可行性

可行。

原因：

1. 现有实现已经把用户到账倍率和代理结算倍率配置化。
2. 订单创建时会快照倍率和分润金额，新旧规则可以自然共存。
3. 支付成功入账读取的是订单 `agent_income_cny`，无需改支付回调核心流程。
4. 管理端和代理端统计均按落库金额聚合，无需重建统计模型。
5. 不涉及数据库结构变更，风险主要集中在配置发布和业务边界确认。

## 风险评估

### 中风险：套餐口径误解

如果业务认为“用户通过 `/user/recharge` 的所有支付都应按 1:7 计算代理收益”，当前方案不足，因为套餐返现不会变化。

处理建议：

- 明确本次只调整余额/图片积分按量充值。
- 若套餐也要按比例调整，另做套餐拿货价方案。

### 中风险：生产环境配置未同步

如果只改 `config.py`，但生产环境变量仍为 `10`，实际运行仍按 `1:10`。

处理建议：

- 实施记录必须列出生产需要修改的环境变量。
- 重启后通过日志或临时检查接口/函数验证实际配置值。

### 低风险：历史订单展示差异

历史订单 50% 分润，新订单约 28.57% 分润，会在同一列表中并存。

处理建议：

- 保留订单快照。
- 必要时增加 `agent_settlement_rate` 展示或导出字段。

### 低风险：金额四舍五入差异

当前按人民币 2 位小数四舍五入，`100 元` 分润为 `28.57 元`。批量对账时可能存在分级订单逐笔四舍五入造成的总额尾差。

处理建议：

- 验收以订单级 `agent_income_cny` 为准。
- 汇总金额按订单落库值求和。

## 建议修订后的实施优先级

1. 按已确认业务范围实施：
   - 余额充值改为 1:7。
   - 图片积分充值同步改为 1:7。
   - 套餐购买本次不调整。

2. 修改配置：
   - `backend/app/config.py`
   - 运行环境变量或 `backend/.env`

3. 验证公式：
   - 代理用户余额充值 100 元，分润 28.57 元。
   - 代理用户图片积分充值 100 元，若同步调整，分润 28.57 元。
   - 直营网用户分润 0。
   - 套餐返现仍等于售价减拿货价。

4. 验证展示：
   - `/admin/payment-orders`
   - `/admin/agent-cash`
   - `/agent/payments`
   - `/admin/agent-subscription-sales` 和 `/agent/subscription-sales` 保持套餐返现逻辑不变。

## 最终判断

当前 plan 可以进入实施。业务边界已明确：套餐不受 1:7 影响，图片积分同步按 1:7 调整。方案风险较低，不需要数据库结构调整，实施复杂度为中小型。
