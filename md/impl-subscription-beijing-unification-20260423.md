## 任务概述

将套餐体系相关时间统一为“北京时间本地时间语义”。

本次改造覆盖：

- 套餐开始/结束/激活时间生成
- 套餐状态判断与过期判断
- 日配额周期窗口计算
- API 鉴权时的套餐有效期判断
- 前端套餐相关页面展示

## 文件变更清单

- `backend/app/services/subscription_service.py`
- `backend/app/core/dependencies.py`
- `backend/app/services/proxy_service.py`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `md/plan-subscription-beijing-unification-20260423.md`

## 核心代码说明

### 1. 后端统一北京时间当前时间入口

在 `SubscriptionService` 中新增：

- `get_current_time(tz_name=None)`

该方法使用 `ZoneInfo("Asia/Shanghai")` 生成北京时间当前时间，并存储为无时区 `datetime`，作为套餐业务时间的统一来源。

### 2. 套餐状态判断改为北京时间

以下逻辑全部改为基于 `SubscriptionService.get_current_time()`：

- `_normalized_subscription_status`
- `_is_effectively_active`
- `resolve_active_subscription`
- `refresh_user_subscription_state`
- `check_quota_before_request`
- `consume_quota_after_request`
- `check_and_expire_subscriptions`

这样套餐是否生效、是否过期、是否还有日额度，全部按北京时间判断。

### 3. 套餐开通时间改为北京时间生成

以下开通逻辑不再使用 `datetime.utcnow()`，改为北京时间本地时间：

- `activate_subscription`
- `activate_plan_subscription`
- `_build_subscription_record` 中 `activated_at` 判定

因此 `start_time/end_time/activated_at/subscription_expires_at` 现在都使用北京时间本地时间语义。

### 4. 配额周期窗口改为北京时间本地存储

`_get_cycle_window()` 从原先“UTC 中转并返回 UTC-naive”改为：

- 输入：北京时间本地时间
- 计算：以 `reset_timezone` 为业务日界
- 输出：转换回北京时间本地时间语义后再存储

这样 `cycle_start_at/cycle_end_at` 与数据库内本地时间语义的消费记录、请求日志可以直接比较，不再混用 UTC naive。

### 5. 请求入口与鉴权层同步修正

为避免调用方继续把 UTC 时间传入套餐服务，本次同步修改：

- `backend/app/core/dependencies.py`
- `backend/app/services/proxy_service.py`

其中：

- API Key 鉴权时的套餐过期校验改为北京时间
- 文本请求准入检查与套餐消费结算使用北京时间当前时间

### 6. 前端套餐展示改为普通本地时间展示

由于后端套餐字段已经统一为北京时间本地时间语义，前端不再需要对套餐字段使用 `formatUtcDate/parseUtcDate`。

已调整：

- `admin/SubscriptionManage.vue`
- `admin/UserManage.vue`
- `user/Dashboard.vue`
- `user/BalanceLog.vue`

这些页面现在直接使用普通 `formatDate` 或 `new Date()` 展示和比较套餐时间。

## 测试验证

### 后端语法校验

```bash
python -m py_compile backend/app/services/subscription_service.py backend/app/core/dependencies.py backend/app/services/proxy_service.py
```

结果：通过。

### 后端兼容测试

```bash
PYTHONPATH=backend python -m pytest backend/app/test/test_subscription_compatibility.py
```

结果：`6 passed`

### 前端构建

```bash
cd frontend
npm run build
```

结果：

- 构建通过
- 仅存在仓库原有 eslint warning 与产物体积 warning
- 无新增编译错误

## 说明

- 本次没有修改非套餐业务时间口径，例如兑换码、最后登录、API Key 使用时间等，避免扩大影响范围。
- `admin/subscription` 页面当前已实现“生成、判断、展示”三层统一北京时间。 
