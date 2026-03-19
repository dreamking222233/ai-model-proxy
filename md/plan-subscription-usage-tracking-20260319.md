## 用户原始需求

1. 深度分析当前项目的 `admin/subscription` 页面及相关前后端处理逻辑，当前通过该页面为用户开通套餐后，页面中的套餐记录区域不显示；接口 `GET /api/admin/subscription/list?page=1&page_size=20` 返回 `total=2` 但 `data=null`。
2. 分析并修复开通套餐后的计费逻辑：确认是否扣减用户余额；如果不扣减或用户本身已经欠费，需要记录套餐期间的消费、Token 和金额，并在管理端可查看套餐期间的使用情况，形成独立于余额扣费的套餐使用统计。

## 现状分析

- 前端 `frontend/src/views/admin/SubscriptionManage.vue` 调用 `listAllSubscriptions` 后直接读取 `res.data.items`。
- 后端 `backend/app/api/admin/subscription.py` 使用 `ResponseModel(data=PageResponse(...))` 返回分页结果。
- `backend/app/schemas/common.py` 中的 `PageResponse` 定义为 `data/total/page/page_size`，并没有 `items` 字段，导致 `PageResponse(items=records, ...)` 中的 `items` 被 Pydantic 丢弃，最终出现 `total` 正常但 `data=null` 的返回结构。
- 当前核心计费逻辑在 `backend/app/services/proxy_service.py::_deduct_balance_and_log`：
  - `subscription_type == "balance"` 时，扣减 `user_balance.balance`，并累计 `user_balance.total_consumed`。
  - `subscription_type != "balance"`（即时间套餐模式）时，不扣减余额，但仍会写入 `consumption_record`，记录 token 和理论费用。
- 现有 `consumption_record` 没有标识“这条消费属于哪一个套餐”，管理端也没有套餐维度的汇总/明细接口，因此无法直接展示某次套餐开通期间的使用情况。

## 技术方案设计

### 1. 修复套餐分页返回结构

- 不再让订阅接口返回不兼容的 `PageResponse(items=...)`。
- 将 `admin/user/{id}` 与 `admin/list` 两个接口统一改为与系统其他分页接口一致的结构：
  - `data.items`
  - `data.list`
  - `data.total`
  - `data.page`
  - `data.page_size`
- 前端读取时兼容 `items` 与 `list`，避免后续接口结构调整引发空表格。

### 2. 为消费记录补充套餐归属信息

- 扩展 `consumption_record`：
  - `billing_mode`：`balance` / `subscription`
  - `subscription_id`：关联 `user_subscription.id`
- 在 `ProxyService._deduct_balance_and_log` 中：
  - 按量用户继续走余额扣费；
  - 套餐用户不扣余额，但写消费记录时标注 `billing_mode=subscription`，并绑定当前生效套餐 `subscription_id`。
- 这样即使用户余额为 0 或负数，套餐期内调用也可被完整归档，不影响现有余额体系。

### 3. 套餐维度统计与明细查询

- 在 `SubscriptionService` 中新增：
  - 套餐列表统计汇总：每条套餐附带请求数、token、消费金额等摘要。
  - 单条套餐使用详情：返回套餐基础信息、使用汇总、期间消费明细分页。
- 统计优先基于 `subscription_id` 精确查询。
- 对历史数据增加兼容回补：
  - 若旧记录没有 `subscription_id` 且消费时间落在套餐有效期内，则作为兜底统计来源。

### 4. 管理端页面增强

- 保留现有“开通/续费套餐”和“套餐记录”主视图。
- 套餐记录表中新增套餐使用摘要列：
  - 请求数
  - Token
  - 理论金额
- 新增“查看使用情况”操作，弹出详情弹窗或抽屉，展示：
  - 套餐基本信息
  - 汇总指标
  - 套餐期间消费明细表

## 涉及文件清单

- `backend/app/api/admin/subscription.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/proxy_service.py`
- `backend/app/models/log.py`
- `backend/app/schemas/common.py`
- `frontend/src/api/subscription.js`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `sql/init.sql`
- `sql/upgrade_subscription_usage_tracking_20260319.sql`（新增）
- `md/impl-subscription-usage-tracking-20260319.md`（实施后新增）

## 实施步骤概要

1. 修复套餐分页接口返回结构，确保记录列表可正常返回。
2. 扩展 ORM 与初始化 SQL，为消费记录增加套餐归属字段。
3. 补充升级 SQL，便于现网数据库增量执行。
4. 调整代理计费记录逻辑，写入 `billing_mode/subscription_id`。
5. 在套餐服务层实现套餐列表汇总统计与单套餐明细查询。
6. 暴露新的管理员查询接口，支持套餐使用详情分页。
7. 改造 `admin/subscription` 页面，显示摘要并提供详情查看。
8. 运行必要的静态检查/编译验证。
9. 生成 impl 文档并执行一次自审。
