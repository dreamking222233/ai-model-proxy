## 任务概述

基于现有套餐体系，为系统扩展了“套餐模板 + 用户发放 + 每日额度刷新”的能力，同时保留旧版按天数开通无限套餐的兼容链路。

本次首期支持：

- 日度无限包
- 周度无限包
- 月度无限包
- 日度畅享包（1000 万 Token/天）
- 周度畅享包（1000 万 Token/天）
- 月度畅享包（1000 万 Token/天）
- 管理员自定义新增每日额度套餐模板

## 核心实现

### 1. 数据层

新增 / 扩展了以下结构：

- `subscription_plan`
  - 套餐模板表
- `user_subscription`
  - 扩展为套餐快照实例
- `subscription_usage_cycle`
  - 每日额度周期表
- `request_log`
  - 增加原始 token、套餐周期、额度消耗字段
- `consumption_record`
  - 增加原始 token、套餐周期、额度消耗字段

对应文件：

- `backend/app/models/log.py`
- `backend/sql/init.sql`
- `sql/init.sql`
- `backend/sql/upgrade_subscription_quota_packages_20260421.sql`
- `sql/upgrade_subscription_quota_packages_20260421.sql`

### 2. 后端服务层

重构了 `SubscriptionService`，增加了：

- 默认 6 个套餐模板的初始化能力
- 套餐模板列表 / 新建 / 更新
- 基于模板发放套餐
- 旧版无限套餐开通兼容
- 当前有效套餐解析
- 每日额度周期计算与消耗累计
- 套餐过期状态同步
- 当前套餐摘要输出

对应文件：

- `backend/app/services/subscription_service.py`

### 3. 请求计费链路

文本请求链路统一接入了套餐校验：

- OpenAI Responses
- OpenAI Chat
- Anthropic Messages

实现内容：

- `balance` 用户继续走余额预检
- `quota` 用户在请求前检查当日额度
- 请求成功后按原始 token 或美元成本累计到套餐周期
- 旧 `unlimited` 套餐继续保持不扣余额
- 图片积分请求不纳入首期套餐额度，仍走原有 `image_credit`

对应文件：

- `backend/app/services/proxy_service.py`
- `backend/app/core/dependencies.py`

### 4. 管理端页面

重构了 `/admin/subscription` 页面，拆成：

- 套餐模板
- 发放套餐
- 套餐记录

其中：

- 套餐模板支持新增 / 编辑
- 支持管理员创建 `1 天 2000 万 Token/天` 这类自定义模板
- 套餐发放支持模板发放与旧版无限套餐开通并存
- 套餐记录支持查看当前周期剩余额度与使用明细

对应文件：

- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/api/subscription.js`

### 5. 用户与管理摘要展示

补充了当前套餐摘要输出和显示：

- 用户列表显示每日限额套餐与剩余额度
- 用户仪表盘显示当前套餐和今日剩余额度
- 用户资料页显示当前套餐摘要
- 用户余额接口返回套餐摘要

对应文件：

- `backend/app/services/auth_service.py`
- `backend/app/api/user/balance.py`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`

## 文件变更清单

- `backend/app/models/log.py`
- `backend/app/models/__init__.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/balance_service.py`
- `backend/app/services/log_service.py`
- `backend/app/api/admin/subscription.py`
- `backend/app/api/user/balance.py`
- `backend/app/core/dependencies.py`
- `backend/app/tasks/__init__.py`
- `backend/sql/init.sql`
- `backend/sql/upgrade_subscription_quota_packages_20260421.sql`
- `sql/init.sql`
- `sql/upgrade_subscription_quota_packages_20260421.sql`
- `frontend/src/api/subscription.js`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`

## 测试验证

已完成：

- `python -m py_compile` 校验后端 Python 文件语法通过
- 本地 `modelinvoke` 数据库已执行安全升级脚本并核对关键表结构
- 前端 `npm run build` 已通过

命令：

```bash
python -m py_compile backend/app/models/log.py backend/app/models/__init__.py backend/app/services/subscription_service.py backend/app/services/proxy_service.py backend/app/services/auth_service.py backend/app/services/balance_service.py backend/app/services/log_service.py backend/app/api/admin/subscription.py backend/app/api/user/balance.py backend/app/core/dependencies.py backend/app/tasks/__init__.py
```

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < backend/sql/upgrade_subscription_quota_packages_safe_20260421.sql
```

```bash
npm run build
```

未完成：

- 未做真实接口联调

## 待优化项

- 若后续需要“套餐耗尽后自动切余额”，可在 `SubscriptionService` 上继续扩展兜底策略
- 若后续需要图片套餐，可在现有模板结构上继续增加 `image_credits` 口径
- 若后续需要更严格硬限制，可增加额度预占机制，避免单次大请求打穿额度
