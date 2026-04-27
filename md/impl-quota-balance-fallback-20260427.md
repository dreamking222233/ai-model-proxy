## 任务概述

本次修复有限额度套餐与余额并存时的计费优先级问题。目标行为调整为：

- 先尝试消耗当日套餐额度
- 套餐额度不足时自动回退到余额计费
- 只有套餐额度不足且余额也不足时，才真正拒绝请求

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_subscription_compatibility.py`
- `md/plan-quota-balance-fallback-20260427.md`

## 核心代码说明

### 1. 请求前预检增加余额补位判断

位置：`backend/app/services/proxy_service.py`

- `_assert_text_request_allowed()` 中，当日额度套餐的预检若抛出 `SUBSCRIPTION_DAILY_QUOTA_EXCEEDED`
- 新增逻辑继续检查 `estimated_total_cost` 对应的余额是否足够
- 若余额足够，则直接放行请求
- 若余额也不足，则返回：
  - `INSUFFICIENT_BALANCE`
  - `当日套餐额度不足，且余额不足以承担本次请求，请充值或缩短上下文后重试`

### 2. 请求后结算支持从套餐回退到余额

位置：`backend/app/services/proxy_service.py`

- `_deduct_balance_and_log()` 中，有限额度套餐先尝试 `consume_quota_after_request()`
- 若实际扣减时因额度不足抛出 `SUBSCRIPTION_DAILY_QUOTA_EXCEEDED`
- 且用户余额足够，则自动改走余额扣费：
  - `billing_mode = balance`
  - `subscription_id = None`
  - 不记录 quota cycle 消耗字段

这样可以覆盖“请求前估算不足”和“请求后实际超出”的两类场景。

### 3. 新增余额辅助方法

- `_get_balance_record()`
- `_balance_decimal()`
- `_can_fallback_to_balance_for_quota_precheck()`
- `_build_quota_balance_insufficient_error()`

用于统一处理余额可用性判断和错误文案。

## 测试验证

执行：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/test/test_subscription_compatibility.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_subscription_compatibility
env PYTHONPATH=backend python -m unittest backend.app.test.test_request_audit_hardening backend.app.test.test_subscription_compatibility backend.app.test.test_channel_health_hardening backend.app.test.test_proxy_channel_failure_hardening
```

结果：

- 语法检查通过
- `test_subscription_compatibility` 通过
- 关联测试共 24 个全部通过

## 风险与边界

- 当前回退余额逻辑只覆盖文本套餐计费链路，不影响无限套餐逻辑。
- 预检是否允许回退，依赖 `estimated_total_cost`；若未来新增特殊计费模型，需要确保预估成本仍然准确。
- 这次未新增数据库变更。
