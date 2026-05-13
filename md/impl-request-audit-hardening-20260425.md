## 任务概述

本轮实现围绕“请求必记录”做了三件事：

1. 修复文本请求成功后，本地计费/记账异常被吞掉的问题。
2. 修复 `subscription_usage_cycle` 并发首次创建时的唯一键竞争恢复。
3. 补齐前置拒绝场景的失败请求日志，确保限额拦截、套餐过期、余额不足等入口阶段失败也能在请求日志中看到。

此外，针对本地实际数据库与旧版 schema 的兼容问题，补充了 `sys_user.subscription_type` 的缓存字段回写兼容逻辑，避免 `daily_quota` 套餐在老库上触发 `DataError`。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/middleware/cache_middleware.py`
- `backend/app/middleware/stream_cache_middleware.py`
- `backend/app/test/test_request_audit_hardening.py`
- `backend/app/test/test_subscription_compatibility.py`
- `md/plan-request-audit-hardening-20260425.md`
- `md/plan-review-request-audit-hardening-20260425.md`

## 核心实现

### 1. 文本请求本地记账失败不再静默吞掉

文件：`backend/app/services/proxy_service.py`

- `_deduct_balance_and_log(...)` 去掉了原先内部统一吞异常的做法，改为向上抛出。
- 新增 `_finalize_successful_text_request(...)`：
  - 统一处理“上游成功后，本地记账/日志入库/套餐消费写入”的成功收尾；
  - 非流式请求在本地记账失败时直接中断成功返回，改为 `TEXT_BILLING_FAILED`；
  - 流式/已输出请求在本地记账失败时，至少补写失败请求日志。

### 2. 增加失败日志兜底

文件：`backend/app/services/proxy_service.py`

- 新增：
  - `_safe_object_id(...)`
  - `_write_minimal_failed_request_log(...)`
  - `_log_pre_request_failure(...)`
  - `_infer_failed_request_billing_type(...)`
- 失败日志逻辑分两层：
  1. 优先写完整 `RequestLog`
  2. 若完整日志写入失败，则写最小失败日志
- 并通过 `request_id` 去重，避免同一请求重复落库。

### 3. 前置拒绝请求也写日志

文件：`backend/app/services/proxy_service.py`

- `handle_openai_request(...)`
- `handle_anthropic_request(...)`
- `handle_responses_request(...)`

这三个入口在“模型解析 / 套餐鉴权 / 长度校验 / 渠道准备”等前置阶段出现异常时，现在都会主动写失败请求日志，然后再把异常返回给调用方。

### 4. 周期并发创建恢复

文件：`backend/app/services/subscription_service.py`

- `_get_or_create_cycle(...)` 增加了嵌套事务和 `IntegrityError` 恢复逻辑。
- 当两个并发请求同时创建同一 `subscription_id + cycle_date` 周期时：
  - 一个请求成功创建；
  - 另一个请求在唯一键冲突后回滚到 savepoint，再重新查询现有周期并继续。

### 5. 老库兼容：`subscription_type` 缓存字段不再写 `quota`

文件：`backend/app/services/subscription_service.py`

- `refresh_user_subscription_state(...)` 现在将所有激活中的套餐统一缓存为 `unlimited`。
- 精确套餐类型仍然由 `user_subscription.plan_kind_snapshot` 和 `subscription_summary.plan_kind` 提供。
- 这样可以兼容旧库中 `sys_user.subscription_type` 只支持 `balance/unlimited` 的情况，避免在 `daily_quota` 套餐用户请求时触发：
  - `Data truncated for column 'subscription_type'`

## 自动化验证

执行：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/services/subscription_service.py backend/app/middleware/cache_middleware.py backend/app/middleware/stream_cache_middleware.py backend/app/test/test_request_audit_hardening.py backend/app/test/test_subscription_compatibility.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_request_audit_hardening backend.app.test.test_subscription_compatibility
```

结果：

- `py_compile` 通过
- 13 条相关单测通过

## 本地真实联调

后端使用：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

### 联调用户 1：无限套餐成功/失败混合验证

- 用户：`audit8085_step`
- 用户 ID：`8`
- API Key ID：`12`
- 套餐：`daily-unlimited`

验证结果：

1. 失败请求可见
- 请求：`POST /v1/chat/completions`
- 结果：`UPSTREAM_INVALID_REQUEST`
- 请求 ID：`cdf0b41f-6b86-4e87-8915-0d5654d25859`
- 用户侧和管理侧请求日志均可见

2. `/v1/responses` 早期本地记账失败可见
- 请求 ID：`7eaef068-6418-474a-b909-92d8e4645a1b`
- 日志中已记录失败原因

3. `/v1/responses` 成功请求可见
- 请求 ID：`98367ed6-77eb-4088-ae26-7d689d257cc4`
- `status=success`
- `request_type=responses`
- `billing_type=subscription`
- 用户侧请求日志可见
- 用户侧 `/api/user/balance/consumption` 与管理侧 `/api/admin/logs/consumption` 均可见对应消费流水

### 联调用户 2：日限额套餐超额前置拦截

- 用户：`quota_case_1`
- 用户 ID：`9`
- API Key ID：`13`
- 套餐：临时测试套餐 `daily-token-10-temp`

验证结果：

- 请求：`POST /v1/responses`
- 结果：`SUBSCRIPTION_DAILY_QUOTA_EXCEEDED`
- 请求 ID：`9d92f8eb-2b13-4a5e-ab16-4103aa3dab54`
- 该请求虽然在前置鉴权阶段即被拒绝，但仍已写入：
  - 用户侧 `/api/user/profile/usage-logs`
  - 管理侧 `/api/admin/logs/requests`

## 当前结论

在当前本地环境下，以下链路已经通过真实验证：

1. 失败请求会写请求日志
2. 成功请求会写请求日志
3. 成功请求会写消费流水
4. 套餐用户成功请求不会扣余额，但会保留消费记录
5. `daily_quota` 超额前置拒绝请求现在也会写请求日志

## 待优化项

1. 本地服务使用 `--reload` 时，热更新窗口内会出现极短暂连接失败，联调时需避免并发脚本一次发太多请求。
2. Redis 当前未启动，日志中的 `cache_details.reason=redis_unavailable` 属于环境现象，不影响本轮套餐与审计逻辑验证。
