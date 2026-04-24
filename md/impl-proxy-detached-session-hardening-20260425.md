## 任务概述

本次针对代理服务中的 detached ORM 风险做补强，重点修复图片计费/日志路径中“进入新数据库会话后继续直接访问旧 ORM 对象属性”的问题，并同步复核用户反馈中的其余问题是否仍然成立。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_request_audit_hardening.py`
- `md/plan-proxy-detached-session-hardening-20260425.md`

## 核心代码说明

### 1. 图片计费日志链路改为快照式取值

位置：`backend/app/services/proxy_service.py`

- 在 `_deduct_image_credits_and_log()` 进入 `session_scope()` 之前，先通过 `_safe_object_id()` 取出：
  - `user_id`
  - `api_key_id`
  - `channel_id`
- 同时快照 `channel_name`、`protocol_type`，避免新会话中访问已脱离会话的 `channel` 属性。
- 若用户或渠道主键无法安全提取，直接抛出 `IMAGE_BILLING_FAILED`，避免误写脏日志。

### 2. 增加 detached 对象回归测试

位置：`backend/app/test/test_request_audit_hardening.py`

- 新增 `_DetachedAttrObject`，其 `id/name/protocol_type` 直接访问会抛错，用于模拟 detached ORM。
- 新增测试 `test_deduct_image_credits_and_log_uses_safe_snapshots_for_detached_objects`
  - 验证图片记账走安全快照值
  - 验证成功写入 `RequestLog`
  - 验证 API Key 使用统计仍能更新

## 对用户反馈问题的复核结论

### 1. `proxy_service.py:7147` 会话生命周期错误

- 该问题在当前主线中已基本修复。
- 文本请求主链路已使用 `_safe_object_id(user)` 与 `fresh_user.id`。
- 本次额外补齐了图片计费日志路径的同类风险，避免留下旁路缺口。

### 2. 渠道健康状态不稳定

- 当前代码中，请求失败与健康检查失败都会累计 `failure_count`。
- 熔断阈值默认来自 `circuit_breaker_threshold`，默认值为 `5`。
- 若上游真实抖动，或健康检查频率较高，会较快触发 `is_healthy=0` 与 `NO_CHANNEL`。
- 该问题当前更偏向“策略敏感度偏高/上游稳定性不足”，本次未直接改阈值，避免误伤现网流量调度。

### 3. `subscription_type` 字段类型

- 当前代码模型已改为 `String(16)`。
- 仓库已存在兼容 SQL：
  - `sql/upgrade_sys_user_subscription_type_compat_20260425.sql`
  - `backend/sql/upgrade_sys_user_subscription_type_compat_20260425.sql`
- 该项不属于本次新增修改。

## 测试验证

执行：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/test/test_request_audit_hardening.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_request_audit_hardening backend.app.test.test_subscription_compatibility
```

结果：

- 语法检查通过
- 14 个测试全部通过
- Redis 本地未启动，仅出现缓存降级日志，不影响本次验证
