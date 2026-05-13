## 版本

v2

## 用户原始需求

当前希望将套餐相关时间“全部同步为北京时间”。

结合上下文，目标是让套餐体系中的时间在以下环节统一口径：

- 后端生成时间
- 后端状态判断时间
- 套餐周期窗口时间
- 前端页面展示时间

重点页面包括：

- `admin/subscription`
- `admin/users`
- `user/dashboard`
- `user/balance`

## 技术方案设计

当前系统套餐时间存在混合口径：

1. 套餐生效时间 `start_time/end_time/activated_at` 使用 `datetime.utcnow()` 生成，为无时区 UTC 时间。
2. 套餐相关数据库记录 `created_at/updated_at` 大多使用数据库 `CURRENT_TIMESTAMP`，语义更接近本地时间。
3. 前端为了兼容上一版实现，对套餐字段使用 `formatUtcDate/parseUtcDate` 转北京时间显示。
4. 后端权限判断与套餐状态判断仍大量依赖 `datetime.utcnow()`。

这导致套餐系统内部“生成、存储、比较、展示”并未统一。

### 统一目标

将套餐相关业务时间统一为：

- **北京时间本地时间语义**
- 存储为无时区 `datetime`
- 比较时使用北京时间当前时间
- 前端展示时按普通本地时间处理，不再额外做 UTC 转换

### 实现原则

1. 在 `SubscriptionService` 中新增统一的北京时间当前时间方法。
2. 所有套餐生效/过期/刷新/周期计算一律改用北京时间当前时间。
3. `cycle_start_at/cycle_end_at/start_time/end_time/activated_at/subscription_expires_at` 都按北京时间本地时间语义生成和比较。
4. 前端中所有套餐字段的展示从 `formatUtcDate/parseUtcDate` 切回普通 `formatDate/new Date()` 逻辑。
5. 鉴权层中套餐过期校验同步改为北京时间。

### 风险点

1. `subscription_service.py` 内部 `datetime.utcnow()` 使用点较多，必须一次性统一，否则会出现显示正确但权限判断错误。
2. 日配额周期 `cycle_start_at/cycle_end_at` 当前实现基于 UTC 中转，需要改成北京时间本地存储，否则消费记录与周期窗口比较仍可能错位。
3. 前端切回普通时间格式化后，必须确认不会影响已修好的非套餐页面。

## 影响范围分析

### 后端

- `backend/app/services/subscription_service.py`
- `backend/app/core/dependencies.py`
- `backend/app/services/proxy_service.py`
- 测试文件中的套餐时间构造

### 前端

- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/BalanceLog.vue`

### 文档

- `md/plan-subscription-beijing-unification-20260423.md`
- `md/impl-subscription-beijing-unification-20260423.md`
- `md/review-subscription-beijing-unification-20260423.md`

## To-Do

1. 为 `SubscriptionService` 增加北京时间当前时间辅助方法。
2. 将套餐状态判断相关 `datetime.utcnow()` 全量替换为北京时间当前时间。
3. 重写 `_get_cycle_window()`，使周期窗口存储为北京时间本地时间。
4. 调整套餐开通逻辑 `activate_subscription/activate_plan_subscription` 的起止时间生成。
5. 调整 `activated_at` 判定逻辑。
6. 调整 `refresh_user_subscription_state/resolve_active_subscription/check_quota_before_request/consume_quota_after_request` 等比较逻辑。
7. 调整 `core/dependencies.py` 中套餐过期校验。
8. 审查 `proxy_service.py` 中传入套餐服务的时间参数，保证口径一致。
9. 将前端套餐字段展示从 `formatUtcDate/parseUtcDate` 改回普通时间展示。
10. 执行后端语法校验和前端构建验证。
11. 编写实施与 review 文档。
