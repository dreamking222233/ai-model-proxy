## 用户原始需求

> Plan v2

- 按顺序继续修复当前套餐与请求记账链路的残余风险。
- 优先保证：用户的每一条请求都必须被记录。
- 无论请求成功、失败、未扣费、本地记账失败、套餐超额还是其他异常，只要用户发起了请求，都必须能在：
  - `admin/logs`
  - `/user/balance`
 看到对应记录。

## 技术方案设计

### 核心目标

1. 请求审计优先于扣费结果。
- 任何进入代理主链路的请求，都必须有稳定的 `RequestLog` 记录。
- 即使本地扣费、套餐入账、周期写入失败，也不能出现“用户实际请求了，但两端页面完全看不到”的情况。

2. 成功请求的本地记账异常不能再被吞掉。
- 对“上游成功，但本地扣费/套餐入账失败”的情况，系统应中断成功返回，改为失败返回。
- 同时必须落库一条可见的失败请求日志，错误信息要能在管理端和用户端看到。

3. `daily_quota` 周期并发创建需要可恢复。
- 解决 `subscription_usage_cycle` 首次创建时的唯一键竞争。
- 避免并发请求导致周期未写入、额度未累计、日志丢失或本地事务失败。

4. 用户端请求页面的数据口径与日志口径一致。
- 经核对，当前用户侧“账单与明细”页面实际走 `/api/user/profile/usage-logs`，底层依赖 `RequestLog`，不是 `ConsumptionRecord`。
- 因此本轮优先级应是：保证 `RequestLog` 在所有请求路径下稳定可见。
- `ConsumptionRecord` 仍用于余额/套餐/成本结算，但不再作为“用户是否能看到请求”的唯一依据。

### 方案要点

1. 拆分“请求成功返回前”的本地落库逻辑
- 将现有 `_deduct_balance_and_log(...)` 改造成“失败可抛出”的严格流程。
- 其内部不再吞掉异常。
- 由调用方接住异常，统一转成“本地记账失败”的失败响应，并补写失败 `RequestLog`。

2. 增加兜底请求日志写入能力
- 提供面向“上游已成功但本地入账失败”与“流式收尾记账失败”的 fallback 日志方法。
- 该方法只保证 `RequestLog` 最小字段必落库：
  - `request_id`
  - `user_id`
  - `requested_model`
  - `channel`
  - `status`
  - `error_message`
  - `response_time_ms`
  - 必要的 billing / quota 快照
- 且必须避免与已有成功日志重复插入同一个 `request_id`。
- 若消费记录无法写入，至少要有 `RequestLog`。

3. 周期创建并发修复
- 为 `_get_or_create_cycle(...)` 增加唯一键冲突恢复逻辑。
- 若 `flush()` 因唯一键冲突失败，则回滚到安全点并重新查询当日周期。

4. 全链路覆盖范围
- Responses 非流式
- OpenAI 非流式 / 流式
- Anthropic 非流式 / 流式
- Responses websocket 同样依赖 `_deduct_balance_and_log(...)`，需要纳入修复
- 图片链路只做审计核对，避免回退现有“本地记账失败则中断返回”的策略

5. 测试覆盖
- 上游成功但 `_deduct_balance_and_log(...)` 失败时：
  - 返回失败
  - `RequestLog` 落库
  - 用户端 usage logs 可见
- `subscription_usage_cycle` 并发创建冲突时可恢复
- 原有成功请求、失败请求、老套餐兼容逻辑不回退

## 影响范围分析

### 涉及模块

- 请求代理主链路
- 套餐周期写入
- 请求日志查询
- 用户端请求明细展示依赖链路

### 关键文件

- `backend/app/services/proxy_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/log_service.py`
- `backend/app/api/user/profile.py`
- `backend/app/test/test_subscription_compatibility.py`
- 可能新增专项测试文件

### 风险点

1. 流式请求在已经向客户端输出部分内容后，再发现本地记账失败，无法完全回滚上游输出。
2. `RequestLog.request_id` 唯一约束下，fallback 日志必须是“仅在主日志未落库时补写”，否则会产生唯一键冲突。
3. `subscription_usage_cycle` 唯一键竞争修复需要正确处理事务状态，避免一次冲突把同一事务上的其他写入也带崩。
4. 非流式主链路应尽量对齐图片链路：上游成功但本地记账失败时，直接中断返回。

## To-Do

1. 确认 `/user/balance` 页面实际展示依赖 `RequestLog`，以 `RequestLog` 完整性为第一目标。
2. 审查 `_deduct_balance_and_log(...)` 的所有调用点，区分非流式、流式、websocket。
3. 设计“本地记账失败 fallback 请求日志”最小字段集合与去重策略。
4. 让 `_deduct_balance_and_log(...)` 不再吞掉异常。
5. 为非流式主链路接入“本地记账失败 -> 兜底失败日志 -> 返回失败”的统一处理。
6. 为流式 / websocket 主链路接入“收尾记账失败 -> 兜底失败日志”的统一处理。
7. 修复 `subscription_usage_cycle` 并发创建冲突恢复。
8. 补充回归测试，覆盖请求必记录、非流式本地记账失败、流式收尾记账失败、周期并发创建。
9. 运行相关测试。
10. 编写 impl 文档。
11. 执行 review，并根据 review 收尾。
