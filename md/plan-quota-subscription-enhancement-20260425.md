# Plan: 套餐额度限制与自动刷新功能

**日期**: 2026-04-25
**功能**: 支持有限额度套餐（日/月/自定义周期），每日自动刷新额度
**任务规模**: 大型（预计 12+ 步骤）

---

## 一、需求分析

### 1.1 当前系统能力

**已有功能**：
- ✅ 无限额度套餐（`plan_kind=unlimited`）：不扣除用户余额，无限使用
- ✅ 每日限额套餐（`plan_kind=daily_quota`）：已支持每日额度限制
- ✅ 套餐模板管理（`SubscriptionPlan`）：管理员可创建套餐模板
- ✅ 用户订阅记录（`UserSubscription`）：记录用户开通的套餐
- ✅ 每日使用周期（`SubscriptionUsageCycle`）：记录每日额度使用情况
- ✅ 时区支持：支持按时区刷新额度（默认 Asia/Shanghai）
- ✅ 额度口径：支持 `total_tokens` 和 `cost_usd` 两种计量方式

**数据模型**：
```python
# SubscriptionPlan - 套餐模板
- plan_code: 套餐编码（唯一）
- plan_name: 套餐名称
- plan_kind: unlimited/daily_quota
- duration_days: 套餐时长（天）
- quota_metric: total_tokens/cost_usd
- quota_value: 每日额度值
- reset_period: 刷新周期（day）
- reset_timezone: 刷新时区

# UserSubscription - 用户订阅记录
- user_id: 用户ID
- plan_id: 套餐模板ID
- start_time/end_time: 有效期
- quota_metric/quota_value: 额度快照

# SubscriptionUsageCycle - 每日使用周期
- subscription_id: 订阅ID
- cycle_date: 周期日期
- quota_limit: 额度上限
- used_amount: 已使用额度
```

### 1.2 新增需求

**核心需求**：
1. **有限额度套餐**：支持设置每日/每月/自定义周期的额度限制
2. **额度自动刷新**：每天自动重置额度（按时区）
3. **灵活配置**：
   - 支持按 Token 数量限制（如每天 1000 万 Token）
   - 支持按成本限制（如每天 100 美元）
   - 支持自定义时长（如 7 天、30 天、90 天）
4. **额度耗尽处理**：额度用完后拒绝请求，第二天自动恢复

**示例套餐**：
- 日卡有限套餐：1 天有效，每天 100 美元额度
- 月卡有限套餐：30 天有效，每天 1000 万 Token
- 季度套餐：90 天有效，每天 50 美元额度

---

## 二、现状分析

### 2.1 已有的 daily_quota 机制

**代码位置**: `backend/app/services/subscription_service.py`

**核心逻辑**：
1. **额度检查**（`check_quota_before_request`）：
   - 查询用户当前有效订阅
   - 获取或创建当日使用周期（`SubscriptionUsageCycle`）
   - 检查 `used_amount < quota_limit`
   - 返回是否允许请求

2. **额度扣减**（`consume_quota_after_request`）：
   - 更新 `SubscriptionUsageCycle.used_amount`
   - 记录到 `RequestLog.subscription_cycle_id`

3. **周期管理**（`_get_or_create_usage_cycle`）：
   - 根据时区计算当日起止时间
   - 自动创建新周期记录
   - 使用 `UniqueConstraint(subscription_id, cycle_date)` 防重

4. **过期检查**（`check_and_expire_subscriptions`）：
   - 定时任务检查过期订阅
   - 更新 `status=expired`

### 2.2 现有问题

**问题 1：额度刷新机制不完善**
- ✅ 已有按日期创建新周期的逻辑
- ✅ 已有时区支持
- ❌ 缺少定时任务自动清理旧周期
- ❌ 缺少跨天刷新的主动触发

**问题 2：套餐模板配置不够灵活**
- ✅ 已支持 `quota_metric` 和 `quota_value`
- ✅ 已支持 `reset_period` 和 `reset_timezone`
- ❌ `reset_period` 目前只支持 "day"，未实现 "month" 等其他周期

**问题 3：前端展示不完整**
- ❌ 管理员创建套餐时，需要清晰展示 `plan_kind` 选项
- ❌ 用户查看套餐时，需要显示剩余额度

---

