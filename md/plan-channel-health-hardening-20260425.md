## 用户原始需求

继续处理当前系统中渠道健康状态不稳定的问题。现状是多个渠道频繁变为不健康，导致请求侧出现 `NO_CHANNEL` / 503。

## 技术方案设计

### 目标

- 降低定时健康检查对线上可用渠道的误伤概率。
- 保留真实上游故障的自动熔断能力。
- 不引入新的数据库结构变更，优先通过现有字段和配置完成策略收敛。

### 核心思路

1. 区分“真实业务请求失败”和“定时健康检查失败”的处理强度。
2. 健康检查失败时：
   - 若渠道最近存在真实成功请求，则只做轻度扣分，不直接累计到激进熔断。
   - 若渠道长期没有成功流量，则允许健康检查逐步拉低状态，但阈值高于真实请求失败。
3. 健康检查接口返回值改为“持久化后的通道状态”，避免前端把一次探测失败误读为通道已被实际熔断。

### 计划变更

- 在 `health_service.py` 中引入健康检查专用阈值/宽限逻辑：
  - `health_check_circuit_breaker_threshold`
  - `health_check_recent_success_grace_seconds`
- scheduled/manual/startup health check 共用统一落库逻辑，但按来源应用更稳健的失败处理。
- 增加单元测试覆盖：
  - 最近有真实成功的渠道在定时检查失败后仍保持 healthy
  - 长时间无成功的渠道在达到专用阈值后才熔断
  - 返回值中的 `is_healthy` 为持久化状态而非单次 probe 成败

## 涉及文件清单

- `backend/app/services/health_service.py`
- `backend/app/test/test_channel_health_hardening.py`
- `md/plan-channel-health-hardening-20260425.md`
- `md/impl-channel-health-hardening-20260425.md`
- `md/review-channel-health-hardening-20260425.md`

## 实施步骤概要

1. 梳理健康检查与请求失败共用状态字段的现状。
2. 在健康检查落库逻辑中加入宽限与专用阈值。
3. 修正健康检查返回值语义。
4. 增加回归测试。
5. 运行验证并输出 impl/review 文档。
