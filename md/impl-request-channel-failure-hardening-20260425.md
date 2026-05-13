## 任务概述

本次继续收敛渠道健康问题，重点优化请求侧 `_record_channel_failure()` 的失败归因，避免 `429 / timeout / 502/503/504` 这类临时性故障被当成硬故障快速打死整条通道。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_proxy_channel_failure_hardening.py`
- `backend/app/test/test_request_audit_hardening.py`
- `backend/app/services/model_service.py`
- `backend/app/core/exceptions.py`
- `md/plan-request-channel-failure-hardening-20260425.md`

## 核心代码说明

### 1. 请求侧失败分类

位置：`backend/app/services/proxy_service.py`

- 新增 `_classify_channel_failure()`：
  - `httpx.TimeoutException`
  - `httpx.ConnectError`
  - `httpx.ReadError`
  - `httpx.RemoteProtocolError`
  - `httpx.NetworkError`
  - `HTTP 408/409/425/429/500/502/503/504`
- 以上统一归类为 `transient`
- 其余按 `generic` 处理

### 2. 临时性故障使用更温和的熔断策略

- 新增 `_resolve_channel_failure_policy()`
- `transient` 默认策略：
  - 阈值：`max(7, base_threshold + 2)`
  - 恢复时间：`min(base_recovery, 120s)`
  - 健康分扣减：`5`
- `generic` 维持原策略：
  - 阈值：`base_threshold`
  - 恢复时间：`base_recovery`
  - 健康分扣减：`10`

### 3. 渠道失败调用点传入原始异常

- 所有 `_record_channel_failure()` 调用点已改为显式传入 `exc / e / stream_error`
- 这样请求侧不会再丢失失败上下文，能按异常类型执行对应策略

### 4. 用户可见异常中文化

为了满足“尽量返回中文错误”的要求，本次顺手补了用户可见错误本地化：

- `proxy_service.py`
  - 新增 `_localize_user_visible_error_text()`
  - 统一本地化常见英文报错，如：
    - `No available channel for this model`
    - `All channels failed: ...`
    - `Upstream returned HTTP ...`
    - `Model 'xxx' not found`
    - `Missing required field: ...`
- `model_service.py`
  - 将 `Model not found` 等直接改为中文
- `core/exceptions.py`
  - 统一异常兜底信息、422 参数校验信息改为中文

## 测试验证

执行：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/services/model_service.py backend/app/core/exceptions.py backend/app/test/test_proxy_channel_failure_hardening.py backend/app/test/test_request_audit_hardening.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_proxy_channel_failure_hardening backend.app.test.test_channel_health_hardening backend.app.test.test_request_audit_hardening backend.app.test.test_subscription_compatibility
```

结果：

- 语法检查通过
- 21 个测试全部通过
- Redis 本地未启动，仅出现缓存降级日志，不影响本次验证

## 风险与边界

- 本次主要解决“临时故障过度惩罚”和“英文错误直出”的问题。
- 对于上游原样返回的复杂英文业务报错，当前只做了常见模式本地化，不做机器翻译。
- `datetime.utcnow()` 的弃用告警仍存在，但不影响本次功能正确性。
