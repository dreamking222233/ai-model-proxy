## 变更记录

- 日期：2026-03-19
- 范围：
  - 修复 `admin/subscription` 页面及套餐期间计费/使用统计相关问题
  - 合并 `user/balance` 页面与 `user/usage` 页面

---

## 一、admin/subscription 修复与增强

### 1. 问题背景

- 管理端为用户开通套餐后，`admin/subscription` 页面中的套餐记录区域不显示。
- 接口返回中存在 `total`，但 `data` 为 `null`，导致前端列表无法正常渲染。
- 套餐用户在使用期间不会扣余额，但原系统无法按套餐周期统计其请求数、Token 和理论消费金额。

### 2. 处理结果

- 修复了套餐列表接口返回结构异常的问题，确保前端能拿到列表数据。
- 为套餐期消费记录增加计费归属标记，支持区分：
  - `balance`：按余额计费
  - `subscription`：按套餐计费
- 为套餐消费记录增加 `subscription_id`，可以将套餐期间的消费与具体套餐记录关联起来。
- 管理端套餐页新增套餐使用情况查看能力，可查看：
  - 套餐期间请求数
  - Token 总量
  - 理论金额
  - 使用明细
- 修复了续费场景下套餐过期状态切换不准确的问题，避免旧套餐过期后错误切回余额模式。

### 3. 修改文件

- `backend/app/api/admin/subscription.py`
- `backend/app/models/log.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/subscription_service.py`
- `frontend/src/api/subscription.js`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `sql/init.sql`

### 4. 新增文件

- `sql/upgrade_subscription_usage_tracking_20260319.sql`
- `md/plan-subscription-usage-tracking-20260319.md`
- `md/impl-subscription-usage-tracking-20260319.md`
- `md/review-subscription-usage-tracking-20260319.md`

### 5. 数据库同步情况

- 升级 SQL 已同步到 `sql/init.sql`
- 本地数据库 `modelinvoke` 已执行：
  - `sql/upgrade_subscription_usage_tracking_20260319.sql`
- 当前 `consumption_record` 表已包含：
  - `billing_mode`
  - `subscription_id`
  - `idx_billing_mode`
  - `idx_subscription_id`

### 6. 验证情况

- 已执行：
  - `python -m py_compile backend/app/api/admin/subscription.py backend/app/models/log.py backend/app/services/proxy_service.py backend/app/services/subscription_service.py`
- 结果：通过

---

## 二、user/balance 与 user/usage 页面合并

### 1. 问题背景

- 用户侧 `user/balance` 页面与 `user/usage` 页面在展示结构和信息层面存在较多重复。
- 页面入口分散，用户需要在不同页面之间切换查看余额、消费账单和请求记录。

### 2. 处理结果

- 将 `user/balance` 升级为统一页面“账单与使用”。
- 在同一页面中通过标签页拆分为：
  - `余额与账单`
  - `请求记录`
- `请求记录` 标签页整合了原 `user/usage` 的能力，包括：
  - 状态筛选
  - 日期筛选
  - 请求摘要
  - 每分钟统计
  - 调用明细
  - 错误详情弹窗
- 保留旧路由兼容：
  - `/user/usage` 重定向到 `/user/balance?tab=usage`
- 用户侧菜单收敛为单个入口“账单与使用”。
- 仪表盘、快速开始、兑换码充值页面中的相关入口和文案也同步更新为新页面表述。

### 3. 修改文件

- `frontend/src/router/index.js`
- `frontend/src/layout/UserLayout.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/views/user/Redemption.vue`

### 4. 新增文件

- `md/plan-user-billing-usage-merge-20260319.md`
- `md/impl-user-billing-usage-merge-20260319.md`

### 5. 验证情况

- 已执行：
  - `cd frontend && npm run lint`
- 结果：通过
- 说明：
  - 存在 1 条历史 warning：`frontend/src/store/index.js:54` 的 `commit` 未使用
  - 该 warning 非本次改动引入

---

## 三、当前涉及文件总览

### 已修改文件

- `backend/app/api/admin/subscription.py`
- `backend/app/models/log.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/subscription_service.py`
- `frontend/src/api/subscription.js`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/layout/UserLayout.vue`
- `frontend/src/router/index.js`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/QuickStart.vue`
- `frontend/src/views/user/Redemption.vue`
- `sql/init.sql`

### 已新增文件

- `sql/upgrade_subscription_usage_tracking_20260319.sql`
- `md/plan-subscription-usage-tracking-20260319.md`
- `md/impl-subscription-usage-tracking-20260319.md`
- `md/review-subscription-usage-tracking-20260319.md`
- `md/plan-user-billing-usage-merge-20260319.md`
- `md/impl-user-billing-usage-merge-20260319.md`

---

## 四、说明

- 本文档用于汇总保存本轮两项主要改动的实施记录。
- 若后续还要补充“用户侧套餐使用明细展示”或“删除未再使用的旧页面组件”，可在此基础上继续追加更新记录。
