## 任务概述

本次针对渠道健康状态不稳定导致的误熔断问题做策略收敛，目标是在不改数据库结构的前提下，降低定时健康检查对线上通道的误伤概率，同时保留真实请求故障的自动熔断能力。

## 文件变更清单

- `backend/app/services/health_service.py`
- `backend/app/test/test_channel_health_hardening.py`
- `md/plan-channel-health-hardening-20260425.md`

## 核心代码说明

### 1. 健康检查使用更温和的熔断阈值

位置：`backend/app/services/health_service.py`

- 新增：
  - `health_check_circuit_breaker_threshold`
  - `health_check_recent_success_grace_seconds`
- 若未显式配置，则默认：
  - 健康检查熔断阈值 = `max(8, 请求熔断阈值 + 3)`
  - 最近真实成功宽限 = `1800` 秒

这样可以避免健康检查和真实请求共用同一个激进阈值，减少定时探测导致的误熔断。

### 2. 最近存在真实成功请求时，失败探测只做轻度降级

- `_check_and_record()` 在健康检查失败时，先判断 `last_success_at` 是否落在宽限期内。
- 若存在最近真实成功：
  - 仅降低 `health_score`
  - 不增加 `failure_count`
  - 不直接触发 `circuit_breaker`
- 若不存在最近真实成功：
  - 才累计 `failure_count`
  - 达到健康检查专用阈值后再熔断

### 3. `last_success_at` 不再被健康检查成功覆盖

- 健康检查成功仍会恢复：
  - `is_healthy`
  - `failure_count`
  - `health_score`
  - `circuit_breaker_until`
- 但不会再改写 `last_success_at`

这样 `last_success_at` 语义收敛为“最近一次真实请求成功”，不再混入探测成功时间。

### 4. 健康检查接口返回值修正

- 之前 `is_healthy` 直接返回单次 probe 是否成功。
- 现在改为返回持久化后的真实通道状态。
- 额外增加：
  - `probe_success`
  - `check_source`
  - `recent_live_success`

这样前端或管理端可以区分“这次探测失败”与“通道已经被系统判定为不健康”。

## 测试验证

执行：

```bash
python -m py_compile backend/app/services/health_service.py backend/app/test/test_channel_health_hardening.py
env PYTHONPATH=backend python -m unittest backend.app.test.test_channel_health_hardening backend.app.test.test_request_audit_hardening backend.app.test.test_subscription_compatibility
```

结果：

- 语法检查通过
- 17 个测试全部通过
- Redis 本地未启动，仅出现缓存降级日志，不影响本次验证

## 风险与边界

- 本次未改请求侧 `_record_channel_failure()` 的判定口径，真实业务失败仍然会按原逻辑较快触发熔断。
- 如果上游本身持续不稳定，`NO_CHANNEL` 仍可能出现；本次主要解决的是“健康检查过于敏感导致的误杀”。
- `last_success_at` 的语义已变为真实请求成功时间，若前端页面之前把它当成“最近一次健康检查成功”展示，需要以后按 `last_health_check_at` 区分理解。
