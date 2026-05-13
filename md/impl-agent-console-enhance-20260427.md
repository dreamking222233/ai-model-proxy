# 代理端后台体验增强实施记录

## 任务概述

本次增强围绕代理端后台三个页面：

1. `agent/dashboard` 增加当前代理站点的数据概览、今日 Token、成功率、失败次数、请求趋势和详情统计。
2. `agent/users` 按 `admin/users` 的交互方式优化用户管理，支持通过按钮完成余额、图片积分、禁用/启用和跳转发放套餐。
3. `agent/subscription` 保留套餐库存发放能力，并新增当前代理的套餐发放记录。

## 文件变更清单

### 后端

- `backend/app/services/log_service.py`
  - `get_request_stats` 增加 `agent_id` 可选参数。
  - 当传入 `agent_id` 时，仅统计当前代理下游用户请求。

- `backend/app/services/subscription_service.py`
  - 新增 `list_agent_subscriptions`。
  - 按 `UserSubscription.agent_id` 过滤代理发放记录。
  - 复用已有订阅序列化和套餐使用汇总逻辑。
  - 套餐创建链路新增 `agent_id` 归属写入，确保代理发放后可在记录页查到。
  - 套餐记录状态筛选改为按运行时业务状态过滤。

- `backend/app/api/agent/stats.py`
  - 新增 `GET /api/agent/stats/dashboard`。
  - 新增 `GET /api/agent/stats/requests`。
  - 今日统计按北京时间自然日窗口计算。

- `backend/app/api/agent/subscription.py`
  - 新增 `GET /api/agent/subscription/records`。
  - 支持 `page`、`page_size`、`status` 查询。

### 前端

- `frontend/src/api/agent.js`
  - 新增 `getAgentDashboardStats`。
  - 新增 `getAgentRequestStats`。
  - 新增 `listAgentSubscriptionRecords`。

- `frontend/src/views/agent/Dashboard.vue`
  - 从简单站点信息页改为完整代理仪表盘。
  - 展示用户总数、今日请求、今日 Token、失败次数。
  - 展示今日 Token 进度、成功率、失败率。
  - 展示近 7 天请求趋势图和详细统计表。
  - 保留站点名称、统一 API 地址、注册开关、公告信息。

- `frontend/src/views/agent/UserManage.vue`
  - 增加统计卡片：用户总数、正常用户、余额总计、图片积分总计。
  - 表格参考管理端用户页面，优化头像、状态、计费模式、资产展示。
  - 操作按钮改为图标按钮：余额、图片积分、发放套餐、禁用/启用。
  - 资产弹窗支持充值/扣除切换，扣除时可填写原因。

- `frontend/src/views/agent/SubscriptionManage.vue`
  - 增加页面头部和刷新按钮。
  - 使用 Tabs 区分“套餐库存”和“发放记录”。
  - 套餐库存表展示类型、时长、额度、剩余库存。
  - 发放记录表展示用户、套餐、状态、额度、已用 Token、开始/结束/发放时间。

- `sql/upgrade_agent_console_enhance_20260427.sql`
- `backend/sql/upgrade_agent_console_enhance_20260427.sql`
  - 回填历史 `user_subscription.agent_id`，用于服务器部署后展示历史代理套餐记录。

## 核心逻辑说明

### 代理仪表盘数据隔离

所有代理端统计接口都从 `require_agent_admin` 获取当前代理账号，并使用 `current_user.agent_id` 过滤：

- 用户总数：`SysUser.agent_id = 当前代理ID` 且 `role = user`
- 请求统计：`RequestLog.agent_id = 当前代理ID`
- 套餐记录：`UserSubscription.agent_id = 当前代理ID`

这样代理端只能看到自己下游用户的数据，不会看到平台全局数据或其他代理数据。

### 失败次数定义

代理仪表盘里的失败次数使用：

```text
RequestLog.status != "success"
```

这比只统计 `error` 更稳妥，可以覆盖 `failed`、`timeout` 等非成功状态。

### 套餐发放记录

代理发放套餐时，原有逻辑已经会写入 `UserSubscription.agent_id`。本次新增的记录接口直接按该字段过滤，不需要新增数据库字段。

Review 后修正：原发放链路实际未写入 `UserSubscription.agent_id`，已在 `activate_plan_subscription` / `_build_subscription_record` 中补齐 `agent_id` 参数，并在 `AgentAssetService.grant_user_subscription` 中显式传入当前代理 ID。

### 请求趋势补零

`LogService.get_request_stats` 改为使用北京时间自然日窗口，返回固定 N 天数据。没有请求的日期返回 0，避免趋势图缺天。

## 测试验证

已执行：

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m py_compile backend/app/services/log_service.py backend/app/services/subscription_service.py backend/app/api/agent/stats.py backend/app/api/agent/subscription.py
```

结果：通过。

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest backend.app.test.test_agent_portal
```

结果：Review 修复后重新执行，`Ran 10 tests in 0.035s OK`。

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -c "import app.main; print('import ok')"
```

结果：导入通过；本地 Redis 未启动，日志提示缓存自动关闭，不影响本次功能。

```bash
npm run build
```

结果：构建通过；仅存在项目已有的 bundle size warning。

## 待优化项

1. 当前代理用户页统计卡片中的余额总计和图片积分总计基于当前分页数据计算；如需全量统计，可后续新增后端汇总接口。
2. 代理套餐发放弹窗当前使用用户 ID 输入；后续可改为搜索选择当前代理用户。
3. 仪表盘趋势已改成北京时间自然日窗口，但 SQL 分组仍使用数据库日期函数；当前数据库时间需保持与系统存储约定一致。
