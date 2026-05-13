## Review 结论

本轮“请求必记录 + 套餐请求审计兜底”实现已经达到目标，当前未发现阻塞上线的问题。

## 核心确认

### 1. 请求日志完整性

已通过真实联调确认以下请求都能在请求日志中看到：

- 普通失败请求
- 上游成功但本地记账失败的请求
- 成功请求
- `daily_quota` 前置超额拒绝请求

对应可见范围：

- 用户侧：`/api/user/profile/usage-logs`
- 管理侧：`/api/admin/logs/requests`

### 2. 消费流水完整性

已通过真实联调确认：

- 成功请求会写入 `ConsumptionRecord`
- 用户侧：`/api/user/balance/consumption`
- 管理侧：`/api/admin/logs/consumption`

均能查到成功套餐请求的消费记录。

### 3. 老库兼容

通过真实联调发现，当前本地实际数据库不接受 `sys_user.subscription_type = 'quota'`。

现已调整为：

- `sys_user.subscription_type` 仅作为粗粒度缓存：
  - `balance`
  - `unlimited`
- 精确套餐类型继续由 `subscription_summary.plan_kind` 和 `user_subscription.plan_kind_snapshot` 提供。

这项兼容修复已经在真实的 `daily_quota` 联调里验证通过。

## Findings

### 无阻塞问题

本轮 review 未发现会导致“请求无法审计”或“套餐用户成功请求无法落消费流水”的阻塞性缺陷。

### 残余风险 1

文件：`backend/app/services/subscription_service.py`

- 当前通过把 `sys_user.subscription_type` 统一回写为 `unlimited` 兼容旧库 schema。
- 这不会影响实际套餐判定与计费，但管理员若直接看 `sys_user.subscription_type` 原始字段，会失去对 `daily_quota` / `unlimited` 的细分能力。

建议：

- 后续正式环境建议通过 SQL 升级，把该字段改造成兼容 `quota` 的枚举或更宽的字符串列。

### 残余风险 2

文件：`backend/app/services/proxy_service.py`

- 真实联调已通过，但服务在 `--reload` 模式下热更新时会有短暂连接失败窗口。
- 这属于开发模式现象，不是业务逻辑问题。

建议：

- 正式环境验证时使用非 `--reload` 方式运行，避免把热更新瞬断误判成请求问题。

## 验证

### 自动化

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/services/subscription_service.py backend/app/middleware/cache_middleware.py backend/app/middleware/stream_cache_middleware.py backend/app/test/test_request_audit_hardening.py backend/app/test/test_subscription_compatibility.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_request_audit_hardening backend.app.test.test_subscription_compatibility
```

结果：

- 编译通过
- 13 条单测通过

### 真实联调

已确认：

1. 无限套餐零余额用户成功请求：
- 请求日志可见
- 消费流水可见
- 余额不扣减

2. 日限额套餐超额请求：
- 返回 `SUBSCRIPTION_DAILY_QUOTA_EXCEEDED`
- 请求日志可见

## 结论

当前版本已经满足本轮核心目标：

- 只要用户有请求，就能在请求日志里看到
- 成功请求还能在消费流水里看到
- 套餐用户、老套餐、限额套餐的主要真实链路均已完成联调验证
