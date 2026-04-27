# 代理工作台实施计划

## 用户原始需求

代理端后台菜单新增“工作台”，主要用于显示当前代理剩余多少额度，包括美元余额、图片积分余额、各种套餐库存额度等信息。

## 技术方案

1. 后端新增代理侧只读汇总接口，基于当前登录代理账号的 `agent_id` 获取资产信息，避免前端调用管理端接口。
2. 汇总接口返回当前代理基础信息、余额池、图片积分池、套餐库存列表和简单统计字段。
3. 前端 `src/api/agent.js` 新增工作台接口封装。
4. 前端新增 `src/views/agent/Workbench.vue` 页面，展示资产卡片、套餐库存表、低库存提示和快捷入口。
5. 代理端路由新增 `/agent/workbench`，默认进入工作台。
6. 代理端菜单新增“工作台”，保留现有“仪表盘”作为业务统计页面。

## 涉及文件

- `backend/app/api/agent/stats.py`
- `frontend/src/api/agent.js`
- `frontend/src/router/index.js`
- `frontend/src/layout/AgentLayout.vue`
- `frontend/src/views/agent/Workbench.vue`

## 实施步骤

1. 新增后端 `/api/agent/stats/workbench` 接口。
2. 新增前端 `getAgentWorkbenchSummary` API 方法。
3. 新建代理工作台 Vue 页面。
4. 调整代理端默认路由和菜单。
5. 执行 Python 编译、前端构建验证。