## 三、技术方案

### 3.1 数据库改动

**无需改动**：现有表结构已完全支持需求

**验证点**：
- ✅ `SubscriptionPlan.plan_kind` 支持 `daily_quota`
- ✅ `SubscriptionPlan.quota_metric` 支持 `total_tokens` 和 `cost_usd`
- ✅ `SubscriptionPlan.quota_value` 使用 `DECIMAL(20, 6)` 足够精度
- ✅ `SubscriptionUsageCycle` 已有唯一约束防止重复创建

### 3.2 后端改动

#### 3.2.1 完善套餐模板管理

**文件**: `backend/app/services/subscription_service.py`

**改动 1：增强内置套餐模板**
```python
BUILTIN_PLANS = [
    # 现有无限套餐保持不变
    {
        "plan_code": "daily-unlimited",
        "plan_name": "日度无限包",
        "plan_kind": "unlimited",
        ...
    },

    # 新增有限额度套餐
    {
        "plan_code": "daily-100usd-quota",
        "plan_name": "日卡有限包（100美元/天）",
        "plan_kind": "daily_quota",
        "duration_mode": "day",
        "duration_days": 1,
        "quota_metric": "cost_usd",
        "quota_value": Decimal("100"),
        "reset_period": "day",
        "reset_timezone": "Asia/Shanghai",
        "sort_order": 70,
        "description": "1 天有效，每天 100 美元额度",
    },
    {
        "plan_code": "monthly-10m-token-quota",
        "plan_name": "月卡有限包（1000万Token/天）",
        "plan_kind": "daily_quota",
        "duration_mode": "month",
        "duration_days": 30,
        "quota_metric": "total_tokens",
        "quota_value": Decimal("10000000"),
        "reset_period": "day",
        "reset_timezone": "Asia/Shanghai",
        "sort_order": 80,
        "description": "30 天有效，每天 1000 万 Token",
    },
    {
        "plan_code": "quarterly-50usd-quota",
        "plan_name": "季度有限包（50美元/天）",
        "plan_kind": "daily_quota",
        "duration_mode": "custom",
        "duration_days": 90,
        "quota_metric": "cost_usd",
        "quota_value": Decimal("50"),
        "reset_period": "day",
        "reset_timezone": "Asia/Shanghai",
        "sort_order": 90,
        "description": "90 天有效，每天 50 美元额度",
    },
]
```

**改动 2：优化额度检查逻辑**
- 位置：`check_quota_before_request` 方法
- 优化：增强错误提示，明确告知用户额度不足和刷新时间
- 示例：
  ```python
  if used_amount >= quota_limit:
      next_reset = cycle_end_at.strftime("%Y-%m-%d %H:%M:%S")
      raise ServiceException(
          429,
          f"今日额度已用完（{used_amount}/{quota_limit} {quota_metric}），"
          f"将于 {next_reset} 自动刷新",
          "QUOTA_EXCEEDED"
      )
  ```

**改动 3：增加额度查询接口**
- 新增方法：`get_user_quota_status(db, user_id) -> dict`
- 返回：
  ```python
  {
      "has_subscription": True,
      "plan_name": "月卡有限包",
      "plan_kind": "daily_quota",
      "quota_metric": "total_tokens",
      "quota_limit": 10000000,
      "used_amount": 5230000,
      "remaining": 4770000,
      "usage_percentage": 52.3,
      "cycle_date": "2026-04-25",
      "next_reset_at": "2026-04-26 00:00:00"
  }
  ```

#### 3.2.2 定时任务：自动刷新额度

**文件**: `backend/app/scheduler/quota_refresh.py`（新建）

**功能**：
1. 每小时检查一次是否有需要刷新的周期
2. 清理 30 天前的旧周期记录（保留历史数据用于统计）

**实现**：
```python
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

def refresh_expired_cycles():
    """清理过期的使用周期记录"""
    db = next(get_db())
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        deleted = db.query(SubscriptionUsageCycle).filter(
            SubscriptionUsageCycle.cycle_end_at < cutoff_date
        ).delete()
        db.commit()
        logger.info(f"Cleaned {deleted} expired usage cycles")
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(refresh_expired_cycles, 'cron', hour='*/1')  # 每小时执行
scheduler.start()
```

