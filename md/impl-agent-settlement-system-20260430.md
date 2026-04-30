# 代理端结算系统实施记录

## 任务概述

本次新增代理端结算系统，用于解决代理必须先由管理端充值余额和套餐库存后才能给下游用户发放资源的问题。

新逻辑：

- 旧资产池足够时，继续优先使用旧资产池，不产生待结算销售。
- 旧资产池不足时，整笔使用管理员配置的每日授信额度。
- 授信发放成功后，给终端用户到账或开通套餐，并写入待结算销售记录。
- 管理端可以按代理、日期、资源类型查看销售汇总和明细，并支持部分结算。
- 每日额度和销售业务日期都按北京时间自然日计算。

## 文件变更清单

### 后端

- `backend/app/models/agent.py`
  - 新增 `AgentDailyLimit`
  - 新增 `AgentDailyLimitUsage`
  - 新增 `AgentSettlementRecord`
  - 新增 `AgentSettlementBatch`
  - 新增 `AgentSettlementBatchItem`
- `backend/app/models/__init__.py`
  - 注册新增 ORM。
- `backend/app/schemas/agent.py`
  - 新增每日额度批量保存请求。
  - 新增结算请求模型。
  - 套餐每日额度和套餐结算数量强制整数。
- `backend/app/services/agent_settlement_service.py`
  - 新增代理每日授信额度、销售记录、结算批次服务。
  - 每日额度批量保存改为整批校验、整批提交。
  - 管理端结算汇总支持按资源类型筛选，并按当前套餐统计旧套餐库存。
  - 停用额度返回剩余 0，避免代理端误显示可发放。
- `backend/app/services/agent_asset_service.py`
  - 改造余额、图片积分、套餐发放逻辑。
  - 资产池不足时走每日授信额度并生成待结算记录。
  - 扣减用户资源时避免未结算授信资源回流旧资产池。
- `backend/app/core/exceptions.py`
  - 参数校验错误返回中文 message，错误明细也不再暴露英文错误类型。
- `backend/app/api/admin/agent.py`
  - 新增每日授信额度配置接口。
  - 新增代理结算汇总、明细、执行结算接口。
- `backend/app/api/agent/stats.py`
  - 工作台接口返回今日授信额度和待结算摘要。
- `backend/app/api/agent/subscription.py`
  - 套餐列表返回今日套餐授信剩余额度。

### 前端

- `frontend/src/api/agent.js`
  - 新增每日授信额度接口。
  - 新增结算汇总、明细、执行结算接口。
- `frontend/src/views/admin/AgentAssetManage.vue`
  - 新增“每日授信额度”配置区域。
  - 套餐每日授信额度输入限制为整数。
- `frontend/src/views/admin/AgentSettlementManage.vue`
  - 新增管理端代理结算页面。
  - 套餐结算数量输入限制为整数。
  - 旧资产池展示补充剩余与已消耗口径。
- `frontend/src/router/index.js`
  - 新增 `/admin/agent-settlements` 路由。
- `frontend/src/layout/AdminLayout.vue`
  - 新增“代理结算”菜单。
- `frontend/src/views/agent/Workbench.vue`
  - 新增今日授信额度和待结算展示。
- `frontend/src/views/agent/SubscriptionManage.vue`
  - 套餐发放支持“库存或今日额度”。
  - 停用的今日授信额度不会作为可发放额度。
- `frontend/src/views/agent/UserManage.vue`
  - 充值弹窗补充授信额度提示。

### SQL

- `sql/upgrade_agent_settlement_system_20260430.sql`
- `backend/sql/upgrade_agent_settlement_system_20260430.sql`
- `sql/init.sql`
- `backend/sql/init.sql`

## 核心实现说明

### 1. 每日授信额度

表：

- `agent_daily_limit`
- `agent_daily_limit_usage`

规则：

- `resource_type=balance`：控制每日可授信发放的美元余额。
- `resource_type=image_credit`：控制每日可授信发放的图片积分。
- `resource_type=subscription + plan_id`：控制某个套餐模板每日可授信发放数量。
- 无配置、停用、额度为 0 都不可授信。
- 发放时先锁额度配置行，再创建或锁当天使用量行，防止并发超额。

