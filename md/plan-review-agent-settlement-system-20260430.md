# 代理端结算系统 Plan Review

评估文档：`md/plan-agent-settlement-system-20260430.md`

## 评审结论

方案主方向可行：在旧资产池不足时引入代理每日授信额度，并把授信发放写入待结算销售记录，符合当前 `AgentAssetService` 统一编排代理余额、图片积分、套餐库存的代码结构。

但当前 Plan 不建议直接进入编码。需要先修订为 Plan v2，补齐以下关键约束：

1. 每日额度消耗、用户资源发放、结算记录创建必须在同一事务中完成。
2. 首次创建每日用量行的并发策略需要重写，不能只依赖 `begin_nested()` 兜底。
3. 授信发放后的回收/扣减不能直接回到旧资产池，否则会产生可重复发放但不再结算的资源。
4. 部分结算需要独立结算批次或操作流水，否则多次部分结算不可审计。
5. 按天汇总应使用明确的北京时间业务日期字段，而不是直接依赖数据库 `created_at`。

结论：**有条件可行，需修订后再实施。**

## 方案完整性

### 通过项

- 已覆盖旧资产池、新授信额度、销售记录、管理端结算页、代理工作台展示、升级 SQL 和前端入口。
- 旧资产池优先、新授信兜底的方向合理，可以避免历史代理资产立即迁移。
- 支持 `quantity + settled_quantity + status` 的部分结算模型，能表达未结算、部分结算、已结算。
- 明确兑换码首版仍走旧余额池，避免首期范围过大。

### 需补充

1. **缺少结算操作审计模型**

当前只有 `agent_settlement_record.settled_quantity / settled_at / remark`。如果管理员分 3 次结算同一批记录，后一次会覆盖前一次结算时间和备注，无法追踪每次结算了多少、谁操作、备注是什么。

建议新增：

- `agent_settlement_batch`
  - `id`
  - `agent_id`
  - `resource_type`
  - `plan_id`
  - `settled_quantity`
  - `operator_user_id`
  - `remark`
  - `created_at`
- `agent_settlement_batch_item`
  - `batch_id`
  - `settlement_record_id`
  - `settled_quantity`

如果首版不想加两张表，至少要新增 `agent_settlement_operation`，记录每次结算动作。

2. **缺少业务日期字段**

需求是“按天查看每个代理销售情况”，且每日额度按北京时间刷新。销售记录建议直接写入：

- `business_date DATE NOT NULL`

该字段在发放时按 `Asia/Shanghai` 生成。管理端按天汇总优先使用 `business_date`，不要依赖 `created_at`，避免数据库时区、服务器时区、北京时间边界不一致。

3. **未定义无额度配置时的行为**

需要明确：

- 没有 `agent_daily_limit` 记录时，是额度为 0，还是不允许授信。
- `status=disabled` 是额度为 0，还是不受限制。
- `daily_limit=0` 是否允许保存，含义是什么。

建议首版采用保守规则：

- 无配置：不可授信。
- disabled：不可授信。
- active 且 `daily_limit > 0`：可授信。

4. **旧资产池不足时是否拆分未定义**

例如代理旧余额剩余 3 美元，给用户充值 5 美元。当前 Plan 写的是“不足则走授信逻辑”，这表示整笔 5 美元走授信，旧余额 3 美元不动。

这可以接受，但必须写清楚，避免实现成“旧余额扣 3 + 授信 2”的混合模式。首版建议不要混合拆分，原因是财务口径更清晰：

- 旧资产池足额：整笔走旧资产池，不产生结算记录。
- 旧资产池不足：整笔走授信，产生一条结算记录。

## 技术选型

整体技术选型合理：

- 继续使用 MySQL / InnoDB 行级锁可行。
- SQLAlchemy ORM 新增模型符合当前项目风格。
- 在 `AgentAssetService` 内改造发放链路是正确位置。
- `SubscriptionService.activate_plan_subscription(..., auto_commit=False, agent_id=...)` 已具备被事务编排的基础。

