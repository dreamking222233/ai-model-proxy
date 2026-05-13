## 评审结论

- 方案整体可行，方向正确。
- 根因判断与代码现状一致：`subscription_usage_cycle` 当前采用 `FOR UPDATE + 读改写`，预检与记账双路径都会放大锁竞争。
- 可以进入实施，但需要先修订 5 个关键点，否则实现细节仍有风险。

## 必须补充的修改点

### 1. 不能只盯 `subscription_usage_cycle`，还要处理 `user_balance` 的提前加锁

- 当前 `ProxyService._deduct_balance_and_log()` 会先执行 `ProxyService._get_balance_record(..., lock=True)`，即使最终走的是套餐记账成功路径，也会先锁住 `user_balance`。
- 如果只优化 `subscription_usage_cycle`，同一用户的并发套餐请求仍可能在余额行锁上串行化。
- 修订建议：
  - `user_balance` 改为按需加锁。
  - 套餐记账成功路径不要提前 `FOR UPDATE` 锁余额。
  - 只有余额扣费路径和套餐超限后的 fallback 路径才锁 `user_balance`。

### 2. 重试位置需要上提到事务边界

- 原方案把“有限重试”放在 `subscription_service` 局部实现，这对 `lock wait timeout / deadlock` 不够稳妥。
- 原因：
  - `consume_quota_after_request()` 运行在 `ProxyService._deduct_balance_and_log()` 的 `session_scope()` 事务里。
  - MySQL 并发异常发生后，当前 Session/事务可能已经处于需要回滚的状态。
  - 在同一个 Session 内原地重试，容易出现事务状态污染。
- 修订建议：
  - `subscription_service` 负责原子更新。
  - `_deduct_balance_and_log()` 在整个本地记账事务层面做有限重试。

### 3. 原子更新条件不能依赖旧快照字段

- 如果周期记录已经存在，但套餐额度、度量字段发生同步修正，单纯用旧行上的 `quota_limit` 参与条件判断存在偏差风险。
- 修订建议：
  - 原子更新时同时写入最新 `quota_metric/quota_limit`。
  - 条件使用本次计算出的额度值，而不是完全依赖旧行快照。

### 4. 预检“无锁化”还不够，最好做到真正只读

- 如果 `check_quota_before_request()` 仍复用 `_get_or_create_cycle()`，即使不加 `FOR UPDATE`，查不到周期时依然会触发插入。
- 这样预检阶段仍然是写路径，每天首个高并发时仍可能在唯一键上竞争。
- 修订建议：
  - 预检使用只读快照查询，不存在周期记录时按 `used_amount=0` 处理。
  - 真正创建周期记录的动作放到请求后记账阶段。

### 5. `rowcount == 0` 不能直接等同于“真实超限”

- 原子更新影响行数为 0，可能是：
  - 并发下额度已被其他请求消耗完
  - 周期记录刚创建冲突后未正确刷新
  - 当前行状态与预期不一致
- 修订建议：
  - 更新失败后先重新读取周期记录再判定。
  - 仅在确认 `used_amount + consumed_amount > quota_limit` 时返回业务超限错误。

## 建议补充测试

- 套餐成功路径不会提前锁 `user_balance`
- 预检阶段只读查询周期快照，不触发周期创建
- 原子更新成功后返回最新 `subscription_cycle_id/quota_used_after`
- 更新影响行数为 0 时，能正确返回超限错误
- 记账事务遇到并发异常时会触发上层有限重试

## 结论

- 方案通过，但应先修订为 Plan v2，再进入编码。