**注册位置**: `backend/app/main.py`
```python
from app.scheduler import quota_refresh

@app.on_event("startup")
async def startup_event():
    quota_refresh.scheduler.start()
```

#### 3.2.3 API 接口改动

**文件**: `backend/app/api/admin/subscription.py`

**改动 1：创建套餐模板时的参数校验**
- 位置：`create_subscription_plan` 接口
- 校验：
  - 当 `plan_kind=daily_quota` 时，`quota_metric` 和 `quota_value` 必填
  - 当 `plan_kind=unlimited` 时，`quota_metric` 和 `quota_value` 可为空

**改动 2：新增用户额度查询接口**
```python
@router.get("/user/{user_id}/quota", response_model=ResponseModel)
def get_user_quota_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """查询用户当前额度状态"""
    status = SubscriptionService.get_user_quota_status(db, user_id)
    return ResponseModel(data=status)
```

**文件**: `backend/app/api/user/profile.py`（新增用户端接口）

**新增接口**：
```python
@router.get("/quota", response_model=ResponseModel)
def get_my_quota_status(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """查询当前用户的额度状态"""
    status = SubscriptionService.get_user_quota_status(db, current_user.id)
    return ResponseModel(data=status)
```

### 3.3 前端改动

#### 3.3.1 管理员套餐管理页面

**文件**: `frontend/src/pages/admin/subscription.tsx`（假设路径）

**改动 1：套餐创建表单**
- 增加 `plan_kind` 单选框：
  - 无限额度（unlimited）
  - 每日限额（daily_quota）
- 当选择 "每日限额" 时，显示额度配置：
  - 额度口径：Token 数量 / 成本（美元）
  - 每日额度值：输入框

**改动 2：套餐列表展示**
- 显示 `plan_kind` 标签：
  - 无限额度：绿色标签 "无限"
  - 每日限额：蓝色标签 "限额"
- 显示额度信息：
  - 例如："每天 1000 万 Token" 或 "每天 100 美元"

#### 3.3.2 用户额度展示

**文件**: `frontend/src/components/QuotaDisplay.tsx`（新建）

**功能**：
- 显示当前套餐信息
- 显示今日额度使用情况（进度条）
- 显示下次刷新时间

**示例 UI**：
```
┌─────────────────────────────────────┐
│ 当前套餐：月卡有限包                │
│ 今日额度：523 万 / 1000 万 Token    │
│ [████████░░░░░░░░░░] 52.3%          │
│ 下次刷新：2026-04-26 00:00:00       │
└─────────────────────────────────────┘
```

---

## 四、实施步骤

### 阶段 1：后端核心功能（6 步）

1. **完善内置套餐模板**
   - 文件：`backend/app/services/subscription_service.py`
   - 任务：在 `BUILTIN_PLANS` 中添加有限额度套餐模板
   - 验证：运行 `init_builtin_plans` 方法，检查数据库

2. **优化额度检查逻辑**
   - 文件：`backend/app/services/subscription_service.py`
   - 任务：增强 `check_quota_before_request` 的错误提示
   - 验证：模拟额度耗尽场景，检查错误信息

3. **新增额度查询方法**
   - 文件：`backend/app/services/subscription_service.py`
   - 任务：实现 `get_user_quota_status` 方法
   - 验证：单元测试覆盖各种场景

4. **创建定时任务**
   - 文件：`backend/app/scheduler/quota_refresh.py`（新建）
   - 任务：实现旧周期清理逻辑
   - 验证：手动触发，检查日志

5. **注册定时任务**
   - 文件：`backend/app/main.py`
   - 任务：在 `startup_event` 中启动调度器
   - 验证：启动服务，检查调度器日志

6. **新增 API 接口**
   - 文件：`backend/app/api/admin/subscription.py`
   - 文件：`backend/app/api/user/profile.py`
   - 任务：添加额度查询接口
   - 验证：Postman 测试接口

### 阶段 2：前端展示（4 步）

7. **管理员套餐创建表单**
   - 文件：`frontend/src/pages/admin/subscription.tsx`
   - 任务：增加 `plan_kind` 和额度配置字段
   - 验证：创建有限额度套餐，检查数据库

8. **管理员套餐列表展示**
   - 文件：`frontend/src/pages/admin/subscription.tsx`
   - 任务：显示套餐类型和额度信息
   - 验证：查看套餐列表，确认信息完整

