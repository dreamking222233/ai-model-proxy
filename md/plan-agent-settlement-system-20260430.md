# 代理端结算系统实施方案

> 版本：v2  
> 修订依据：`md/plan-review-agent-settlement-system-20260430.md`  
> v2 结论：可以进入实施。v2 已补齐授信事务一致性、并发锁顺序、授信资源回收口径、部分结算审计、北京时间业务日期字段。

## 1. 用户原始需求

当前代理端必须由管理端先给代理充值余额、图片积分和套餐库存，代理才能给自己的下游用户分配资源，效率较低。

需要新增一套代理结算系统：

- 代理可以直接给自己的用户充值余额或开通套餐，并产生记账销售记录。
- 管理端新增结算页面，可以按天查看每个代理的销售情况。
- 管理端可根据销售记录找代理结算，可以分批结算，例如卖出 5 张月卡，只结算 4 张，剩余 1 张保持未结算。
- 管理端可为每个代理设置每天可支配额度，包含：
  - 按量付费余额额度。
  - 各套餐模板的每日可发放数量，例如无限日卡、无限周卡、无限月卡、畅享日卡、畅享周卡等。
  - 图片积分每日额度需要兼容现有代理用户管理能力。
- 每日额度按北京时间自然日刷新，当天额度使用完后，代理不能继续给用户充值或开通对应套餐。
- 管理端页面需要同时看到：
  - 新结算系统产生的待结算销售。
  - 旧体系下代理已经存在的余额、图片积分、套餐库存及其消耗情况，避免误判。

## 2. 现有逻辑梳理

### 2.1 代理资产池

现有代理资产由 `backend/app/services/agent_asset_service.py` 统一处理：

- `grant_user_balance`
  - 校验用户属于当前代理。
  - 扣减 `agent_balance.balance`。
  - 增加 `user_balance.balance`。
  - 写入 `agent_balance_record` 和 `consumption_record`。
- `reclaim_user_balance`
  - 从用户余额扣回。
  - 增加代理余额池。
- `grant_user_image_credits`
  - 扣减 `agent_image_balance.balance`。
  - 增加 `user_image_balance.balance`。
  - 写入 `agent_image_credit_record` 和 `image_credit_record`。
- `grant_user_subscription`
  - 扣减 `agent_subscription_inventory.remaining_count`。
  - 调用 `SubscriptionService.activate_plan_subscription` 开通用户套餐。
  - 写入 `agent_subscription_inventory_record`。

### 2.2 代理端接口

代理端当前入口：

- `POST /api/agent/users/recharge`
- `POST /api/agent/users/deduct`
- `POST /api/agent/users/image-credits/recharge`
- `POST /api/agent/users/image-credits/deduct`
- `POST /api/agent/subscription/grant`
- `POST /api/agent/redemption`

这些接口都默认依赖代理已有资产池或固定兑换码面额规则。

### 2.3 管理端接口与页面

管理端已有：

- `admin/agents`：代理管理。
- `admin/agent-assets`：代理余额、图片积分、套餐库存、兑换码固定面额规则。
- `admin/agent-logs`：代理请求日志。

当前没有结算页面、每日额度配置页面、待结算销售流水。

## 3. 核心设计原则

### 3.1 不破坏旧资产池

旧资产池继续保留：

- 已经充值给代理的余额、图片积分、套餐库存仍可使用。
- 旧资产池的使用不重复生成待结算应收账款，因为这部分可以理解为已预充值、已结算资源。
- 管理端新页面会显示旧资产池余额和库存，辅助判断代理当前资源情况。

### 3.2 新增授信结算模式

当代理执行资源发放时：

- 若对应旧资产池足够，优先走旧逻辑。
- 若旧资产池不足或套餐库存为 0，则整笔尝试走新增的“每日授信额度”。
- 授信额度可用时，资源直接发放给终端用户，同时写入待结算销售记录。
- 授信额度不足时，返回中文错误提示，例如 `当前代理今日余额额度不足，请联系管理员调整额度或次日再试`。

首版明确不做混合拆分：

