## 用户原始需求

- 当前 `user/balance` 页面和 `user/usage` 页面内容有较多相似区域，希望评估并合并为一个页面。

## 技术方案设计

- 保留 `user/balance` 作为合并后的主入口，页面升级为“账单与使用”单页。
- 在主页面中新增标签页，拆分为：
  - `余额与账单`：保留当前余额、累计充值、累计消费、消费记录。
  - `请求记录`：并入当前 `user/usage` 的筛选、今日摘要、每分钟统计、调用明细、错误详情弹窗。
- 保留现有后端接口，不新增接口，不改动后端逻辑：
  - `getBalance`
  - `getConsumptionRecords`
  - `getUsageLogs`
  - `getPerMinuteStats`
- 兼容旧链接：
  - `user/usage` 路由继续存在，但重定向到 `user/balance?tab=usage`
  - 仪表盘、快捷开始、兑换码页等引用统一改为新页面表述
- 用户菜单收敛为一个入口，移除单独的“使用记录”菜单项，避免重复导航。

## 涉及文件清单

- `frontend/src/router/index.js`
- `frontend/src/layout/UserLayout.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Redemption.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/views/user/Dashboard.vue`

## 实施步骤概要

1. 调整路由，将 `user/usage` 改为兼容跳转到 `user/balance?tab=usage`
2. 重构 `BalanceLog.vue`，整合 `UsageLog.vue` 的数据获取和页面结构
3. 使用标签页区分账单与请求记录，保留原有筛选与弹窗能力
4. 更新用户侧菜单与页面文案，统一指向合并后的页面
5. 执行前端 lint 验证
6. 生成 impl/review 文档并完成自审
