# 代理端后台体验增强计划

## 用户原始需求

当前代理端后台需要补齐以下能力：

1. `agent/dashboard` 页面参考 `admin/dashboard`，展示当前代理站点今日 Token 使用量、成功率、失败次数、用户总数、今日请求数、请求趋势和详情统计区域。
2. `agent/users` 页面参考 `admin/users`，可以通过按钮为用户加减余额、充值/扣减图片积分、禁用/启用用户，并优化页面 UI/UX。
3. `agent/subscription` 页面可以看到代理已发放的套餐记录。

## 技术方案设计

### 后端

1. 新增代理仪表盘统计接口：
   - `GET /api/agent/stats/dashboard`
   - 按 `current_user.agent_id` 过滤用户和请求记录。
   - 返回 `total_users`、`today_requests`、`today_tokens`、`today_errors`。

2. 新增代理请求趋势接口：
   - `GET /api/agent/stats/requests?days=7`
   - 复用 `LogService.get_request_stats`，增加 `agent_id` 可选过滤。
   - 返回近 N 天每日请求数、成功数、失败数、输入/输出/总 Token。

3. 新增代理套餐发放记录接口：
   - `GET /api/agent/subscription/records`
   - 按 `UserSubscription.agent_id = 当前代理ID` 过滤。
   - 返回套餐记录、用户信息、状态、开始/结束时间、额度使用信息。

### 前端

1. `frontend/src/api/agent.js`
   - 增加 `getAgentDashboardStats`
   - 增加 `getAgentRequestStats`
   - 增加 `listAgentSubscriptionRecords`

2. `frontend/src/views/agent/Dashboard.vue`
   - 改造成类 `admin/dashboard` 的统计卡 + 进度卡 + 趋势图 + 详情表。
   - 请求全部走代理端接口，仅展示当前代理下游数据。

3. `frontend/src/views/agent/UserManage.vue`
   - 参考 `admin/users` 的统计卡、表格、操作按钮、资产操作弹窗。
   - 保持代理权限边界：只能管理当前代理下的普通用户。

4. `frontend/src/views/agent/SubscriptionManage.vue`
   - 保留套餐库存和发放功能。
   - 新增“发放记录”表格，展示当前代理发放过的套餐。

## 涉及文件清单

- `backend/app/services/log_service.py`
- `backend/app/services/subscription_service.py`
- `backend/app/api/agent/stats.py`
- `backend/app/api/agent/subscription.py`
- `frontend/src/api/agent.js`
- `frontend/src/views/agent/Dashboard.vue`
- `frontend/src/views/agent/UserManage.vue`
- `frontend/src/views/agent/SubscriptionManage.vue`

## 实施步骤概要

1. 扩展后端统计服务，支持按代理过滤请求趋势。
2. 增加代理仪表盘统计接口。
3. 增加代理套餐发放记录接口。
4. 扩展前端代理 API 方法。
5. 重构代理仪表盘页面。
6. 优化代理用户管理页面。
7. 优化代理套餐管理页面并加入发放记录。
8. 执行后端 Python 编译检查和前端构建验证。