9. **用户额度展示组件**
   - 文件：`frontend/src/components/QuotaDisplay.tsx`（新建）
   - 任务：实现额度展示 UI
   - 验证：查看组件渲染效果

10. **集成额度展示到用户页面**
    - 文件：`frontend/src/pages/user/dashboard.tsx`
    - 任务：在用户仪表盘显示额度信息
    - 验证：用户登录后查看额度

### 阶段 3：测试与优化（3 步）

11. **单元测试**
    - 文件：`backend/app/test/test_subscription_quota.py`（新建）
    - 任务：覆盖额度检查、扣减、刷新等场景
    - 验证：`pytest` 通过所有测试

12. **集成测试**
    - 任务：模拟完整流程
      1. 管理员创建有限额度套餐
      2. 为用户开通套餐
      3. 用户调用 API 消耗额度
      4. 额度耗尽后拒绝请求
      5. 跨天后额度自动刷新
    - 验证：所有步骤正常运行

13. **文档更新**
    - 文件：`docs/subscription-quota-guide.md`（新建）
    - 任务：编写套餐额度功能使用文档
    - 内容：
      - 套餐类型说明
      - 额度计量方式
      - 刷新机制
      - API 接口文档

---

## 五、风险与注意事项

### 5.1 技术风险

**风险 1：时区处理错误**
- 描述：跨时区用户可能遇到额度刷新时间不准确
- 缓解：使用 `zoneinfo` 库，严格按照 `reset_timezone` 计算
- 测试：覆盖多个时区场景

**风险 2：并发扣减额度**
- 描述：高并发场景下可能出现超额扣减
- 缓解：使用数据库行锁（`with_for_update()`）
- 测试：压力测试验证

**风险 3：定时任务失败**
- 描述：调度器异常导致旧数据堆积
- 缓解：增加异常捕获和告警日志
- 监控：定期检查 `SubscriptionUsageCycle` 表大小

### 5.2 业务风险

**风险 1：用户体验下降**
- 描述：额度耗尽后用户无法使用服务
- 缓解：
  - 提前预警（剩余 10% 时提示）
  - 提供余额充值入口
  - 清晰展示刷新时间

**风险 2：套餐配置错误**
- 描述：管理员配置错误导致用户权益受损
- 缓解：
  - 表单校验
  - 配置预览
  - 操作日志记录

### 5.3 兼容性

**向后兼容**：
- ✅ 现有无限套餐不受影响
- ✅ 现有 API 接口保持不变
- ✅ 数据库表结构无需迁移

---

## 六、验收标准

### 6.1 功能验收

- [ ] 管理员可创建有限额度套餐（Token 和成本两种口径）
- [ ] 管理员可为用户开通有限额度套餐
- [ ] 用户调用 API 时正确扣减额度
- [ ] 额度耗尽后拒绝请求，返回明确错误信息
- [ ] 每日 00:00（按时区）自动刷新额度
- [ ] 用户可查看当前额度使用情况
- [ ] 管理员可查看所有用户的额度状态

### 6.2 性能验收

- [ ] 额度检查响应时间 < 50ms
- [ ] 支持 1000+ 并发请求不出现超额扣减
- [ ] 定时任务执行时间 < 5 秒

### 6.3 测试覆盖

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试覆盖核心流程
- [ ] 压力测试验证并发安全

---

## 七、后续优化方向

1. **多周期支持**：支持按周、按月刷新额度
2. **额度预警**：剩余 10% 时发送通知
3. **额度转移**：支持将未用完的额度转移到下一周期
4. **套餐组合**：支持用户同时拥有多个套餐
5. **额度统计**：提供额度使用趋势图表

---

## 八、总结

本方案基于现有系统的 `daily_quota` 机制，无需修改数据库表结构，仅需：
1. 完善内置套餐模板
2. 优化额度检查和查询逻辑
3. 增加定时任务清理旧数据
4. 完善前端展示

**优势**：
- ✅ 改动量小，风险可控
- ✅ 向后兼容，不影响现有功能
- ✅ 代码复用度高，维护成本低

**预计工作量**：
- 后端开发：3-4 天
- 前端开发：2-3 天
- 测试与优化：2 天
- 总计：7-9 天