- 旧资产池足额：整笔走旧资产池，不产生结算记录。
- 旧资产池不足：整笔走授信额度，不扣旧资产池，产生一条结算记录。
- 例：代理旧余额剩余 3 美元，给用户充值 5 美元，系统不会扣 3 美元旧余额再授信 2 美元，而是整笔 5 美元走授信。

### 3.3 每日额度只限制授信发放

每日额度用于防止代理无预充值资产时无限透支：

- 按量余额：按美元金额控制。
- 图片积分：按积分数量控制。
- 套餐：按 `plan_id` 控制每日可发放数量。
- 额度按北京时间自然日统计，使用 `Asia/Shanghai`。

旧资产池消耗本质是已预充值资源，第一版不纳入每日授信额度消耗，避免代理旧余额充足时被日限额误拦截。

无额度配置规则：

- 没有 `agent_daily_limit` 记录：不可授信。
- `status=disabled`：不可授信。
- `status=active` 且 `daily_limit > 0`：可授信。
- `daily_limit=0` 允许保存，含义是今日额度为 0，不允许授信。

### 3.4 支持部分结算

销售记录本身支持部分结算：

- 余额、图片积分：记录 `quantity`，可结算任意小于等于剩余数量的金额/积分。
- 套餐：记录 `quantity=1`，也可以聚合结算，例如管理员在汇总行结算 4 张月卡，系统会按最早记录依次划掉 4 条或部分数量。
- 结算后更新 `settled_quantity` 和 `status`。
- 每次结算写入独立结算批次和批次明细，保留谁在什么时间结算了多少。
- 状态：
  - `pending`：未结算。
  - `partial`：部分结算。
  - `settled`：已结算。
  - `cancelled`：已作废，第一版预留，不默认开放。

并发结算规则：

- 后端对待结算记录按 `created_at asc, id asc` 加 `FOR UPDATE`。
- 管理员请求结算数量大于剩余未结算数量时，直接拒绝并返回中文错误。
- 多个管理员同时结算同一代理、同一套餐时，后到事务必须基于最新 `settled_quantity` 再判断。

### 3.5 授信资源回收规则

首版不允许授信资源通过普通扣减转换成旧资产池：

- 代理给用户的授信余额、授信图片积分如果后续需要扣回，第一版不自动回收到 `agent_balance` 或 `agent_image_balance`。
- 普通扣减接口仍可扣减用户余额/图片积分，但不会因为授信销售记录而自动冲销待结算。
- 为避免财务漏洞，若系统检测到该代理存在未结算授信记录，用户扣减时不增加旧资产池，只写用户侧扣减流水和操作日志。
- 后续如需退款冲销，可新增 `cancelled` 或负向结算记录。

## 4. 数据库设计

### 4.1 `agent_daily_limit`

用途：管理端配置每个代理每天可透支发放的资源额度。

字段：

- `id`
- `agent_id`
- `resource_type`
  - `balance`
  - `image_credit`
  - `subscription`
- `plan_id`
  - 仅 `subscription` 使用。
  - `balance` / `image_credit` 为空。
- `daily_limit`
  - 金额、积分或套餐份数。
- `status`
  - `active`
  - `disabled`
- `created_at`
- `updated_at`

约束：

- 唯一键：`agent_id + resource_type + plan_id_key`
- MySQL 对 NULL 唯一键不严格，因此使用生成列或额外 `plan_id_key` 规避。

### 4.2 `agent_daily_limit_usage`

用途：记录代理某个北京时间日期的额度使用量。

字段：

- `id`
- `agent_id`
- `usage_date`
- `resource_type`
- `plan_id`
- `used_amount`
- `created_at`
- `updated_at`

约束：

- 唯一键：`agent_id + usage_date + resource_type + plan_id_key`

并发控制：

- 发放时先锁 `agent_daily_limit` 配置行。
- 持有配置行锁后，再查询或创建当天 `agent_daily_limit_usage`。
- 在同一事务内检查并累加 `used_amount`。
- `AgentSettlementService` 不自行 commit，由 `AgentAssetService` 统一提交。

### 4.3 `agent_settlement_record`

用途：记录代理授信发放产生的待结算销售明细。

