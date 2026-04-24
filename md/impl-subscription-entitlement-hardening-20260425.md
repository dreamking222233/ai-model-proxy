## 任务概述

本次实现针对套餐链路的两类核心风险做了收敛：

1. 修正鉴权层只依赖 `sys_user.subscription_type / subscription_expires_at` 的过期判断，避免用户套餐刚过期或缓存滞后时，被提前拦截成 `SUBSCRIPTION_EXPIRED`，无法进入后续余额兜底逻辑。
2. 将 `daily_quota` 套餐从“仅判断当前已用是否达上限”改为“请求前预测 + 请求后兜底”双重限制，降低单次请求直接冲破当日额度的风险。

## 文件变更清单

- `backend/app/core/dependencies.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/test/test_subscription_compatibility.py`
- `md/plan-subscription-entitlement-hardening-20260425.md`

## 核心代码说明

### 1. 鉴权层先刷新真实套餐状态

文件：`backend/app/core/dependencies.py`

- 将原先基于 `user.subscription_type in {"unlimited", "quota"}` 且直接比较 `subscription_expires_at` 的拦截逻辑，调整为：
  - 先调用 `SubscriptionService.refresh_user_subscription_state(...)`；
  - 再提交并刷新 `user`；
  - 不在鉴权层直接根据旧缓存抛 `SUBSCRIPTION_EXPIRED`。

这样做的目的，是把“是否允许继续请求”留给真正的请求计费链路判断：
- 有有效套餐：继续走套餐；
- 套餐失效但余额充足：允许走余额；
- 套餐失效且余额不足：由请求层抛出明确错误。

### 2. 文本请求增加额度预估

文件：`backend/app/services/proxy_service.py`

- 扩展 `_assert_text_request_allowed(...)`，支持接收 `quota_precheck`。
- 新增：
  - `estimate_openai_input_tokens(...)`
  - `estimate_responses_input_tokens(...)`
  - `_extract_estimated_output_tokens(...)`
  - `_build_text_quota_precheck(...)`

处理方式：
- OpenAI / Anthropic / Responses 三类文本请求在模型解析后，先构造本次请求的额度预估；
- 若是 `daily_quota` 套餐，则把预估值传入 `SubscriptionService.check_quota_before_request(...)`。

当前预估口径：
- Token 套餐：输入 token 粗估 + 请求体中显式输出上限；
- 金额套餐：在存在显式输出上限时，按模型单价估算输入/输出成本。

### 3. `daily_quota` 增加前后双重限额

文件：`backend/app/services/subscription_service.py`

- `check_quota_before_request(...)`
  - 新增 `quota_precheck` 参数；
  - 若能得到和套餐口径一致的预估消耗值，则在读取当日周期后比较“本次预计消耗”与“剩余额度”；
  - 超额时直接拒绝请求。

- `consume_quota_after_request(...)`
  - 在写入 `used_amount` 之前，再次计算 `next_used_amount`；
  - 若 `next_used_amount > quota_limit`，直接抛出 `SUBSCRIPTION_DAILY_QUOTA_EXCEEDED`；
  - 避免并发请求或预估不足时把超额消费写入周期账本。

## 测试验证

执行：

```bash
python -m py_compile backend/app/core/dependencies.py backend/app/services/subscription_service.py backend/app/services/proxy_service.py backend/app/test/test_subscription_compatibility.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_subscription_compatibility
```

结果：

- `py_compile` 通过
- `test_subscription_compatibility` 共 9 条用例全部通过

新增覆盖点：

- 过期缓存套餐在鉴权层不再被提前拦截
- `daily_quota` 请求前预测超额时被拒绝
- `daily_quota` 请求后写入前再次校验，超额时被拒绝

## 待优化项

- 当客户端未显式传 `max_tokens / max_completion_tokens / max_output_tokens` 时，请求前只能基于输入体积做保守估算，最终仍依赖请求后兜底校验。
- 流式请求若在最终记账时发现超额，当前仍属于“上游已执行、系统拒绝记账”的保守策略，后续可再考虑是否对低剩余额度用户提前强制要求显式输出上限。
