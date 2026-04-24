## 用户原始需求

继续收敛渠道健康问题，并在完成后提交到 GitHub。

## 技术方案设计

### 目标

- 优化请求侧 `_record_channel_failure()` 的失败归因。
- 降低 `429 / timeout / 502/503/504` 这类临时故障对渠道健康状态的误伤。
- 保留对鉴权失败、配置错误、硬故障的正常熔断能力。

### 核心思路

1. 给请求侧失败引入“临时故障 / 通用故障”分类。
2. 对临时故障使用更温和的策略：
   - 更高的熔断阈值
   - 更短的熔断恢复时间
   - 更小的健康分扣减
3. 保持现有数据库结构不变，通过现有 `system_config` 兼容新增配置键。
4. 补测试覆盖分类与阈值行为。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_proxy_channel_failure_hardening.py`
- `md/plan-request-channel-failure-hardening-20260425.md`
- `md/impl-request-channel-failure-hardening-20260425.md`
- `md/review-request-channel-failure-hardening-20260425.md`

## 实施步骤概要

1. 为 `_record_channel_failure()` 增加失败分类和策略解析。
2. 把请求侧渠道失败调用点改为传入原始异常对象。
3. 增加回归测试。
4. 运行验证。
5. 生成 impl/review 文档并提交 GitHub。
