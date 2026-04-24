## 用户原始需求

- 按当前系统对套餐逻辑进行风险修正。
- 优先优化两项问题：
  1. `daily_quota` 套餐改成真正的硬限额，避免单次请求直接冲破当日额度。
  2. 鉴权层不要只依赖 `sys_user.subscription_type / subscription_expires_at`，应先回查真实套餐状态，并允许套餐到期后按余额兜底。
- 完成后输出详细 tasks，并做一次 review。

## 技术方案设计

### 目标

- 让“是否能发起文本请求”的判定只依赖真实有效套餐记录和余额，不依赖可能滞后的用户缓存字段。
- 让 `daily_quota` 套餐在请求前和请求后都具备额度约束，减少超额穿透。
- 保持老无限套餐、模板套餐、历史脏数据兼容逻辑不回退。

### 方案要点

1. 统一鉴权入口的套餐状态刷新
- 在 `verify_api_key_from_headers` 中调用 `SubscriptionService.refresh_user_subscription_state(...)`。
- 若有有效套餐：
  - 返回刷新后的用户对象；
  - 不再因旧缓存字段错误拦截。
- 若无有效套餐：
  - 若余额大于 0，允许继续请求；
  - 若存在过期套餐缓存但无余额，抛出 `SUBSCRIPTION_EXPIRED`；
  - 否则抛出 `INSUFFICIENT_BALANCE`。

2. 将 `daily_quota` 改为硬限额判定
- 扩展 `SubscriptionService.check_quota_before_request(...)` 支持传入本次请求预估消耗。
- 对按 Token 限额的套餐，优先用请求体内可得到的 `max_tokens` / `max_completion_tokens` / `thinking.budget_tokens` 等信息估算最坏输出，再结合输入 token 进行前置拦截。
- 对按金额限额的套餐，若无法在请求前精确估算，则继续采用“已用额度判定 + 请求后记账”，并在文档中明确这是当前保守实现。
- 新增请求后兜底校验：若前置无法完全覆盖，也要在消费阶段检测是否超过剩余额度，并拒绝写入超额消费。

3. 并发与一致性
- `check_quota_before_request(...)` 在需要做硬限额判断时使用行锁读取当日周期。
- `consume_quota_after_request(...)` 在写入前再次校验 `used_amount + consumed_amount <= quota_limit`，避免并发穿透。

4. 测试覆盖
- 鉴权层：
  - 过期套餐且余额充足时允许请求。
  - 过期套餐且无余额时返回 `SUBSCRIPTION_EXPIRED`。
- 限额层：
  - 单次请求预测消耗超过剩余额度时被拒绝。
  - 并发/后置写入超过额度时被拒绝。
  - 老无限套餐不受影响。

## 涉及文件清单

- `backend/app/core/dependencies.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/test/test_subscription_compatibility.py`
- `md/impl-subscription-entitlement-hardening-20260425.md`
- `md/review-subscription-entitlement-hardening-20260425.md`

## 详细 Tasks

1. 调整鉴权层套餐判定，优先刷新真实套餐状态。
2. 在鉴权层补上“无有效套餐时按余额兜底”的兼容逻辑。
3. 为文本请求增加可复用的前置额度估算方法。
4. 扩展 `check_quota_before_request(...)` 支持基于本次请求预估值进行硬限额拦截。
5. 扩展 `consume_quota_after_request(...)` 的后置校验，防止并发或预测不足导致超额写入。
6. 在文本请求入口把预估信息传入套餐前置校验。
7. 为鉴权层与套餐硬限额补齐回归测试。
8. 运行相关单测并记录结果。
9. 编写 impl 文档。
10. 基于 plan/impl 执行一次 review，并按结果确认是否需要收尾修正。