字段：

- `id`
- `agent_id`
- `target_user_id`
- `business_date`
  - 按 `Asia/Shanghai` 生成。
  - 管理端按天统计优先使用该字段。
- `resource_type`
  - `balance`
  - `image_credit`
  - `subscription`
  - `redemption_code` 第一版预留，当前仍优先沿用余额池生成兑换码。
- `plan_id`
- `plan_code_snapshot`
- `plan_name_snapshot`
- `plan_kind_snapshot`
- `duration_days_snapshot`
- `quota_metric_snapshot`
- `quota_value_snapshot`
- `quantity`
  - 余额：美元金额。
  - 图片积分：积分数。
  - 套餐：份数，通常为 1。
- `settled_quantity`
- `unit_amount`
  - 第一版可为空，后续如需要记录代理结算单价可补。
- `status`
  - `pending`
  - `partial`
  - `settled`
  - `cancelled`
- `source_action`
  - `grant_user_balance`
  - `grant_user_image_credit`
  - `grant_user_subscription`
- `related_subscription_id`
- `related_balance_record_id`
- `related_image_record_id`
- `operator_user_id`
- `remark`
- `created_at`
- `settled_at`
- `updated_at`

索引：

- `idx_agent_settlement_agent_date`
- `idx_agent_settlement_status`
- `idx_agent_settlement_resource`
- `idx_agent_settlement_user`

### 4.4 `agent_settlement_batch`

用途：记录一次管理端结算动作。

字段：

- `id`
- `agent_id`
- `resource_type`
- `plan_id`
- `business_start_date`
- `business_end_date`
- `settled_quantity`
- `operator_user_id`
- `remark`
- `created_at`

### 4.5 `agent_settlement_batch_item`

用途：记录一次结算动作实际划掉了哪些销售记录。

字段：

- `id`
- `batch_id`
- `settlement_record_id`
- `settled_quantity`
- `created_at`

### 4.6 对现有表的影响

不修改现有历史表语义：

- `agent_balance`
- `agent_image_balance`
- `agent_subscription_inventory`
- `agent_balance_record`
- `agent_image_credit_record`
- `agent_subscription_inventory_record`
- `user_subscription`
- `consumption_record`

授信发放时仍要写用户侧流水，保证用户端账单、请求扣费、套餐状态与现有逻辑一致。

## 5. 后端设计

### 5.1 新增模型

文件：`backend/app/models/agent.py`

新增 ORM：

- `AgentDailyLimit`
- `AgentDailyLimitUsage`
- `AgentSettlementRecord`
- `AgentSettlementBatch`
- `AgentSettlementBatchItem`

### 5.2 新增 Schema

文件：`backend/app/schemas/agent.py`

新增请求模型：

- `AgentDailyLimitUpsert`
- `AgentDailyLimitBatchUpsert`
- `AgentSettlementRecordQuery`
- `AgentSettlementSettleRequest`

### 5.3 新增服务

文件：`backend/app/services/agent_settlement_service.py`

核心方法：

- `get_today_date()`
- `list_limits(agent_id)`
- `upsert_limit(agent_id, resource_type, daily_limit, plan_id)`
- `check_and_consume_daily_limit(agent_id, resource_type, amount, plan_id)`
- `create_settlement_record(...)`
- `list_admin_settlement_summary(date_range, agent_id, status)`
- `list_admin_settlement_records(date_range, agent_id, resource_type, status)`
- `settle_records(agent_id, resource_type, quantity, plan_id, start_date, end_date, remark)`
- `get_agent_today_quota_summary(agent_id)`

并发策略：

- `check_and_consume_daily_limit` 先锁定 `agent_daily_limit` 配置行。
- 持有配置行锁后，再锁定或创建 `agent_daily_limit_usage`。
- 检查 `used_amount + amount <= daily_limit` 后再写入使用量。
- 所有方法默认不提交事务，由调用方统一 `commit`。

### 5.4 改造 `AgentAssetService`

改造点：

