# 代理工作台实施记录

## 任务概述

代理端后台新增“工作台”菜单和页面，用于集中展示当前代理资产池，包括余额、图片积分、套餐库存和库存风险提示。

## 文件变更清单

- `backend/app/api/agent/stats.py`
  - 新增 `GET /api/agent/stats/workbench`。
  - 基于当前代理账号 `agent_id` 返回代理基础信息、余额池、图片积分池、套餐库存和库存汇总。
- `frontend/src/api/agent.js`
  - 新增 `getAgentWorkbenchSummary()`。
- `frontend/src/views/agent/Workbench.vue`
  - 新增代理工作台页面。
  - 展示可分配余额、图片积分、套餐剩余库存、低库存套餐、套餐库存表和快捷入口。
- `frontend/src/router/index.js`
  - 新增 `/agent/workbench` 路由。
  - `/agent` 默认重定向到 `workbench`。
  - 已登录代理访问登录页时默认跳转工作台。
- `frontend/src/layout/AgentLayout.vue`
  - 新增“工作台”菜单项。
- `frontend/src/views/Login.vue`
  - 代理账号登录成功后默认进入 `/agent/workbench`。
- `md/plan-agent-workbench-20260427.md`
  - 新增实施计划文档。

## 核心逻辑

工作台接口只允许代理账号访问，依赖 `require_agent_admin` 获取当前登录代理，避免代理端调用管理端接口或传入任意代理 ID。

接口返回结构：

```json
{
  "agent": {},
  "balance": 0,
  "image_credit_balance": 0,
  "subscription_inventory": [],
  "subscription_summary": {
    "plan_count": 0,
    "total_remaining": 0,
    "total_granted": 0,
    "total_used": 0,
    "low_stock_count": 0,
    "empty_stock_count": 0
  }
}
```

## 测试验证

- `python -m py_compile backend/app/api/agent/stats.py`：通过。
- `npm run build`：通过，仅存在既有的 bundle size warning。

## 待优化项

- 后续可补充最近资产流水，例如代理余额充值、发放、回收记录。
- 后续可增加库存预警阈值配置，由管理端控制不同套餐的预警线。