但需要调整两个实现策略。

### 1. 每日额度并发控制

当前 Plan 写法：

- `agent_daily_limit_usage` 使用 `with_for_update()`
- 首次创建 usage 记录时用 `begin_nested()` 处理唯一键竞争

这个策略不够稳。原因是首次没有 usage 行时，多个事务都锁不到行，会同时尝试插入。即使用唯一键处理了插入冲突，也需要谨慎处理 SQLAlchemy session rollback、重新查询锁行、重新校验额度，否则容易出现额度被重复判断或事务状态异常。

建议改为：

1. 先锁定对应的 `agent_daily_limit` 配置行：
   - `SELECT ... FROM agent_daily_limit WHERE agent_id=? AND resource_type=? AND plan_id_key=? AND status='active' FOR UPDATE`
2. 在持有 limit 行锁的同一事务内查询或创建当天 usage 行。
3. 检查 `used_amount + amount <= daily_limit`。
4. 更新 usage。
5. 继续完成用户资源发放和结算记录写入。
6. 最后统一 commit。

这样即使当天 usage 行不存在，也能通过 limit 行串行化同一代理、同一资源、同一套餐的授信发放。

### 2. 服务方法不要各自 commit

当前 `AgentAssetService` 方法内部会 `db.commit()`。新增 `AgentSettlementService.check_and_consume_daily_limit()` 和 `create_settlement_record()` 不能自己提交事务。

授信发放必须是一个原子事务：

- 检查并增加每日用量
- 给用户余额/图片积分/套餐
- 写用户侧流水
- 写 `agent_settlement_record`
- commit

任何一步失败都要整体 rollback。否则可能出现“额度已消耗但用户未到账”或“用户到账但没有结算记录”。

## 实施可行性

可实施，但应调整实施顺序。

建议 Plan v2 的后端顺序改为：

1. 先补 SQL 与 ORM：daily limit、usage、settlement record、settlement batch / operation。
2. 实现 `AgentSettlementService`，但方法默认不 commit，由调用方统一提交。
3. 在 `AgentAssetService` 内封装三条授信发放私有方法：
   - `_grant_user_balance_with_credit_limit`
   - `_grant_user_image_credits_with_credit_limit`
   - `_grant_user_subscription_with_credit_limit`
4. 改造原发放方法：
   - 旧资产池足额走原逻辑。
   - 旧资产池不足整笔走授信逻辑。
5. 增加管理端结算 API，并确保固定路由放在 `/{agent_id}` 前。
6. 增加代理工作台额度汇总。
7. 最后做前端管理端和代理端展示。

测试不能只做 Python 编译和前端构建。至少补充以下用例：

- 旧余额足额时不生成结算记录。
- 旧余额不足时整笔走授信并生成结算记录。
- 每日额度刚好用完时允许，超过 0.000001 美元或 1 积分时拒绝。
- 套餐库存为 0 时走授信，库存大于 0 时不走授信。
- 并发两笔发放总额超过 daily limit 时，只能成功一笔或成功到额度内。
- 管理员部分结算 5 张中的 4 张后，剩余 1 张仍为未结算。
- 两个管理员并发结算同一批记录时不能超结。
- 北京时间 23:59:59 和 00:00:00 的 usage_date / business_date 正确切换。

## 潜在风险

### 1. 高风险：授信回收进入旧资产池

Plan 当前写法是：代理从用户扣减余额或图片积分，仍沿用旧逻辑回收到代理资产池，已产生的授信销售记录不自动冲销。

这会产生严重财务漏洞：

1. 代理无旧余额，通过授信给用户充值 100。
2. 系统生成待结算销售 100。
3. 代理再从用户扣回 100。
4. 旧逻辑把 100 回收到 `agent_balance.balance`。
5. 代理之后可以用这 100 旧余额继续发放，且不会再生成待结算记录。

结果是授信资源被转换成“已预充值资产池”，后续发放绕过结算。