- `grant_user_balance`
  - 若 `agent_balance.balance >= amount`，保留现有预充值逻辑。
  - 若不足，走授信逻辑：
    - 检查 `balance` 今日额度。
    - 直接给用户余额充值。
    - 写 `agent_settlement_record`。
    - 写 `consumption_record`，保持用户账单可见。
    - 不扣 `agent_balance.balance`。
- `grant_user_image_credits`
  - 同余额逻辑。
- `grant_user_subscription`
  - 若库存足够，保留现有库存逻辑。
  - 若库存不足，走授信逻辑：
    - 检查 `subscription + plan_id` 今日额度。
    - 调用 `SubscriptionService.activate_plan_subscription`。
    - 写 `agent_settlement_record`。
    - 不扣库存。

扣减改造：

- `reclaim_user_balance` 和 `reclaim_user_image_credits` 增加授信安全判断。
- 如果代理存在未结算授信余额/图片积分记录，扣减用户资源时不增加旧代理资产池，避免授信资源变成预充值资产。
- 用户侧流水仍照常记录，操作日志仍照常记录。

### 5.5 管理端 API

文件：`backend/app/api/admin/agent.py`

新增接口：

- `GET /api/admin/agents/{agent_id}/daily-limits`
- `PUT /api/admin/agents/{agent_id}/daily-limits`
- `GET /api/admin/agents/settlements/summary`
- `GET /api/admin/agents/settlements/records`
- `POST /api/admin/agents/settlements/settle`

注意路由顺序：

- 固定路径必须放在 `/{agent_id}` 前，避免 `settlements` 被解析为 `agent_id`。

### 5.6 代理端 API

文件：`backend/app/api/agent/stats.py`

扩展 `GET /api/agent/stats/workbench`：

- 返回今日授信额度。
- 返回今日已用额度。
- 返回今日剩余额度。
- 返回当前待结算数量/金额。

## 6. 前端设计

### 6.1 管理端新增菜单

文件：

- `frontend/src/router/index.js`
- `frontend/src/layout/AdminLayout.vue`

新增页面：

- 路由：`/admin/agent-settlements`
- 标题：`代理结算`

### 6.2 管理端新增页面

文件：`frontend/src/views/admin/AgentSettlementManage.vue`

页面区域：

- 筛选区：
  - 日期范围。
  - 代理。
  - 状态。
  - 资源类型。
- 今日/区间汇总：
  - 每个代理余额销售额。
  - 图片积分销售量。
  - 每个套餐销售数量。
  - 已结算、未结算、部分结算。
  - 旧资产池余额、图片积分余额、套餐库存剩余。
- 明细表：
  - 代理。
  - 用户。
  - 资源类型。
  - 套餐。
  - 数量。
  - 已结算数量。
  - 未结算数量。
  - 状态。
  - 创建时间。
- 结算操作：
  - 对选中代理、资源类型、套餐、日期区间进行结算。
  - 输入结算数量。
  - 后端按最早待结算记录依次划掉。

### 6.3 管理端代理资产页增强

文件：`frontend/src/views/admin/AgentAssetManage.vue`

新增“每日授信额度”区域：

- 余额每日额度。
- 图片积分每日额度。
- 每个套餐模板每日可发放数量。
- 可启用/停用对应额度。

### 6.4 代理端工作台增强

文件：`frontend/src/views/agent/Workbench.vue`

新增展示：

- 今日余额授信额度、已用、剩余。
- 今日图片积分授信额度、已用、剩余。
- 每个套餐今日可发放数量、已用、剩余。
- 当前待结算销售合计。

### 6.5 代理端用户和套餐页面文案

文件：

- `frontend/src/views/agent/UserManage.vue`
- `frontend/src/views/agent/SubscriptionManage.vue`

调整文案：

- 原“余额不足/库存不足”场景会自动尝试今日授信额度。
- 若授信额度不足，显示后端中文错误。

## 7. SQL 文件

新增：

- `sql/upgrade_agent_settlement_system_20260430.sql`
- `backend/sql/upgrade_agent_settlement_system_20260430.sql`

同步更新：

- `sql/init.sql`
- `backend/sql/init.sql`

## 8. 详细 Tasks

### 阶段 1：方案与数据库

