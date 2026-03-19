## Review 结论

本次实现已覆盖需求，且自审中发现的关键边界问题已修复。

## 发现的问题

### 1. 续费后的过期切换风险

- 风险点：用户在首个套餐有效期内续费后，会产生多条连续的套餐记录。若旧套餐到期时直接把用户切回 `balance`，会导致仍在有效期内的新套餐失效，同时影响套餐期间消费归属。
- 处理结果：已在 `backend/app/services/subscription_service.py` 中调整 `check_and_expire_subscriptions`，改为过期时重新计算用户剩余有效套餐，仅在不存在有效套餐时切回 `balance`。

## 验证情况

- `python -m py_compile backend/app/api/admin/subscription.py backend/app/models/log.py backend/app/services/proxy_service.py backend/app/services/subscription_service.py`
  - 通过
- `cd frontend && npm run lint`
  - 通过
  - 存量 warning：`frontend/src/store/index.js:54` `commit` 未使用，本次未引入新的 lint 错误

## 建议

- 现网发布前执行 `sql/upgrade_subscription_usage_tracking_20260319.sql`。
- 发布后可抽样验证以下场景：
  - 新开套餐后列表是否立即可见
  - 套餐用户调用后余额是否保持不变
  - 套餐详情中是否能看到请求数、Token 和理论金额
  - 连续续费用户在旧套餐到期后是否仍保持套餐模式