建议首版改为以下任一规则：

- 规则 A：授信产生的用户资源不允许通过普通扣减回收到旧资产池。
- 规则 B：扣减时优先冲销对应授信销售，写负向结算记录，不增加旧资产池。
- 规则 C：回收进入独立的 `agent_credit_reclaimed_balance`，该池再次发放仍必须生成或关联结算记录。

首版最简单稳妥的是规则 A：允许扣减用户资源，但不回收到旧资产池，需要管理员人工处理冲销。

### 2. 高风险：结算并发超结

`settle_records()` 必须对待结算记录按 `created_at asc, id asc` 加 `FOR UPDATE`，并在锁内计算剩余数量和更新状态。

需要明确：

- 如果请求结算数量大于剩余数量，直接拒绝，还是只结算可用数量。
- 多管理员并发结算同一代理、同一套餐时，后到事务必须看到最新 `settled_quantity`。

建议首版选择“请求数量大于剩余数量则拒绝”，避免 UI 与实际结算数量不一致。

### 3. 中高风险：限额配置修改与发放并发

如果管理员在代理发放过程中降低 daily limit，必须定义锁顺序和结果。

建议：

- 发放时锁 `agent_daily_limit` 行。
- 修改额度时也锁同一行。
- 如果新 daily_limit 小于今日 used_amount，允许保存但剩余额度为 0，或禁止保存。建议允许保存并提示“今日已用超过新额度，今日不可继续发放”。

### 4. 中风险：Decimal 精度和字段大小

余额使用 `DECIMAL(12,6)`，图片积分使用 `DECIMAL(12,3)`。新增表需要沿用同等或更高精度：

- balance quantity / used_amount / daily_limit：`DECIMAL(12,6)`
- image_credit quantity / used_amount / daily_limit：`DECIMAL(12,3)`
- subscription quantity / used_amount / daily_limit：可以用 `INT`，如果统一 DECIMAL，则应用层强制整数。

不要用 float 做服务层计算，Schema 可以接收数字，但进入服务层必须转 `Decimal`。

### 5. 中风险：旧资产池展示口径

管理端页面需要同时看新待结算销售和旧资产池情况，但 UI 必须明确分区：

- 新授信销售：待结算、部分结算、已结算。
- 旧资产池：当前余额/图片积分/库存、历史充值、历史发放、历史回收。

不要把旧资产池消耗合并进“销售额”，否则管理员会误以为需要再次结算。

### 6. 中风险：套餐模板快照不完整

`agent_settlement_record` 已规划 `plan_code_snapshot` 和 `plan_name_snapshot`，建议同时保存：

- `plan_kind_snapshot`
- `duration_days_snapshot`
- `quota_metric_snapshot`
- `quota_value_snapshot`

否则后续套餐模板改名或改额度后，历史销售记录很难解释。

## 重点修改建议

Plan v2 建议直接补入以下条款：

1. 授信发放整笔模式：旧资产池足额才走旧资产池，不足则整笔走授信，不做混合拆分。
2. 新增 `business_date` 到 `agent_settlement_record`。
3. 新增结算批次/操作流水表，保留每次部分结算明细。
4. 发放时先锁 `agent_daily_limit` 行，再创建或锁 `agent_daily_limit_usage` 行。
5. 授信发放链路统一一个事务提交，`AgentSettlementService` 不自行 commit。
6. 回收/扣减不能把授信资源转入旧资产池；首版应拒绝或仅做人工冲销。
7. `settle_records()` 对销售记录加 `FOR UPDATE`，超出剩余数量直接拒绝。
8. 明确无额度配置、disabled、daily_limit=0 的业务语义。
9. 补充并发发放、并发结算、北京时间跨日的测试用例。

## 最终建议

当前方案可以作为架构基础，但还没有达到可直接编码的稳定度。建议先修订 `md/plan-agent-settlement-system-20260430.md` 为 v2，优先解决并发一致性、回收口径和结算审计，再进入 SQL 与后端服务实现。
