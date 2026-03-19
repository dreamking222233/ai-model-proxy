## 任务概述

- 将用户侧 `user/balance` 与 `user/usage` 合并为一个“账单与使用”页面，减少重复入口和相似信息分散的问题。
- 保留原有后端接口与数据结构，不新增后端改动。
- 保留旧的 `user/usage` 访问兼容，通过路由重定向到 `user/balance?tab=usage`。

## 文件变更清单

- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/router/index.js`
- `frontend/src/layout/UserLayout.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/views/user/Redemption.vue`
- `md/plan-user-billing-usage-merge-20260319.md`

## 核心代码说明

### 1. 单页双标签整合

- 在 `BalanceLog.vue` 中新增 `a-tabs`，拆分为：
  - `余额与账单`
  - `请求记录`
- `余额与账单` 保留原页面的余额摘要、充值联系方式与消费记录表。
- `请求记录` 并入原 `UsageLog.vue` 的筛选条件、请求摘要、每分钟统计、调用明细与错误详情弹窗。

### 2. 路由兼容策略

- `user/balance` 继续作为主页面入口，但标题改为“账单与使用”。
- `user/usage` 不再直接挂载独立页面，改为重定向到：
  - `/user/balance?tab=usage`
- 合并页根据 `query.tab` 决定默认激活的标签，并在切换标签时同步更新 URL。

### 3. 导航与文案收敛

- 用户侧菜单移除单独的“使用记录”入口，仅保留“账单与使用”。
- 仪表盘快捷入口改为直达 `账单与使用` 页的 `请求记录` 标签。
- 快速开始、兑换码充值页的文案统一改为指向新页面。

## 测试验证

- 执行：`cd frontend && npm run lint`
- 结果：通过
- 说明：存在 1 条历史 warning，位于 `frontend/src/store/index.js:54`，为未使用的 `commit`，非本次改动引入

## 待优化项

- `frontend/src/views/user/UsageLog.vue` 当前已不再被路由使用，后续可视情况删除或拆成可复用子组件。
- 如后续需要继续收敛用户侧入口，可考虑将 `user/stats` 的图表统计也进一步并入当前合并页。