### 2. 待结算销售记录

表：

- `agent_settlement_record`

授信发放成功后写入：

- 代理 ID
- 用户 ID
- 北京时间业务日期 `business_date`
- 资源类型
- 套餐快照
- 销售数量
- 已结算数量
- 状态

### 3. 部分结算审计

表：

- `agent_settlement_batch`
- `agent_settlement_batch_item`

管理端执行结算时：

- 按最早销售记录依次结算。
- 对销售记录加 `FOR UPDATE` 防止并发超结。
- 请求结算数量大于未结算数量时直接拒绝。
- 每次结算动作都写批次和批次明细。

### 4. 资产池与授信关系

发放规则：

- 旧资产池足额：整笔走旧资产池。
- 旧资产池不足：整笔走授信额度。
- 不做“旧资产池扣一部分 + 授信补差”的混合模式。

扣减规则：

- 如果代理存在未结算授信余额/图片积分记录，扣减用户资源时不增加代理旧资产池。
- 这样可以避免授信资源被扣回后变成预充值资产，再次发放时绕过结算。

## 新增接口

### 管理端

- `GET /api/admin/agents/{agent_id}/daily-limits`
- `PUT /api/admin/agents/{agent_id}/daily-limits`
- `GET /api/admin/agents/settlements/summary`
- `GET /api/admin/agents/settlements/records`
- `POST /api/admin/agents/settlements/settle`

### 代理端

- `GET /api/agent/stats/workbench`
  - 新增 `credit_limit_summary`
- `GET /api/agent/subscription/plans`
  - 新增 `credit_limit`
  - 新增 `daily_remaining_count`

## 测试验证

已执行：

```bash
python -m py_compile backend/app/models/agent.py backend/app/models/__init__.py backend/app/schemas/agent.py backend/app/services/agent_settlement_service.py backend/app/services/agent_asset_service.py backend/app/api/admin/agent.py backend/app/api/agent/stats.py backend/app/api/agent/subscription.py
```

结果：通过。

已执行：

```bash
npm run build
```

目录：`frontend`

结果：构建通过，仅有既有的资源体积警告。

## Review 修复记录

首次代码审查结论为“不通过”，已修复以下问题：

- 套餐授信额度和套餐结算数量允许小数：已在 Schema、服务层和前端输入层强制整数。
- 管理端结算汇总旧套餐资产池口径错误：已改为按当前 `plan_id` 统计 `remaining_count` 和 `total_used`。
- 管理端结算汇总资源类型筛选无效：已补齐 summary 接口和服务层 `resource_type` 过滤。
- 停用额度仍在代理端显示可用：已在后端序列化时对 `disabled` 返回 `remaining_amount=0`，前端也校验 `status=active`。
- 每日额度批量保存非事务：已改为先整批校验，再整批 `flush`，最后统一 `commit`。
- 参数校验错误可能包含英文：已统一转换为中文错误信息，错误明细 `type` 也改为中文。

二次外部 Review 因上游返回 `INSUFFICIENT_BALANCE` 中断，未取得最终结论；已基于首次 Review 问题逐项本地复核并重新执行编译和构建。

## 部署说明

上线前执行以下 SQL：

```sql
source sql/upgrade_agent_settlement_system_20260430.sql;
```

或使用后端目录同步文件：

```sql
source backend/sql/upgrade_agent_settlement_system_20260430.sql;
```

执行后需要在管理端：

1. 打开 `admin/agent-assets`。
2. 选择代理。
3. 配置余额、图片积分、各套餐模板的每日授信额度。
4. 打开 `admin/agent-settlements` 查看销售与执行结算。

## 注意事项

- 本次未把代理兑换码纳入授信结算，兑换码仍使用代理余额池生成。
- `backend/sql/init.sql` 原本与主 `sql/init.sql` 存在代理基础表同步差异，本次只补充了结算系统新增表。
- 当前工作区存在图片生成相关未提交改动，本次没有修改这些文件。