- [x] 创建 Plan 文档。
- [x] 使用 `codex exec` 评估 Plan。
- [x] 根据评估结果修订 Plan v2。
- [x] 新增升级 SQL。
- [x] 更新两个 init.sql。

### 阶段 2：后端模型与服务

- [x] 在 `agent.py` 新增结算相关 ORM。
- [x] 在 `schemas/agent.py` 新增请求 Schema。
- [x] 新增 `agent_settlement_service.py`。
- [x] 实现每日额度查询、配置、消耗。
- [x] 实现销售记录创建与结算划账。
- [x] 改造 `AgentAssetService`，支持资产池不足时走授信。
- [x] 扩展代理工作台统计。
- [x] 新增管理端结算 API。

### 阶段 3：前端管理端

- [x] `frontend/src/api/agent.js` 新增结算和每日额度接口。
- [x] `AgentAssetManage.vue` 增加每日额度配置。
- [x] 新增 `AgentSettlementManage.vue`。
- [x] 新增管理端路由和菜单。

### 阶段 4：前端代理端

- [x] `Workbench.vue` 展示今日授信额度和待结算。
- [x] `SubscriptionManage.vue` 将库存文案调整为“库存/今日额度”。
- [x] `UserManage.vue` 保持操作入口，补充额度不足提示文案。

### 阶段 5：验证与文档

- [x] Python 编译检查。
- [x] 前端构建或静态检查。
- [x] 创建实施记录 `md/impl-agent-settlement-system-20260430.md`。
- [x] 创建 Review 文档 `md/review-agent-settlement-system-20260430.md`。
- [x] 根据 Review 修复问题。

## 9. 风险与处理

### 9.1 重复结算风险

风险：旧资产池消耗与新增授信销售混在一起，可能重复向代理结算。

处理：

- 只有授信发放才写 `agent_settlement_record`。
- 旧资产池消耗只在结算页面作为“预充值资产消耗/剩余”展示，不进入待结算。

### 9.2 并发超额风险

风险：代理并发给多个用户充值，可能超过每日额度。

处理：

- `agent_daily_limit_usage` 行级锁。
- 唯一键防止重复创建当日用量行。
- 检查和累加在同一个事务内完成。

### 9.3 套餐部分结算风险

风险：管理员按数量结算时需要准确划掉最早未结算记录。

处理：

- 后端按 `created_at asc, id asc` 顺序消费 `remaining_quantity`。
- 每条记录有 `quantity` 和 `settled_quantity`。
- 更新状态为 `partial` 或 `settled`。

### 9.4 回收/扣减与结算关系

v2 首版规则：

- 代理从用户扣减余额或图片积分时，如果该代理没有未结算授信记录，沿用旧逻辑回收到代理资产池。
- 如果该代理存在未结算授信余额/图片积分记录，扣减只影响用户资源，不增加代理旧资产池。
- 已产生的授信销售记录不自动冲销，避免用户扣减被误用为财务退款。
- 如果确实需要退款冲销，后续新增 `cancelled` 或反向结算记录。

### 9.5 兑换码关系

第一版规则：

- 代理兑换码仍使用代理余额池生成，保持现有“生成时冻结余额，删除未使用兑换码退回”的逻辑。
- 如果需要“无余额也可用今日余额额度生成兑换码”，可在第二阶段将 `redemption_code` 纳入结算资源。

## 10. 可行性初评

技术上可行，主要原因：

- 当前代理所有资源发放都集中在 `AgentAssetService`，改造入口清晰。
- 用户余额、图片积分、套餐开通已有成熟逻辑，新结算系统只需要在代理资产不足时替换“扣代理资产”为“扣今日额度 + 写销售记录”。
- 管理端已有代理、套餐、资产页面，可以直接扩展 API 与页面。
- 现有日志表都带 `agent_id`，便于结算页面展示历史上下文。

需要重点控制：

- 数据库唯一键和行级锁，防止并发超额。
- 路由顺序，避免 `/settlements/*` 被 `/{agent_id}` 捕获。
- 旧资产池与新授信记录的财务口径必须在 UI 上分开展示。
