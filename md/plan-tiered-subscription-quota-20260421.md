## Plan v2

本版基于最新补充需求修订：

- 先按当前已售出的 6 个套餐模板落地
- 之前大量已开通的“按天数无限额度套餐”必须保持兼容
- 管理员后续可以自行配置新的每日刷新额度模板
  - 例如 `1 天 1000 万 Token/天`
  - 或 `1 天 2000 万 Token/天`

## 用户原始需求

当前系统已经支持两类权益：

- 管理端 `/admin/subscription` 可给用户开通日卡、月卡、季卡、年卡等时间套餐
- 管理端 `/admin/users` 可给用户充值余额

但现有时间套餐开通后不会扣除用户余额，等价于“在有效期内无限额度使用”。

本次希望扩展出更多套餐形态，例如：

- 日卡有限套餐
- 月卡有限套餐
- 自定义时间套餐
- 套餐有效期内，按“每天额度”限制使用
- 每天额度既可以按美元计，也可以按 Token 计
- 次日自动刷新额度

业务目标不是单纯新增几个套餐名称，而是形成一套更丰富的套餐体系，用于吸引不同消费层级的客户，同时限制部分客户无节制占用无限资源。

当前优先要落地的套餐模板来自现有对外套餐图：

- 无限包
  - 日度无限包
  - 周度无限包
  - 月度无限包
- 轻量流量包
  - 日度畅享包：每天 `10,000,000 Token`
  - 周度畅享包：有效期 7 天，每天 `10,000,000 Token`
  - 月度畅享包：有效期 30 天，每天 `10,000,000 Token`

并且管理员后续要能自行增加更多同类模板，例如：

- `1 天 / 每天 20,000,000 Token`
- `30 天 / 每天 5,000,000 Token`
- `7 天 / 每天 100 美元额度`

## 当前项目现状

### 1. 当前“套餐”本质上只有两态：余额模式 / 无限时间模式

现有用户状态保存在：

- `backend/app/models/user.py`
- `sql/init.sql`

核心字段只有：

- `subscription_type`
  - 当前注释语义为 `balance=按量计费, unlimited=时间套餐`
- `subscription_expires_at`

也就是说，系统目前没有“有限额度套餐”的用户态表达能力。

### 2. 当前套餐记录只记录时间段，不记录额度规则

现有套餐记录模型在：

- `backend/app/models/log.py` 中的 `UserSubscription`
- `backend/app/services/subscription_service.py`
- `backend/app/api/admin/subscription.py`

当前字段只覆盖：

- 套餐名称
- 套餐类型
- 开始时间 / 结束时间
- 状态
- 创建人

缺少以下核心字段：

- 套餐模板来源
- 套餐是否无限 / 是否限额
- 限额口径（USD / Token / 图片积分）
- 每周期额度
- 周期类型（每天刷新）
- 刷新时区
- 实际生效快照

因此现有 `user_subscription` 结构不足以承载“月卡，每天 100 美元额度”这类需求。

### 3. 当前请求扣费链路只区分“扣余额”与“不扣余额”

核心逻辑在：

- `backend/app/services/proxy_service.py`
- `backend/app/core/dependencies.py`

当前行为是：

- `subscription_type == "balance"`
  - 请求前检查 `user_balance.balance > 0`
  - 请求成功后按 `total_cost` 扣余额
- `subscription_type != "balance"`
  - 不扣余额
  - 仅记录 `billing_mode="subscription"` 的消费日志
  - 套餐是否过期只在鉴权处校验

这意味着：

- 当前无限套餐用户不会被额度限制
- 请求链路里没有“检查套餐剩余额度”的预检
- 也没有“按天累计用量”的数据结构

### 4. 当前日志能统计套餐期间理论消费，但不能表达“周期额度”

现有统计主要依赖：

- `request_log`
- `consumption_record`
- `SubscriptionService.get_subscription_usage_detail`
- `LogService`

当前可以统计：

- 某个套餐期间的请求数
- 某个套餐期间的 token 总量
- 某个套餐期间的理论金额

但不能统计：

- 今天已经用了多少日额度
- 今天还剩多少额度
- 该次请求占用了哪个额度周期
- 某个用户是否因为“当日额度用尽”被拦截

### 5. 当前管理端只能“直接开通套餐”，不能“配置套餐模板”

当前前端页面：

- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/views/admin/UserManage.vue`

现状是：

- `/admin/subscription` 只有一个简单开通表单
- 管理员只能按用户 ID + 套餐类型 + 天数直接发放套餐
- 没有套餐模板管理
- 没有额度规则管理
- 没有“月卡但每日限额”的配置入口

这与“我要先配置一批套餐，再按套餐开通给客户”的业务目标不一致。

### 6. 当前没有自动刷新日额度的基础设施

当前定时任务体系在：

- `backend/app/tasks/__init__.py`
- `backend/app/main.py`

现有 scheduler 仅负责渠道健康检查。

订阅相关现状是：

- `SubscriptionService.check_and_expire_subscriptions()` 已存在
- `/api/admin/subscription/check-expired` 已存在
- 但没有真正挂到调度器里自动执行
- 更没有“额度日切刷新”相关任务

### 7. 当前 SQL 初始化脚本与订阅代码存在脱节

本次分析发现一个比较重要的工程问题：

- `backend/app/models/log.py` 中已存在 `UserSubscription`
- `backend/app/services/subscription_service.py` 已基于 `user_subscription` 工作
- 但 `sql/init.sql` 和 `backend/sql/init.sql` 里没有 `user_subscription` 建表语句
- 两套 init SQL 对 `consumption_record` 的字段也未完全同步

这说明订阅模块当前在“运行库 / ORM / 初始化脚本”之间已经有结构漂移，后续扩展前必须先统一。

## 核心设计判断

### 判断 1：不要继续只扩展 `monthly / quarterly / yearly / custom` 枚举

如果继续沿当前思路，仅在现有接口里增加几个布尔字段或额度字段，会很快失控：

- 日卡无限
- 日卡限额
- 月卡无限
- 月卡每日限额
- 月卡总限额
- 自定义时长每日限额

这些组合会让“套餐类型枚举”越来越多，后续很难维护。

### 判断 2：应该升级为“套餐模板 + 用户订阅实例 + 周期额度”

更稳妥的建模方式是：

1. 套餐模板
   - 管理员配置“卖什么套餐”
2. 用户订阅实例
   - 记录“某个用户买了哪一个套餐，生效区间是什么”
3. 周期额度
   - 记录“这个订阅在今天这个周期内已经用了多少”

这样才能同时支持：

- 无限时间套餐
- 每日限额套餐
- 未来扩展总额度套餐
- 未来扩展图片积分套餐

### 判断 3：日额度刷新不建议依赖“每天零点批量重置”

更好的做法不是“凌晨跑一批 UPDATE 把所有用户额度清零”，而是：

- 根据业务时区计算“当前属于哪个额度周期”
- 请求到来时按周期惰性创建 / 读取用量记录
- 新的一天自然对应新的周期记录

这样有几个好处：

- 不依赖凌晨批处理成功
- 不会对全部活跃订阅做全量扫描
- 支持以后扩展周额度 / 月额度
- 实现上更接近账本模型，便于审计

### 判断 4：余额钱包应继续与套餐额度解耦

当前余额充值能力是成熟链路，建议保留。

推荐关系：

- `余额` 是按量钱包
- `套餐` 是时间权益
- `日额度` 是套餐内的限制规则

也就是：

- 套餐用户不一定不需要余额
- 余额用户也不一定有套餐
- 后续甚至可以支持“套餐额度用尽后切余额”的兜底策略

但首期建议先做：

- 套餐额度耗尽时直接拦截
- 不自动切余额

理由是业务语义更清晰，风控更可控。

## 首期落地范围

### 本期必须完成

- 保留旧的 `balance + unlimited` 逻辑兼容
- 增加套餐模板能力
- 预置并支持你当前图里的 6 个套餐
- 支持管理员新增自定义“每日刷新额度”套餐模板
- 首期限额套餐至少支持：
  - `Token/天`
  - 数据结构预留 `USD/天`
- 管理员可基于模板给用户开通套餐
- 请求成功后正确累计到“当日额度已用”
- 次日自动按业务日期刷新

### 本期暂不强制完成

- 前台自助购买
- 自动支付与订单系统
- 套餐耗尽自动切余额
- 图片积分类套餐模板

## 目标

### 业务目标

- 支持管理员预先配置多种套餐模板
- 支持给用户开通：
  - 无限时间套餐
  - 时间有效 + 每日限额套餐
- 每日限额支持至少两种口径：
  - 美元额度
  - Token 额度
- 次日额度自动刷新
- 管理端、用户端、日志端都能看见当前套餐与额度消耗

### 技术目标

- 保持现有余额充值链路不受影响
- 保持现有无限套餐链路可继续工作
- 请求执行前可识别套餐是否可用
- 请求成功后正确结算到对应额度周期
- 套餐过期与额度刷新具备清晰的数据边界

## 非目标

- 本期不改动图片积分套餐销售逻辑，但数据结构应预留扩展位
- 本期不引入支付、订单、自动扣款
- 本期不做套餐自助购买页面，仅覆盖管理端配置与发放
- 本期不处理历史老日志回填到“日额度周期”维度，除非后续明确要求补偿脚本

## 技术方案设计

### 方案总览

推荐将本次改造拆为 5 层：

1. 数据层
   - 新增套餐模板、套餐周期用量表
   - 扩展用户订阅和消费日志字段
2. 服务层
   - 抽象“当前有效权益解析”和“额度周期结算”
3. 请求计费层
   - 在代理请求入口增加套餐额度预检与结算
4. 管理端
   - 支持套餐模板 CRUD + 发放套餐
5. 用户端
   - 展示当前套餐、今日已用 / 剩余额度

## 推荐业务模型

### 模型一：套餐模板 `subscription_plan`

作用：

- 由管理员维护可售套餐目录

建议字段：

- `id`
- `plan_code`
  - 英文 kebab-case，便于程序引用
- `plan_name`
  - 如 `日卡 100 美元/天`
- `plan_kind`
  - `unlimited`
  - `daily_quota`
- `duration_mode`
  - `day`
  - `month`
  - `quarter`
  - `year`
  - `custom`
- `duration_days`
- `quota_metric`
  - `cost_usd`
  - `total_tokens`
  - 预留 `image_credits`
- `quota_value`
  - 建议 `DECIMAL(20,6)`
- `reset_period`
  - 首期固定 `day`
- `reset_timezone`
  - 首期默认 `Asia/Shanghai`
- `status`
  - `active / inactive`
- `description`
- `created_at`
- `updated_at`

说明：

- 不建议把套餐规则直接塞进 `system_config` 或 `sys_user`
- 模板表是未来做前台购买、订单系统的必要基础

### 当前套餐模板与数据映射

建议首批初始化 6 个模板：

1. `daily-unlimited`
   - `plan_name=日度无限包`
   - `plan_kind=unlimited`
   - `duration_mode=day`
   - `duration_days=1`

2. `weekly-unlimited`
   - `plan_name=周度无限包`
   - `plan_kind=unlimited`
   - `duration_mode=custom`
   - `duration_days=7`

3. `monthly-unlimited`
   - `plan_name=月度无限包`
   - `plan_kind=unlimited`
   - `duration_mode=month`
   - `duration_days=30`

4. `daily-10m-token`
   - `plan_name=日度畅享包`
   - `plan_kind=daily_quota`
   - `duration_mode=day`
   - `duration_days=1`
   - `quota_metric=total_tokens`
   - `quota_value=10000000`

5. `weekly-10m-token`
   - `plan_name=周度畅享包`
   - `plan_kind=daily_quota`
   - `duration_mode=custom`
   - `duration_days=7`
   - `quota_metric=total_tokens`
   - `quota_value=10000000`

6. `monthly-10m-token`
   - `plan_name=月度畅享包`
   - `plan_kind=daily_quota`
   - `duration_mode=month`
   - `duration_days=30`
   - `quota_metric=total_tokens`
   - `quota_value=10000000`

后续管理员如果想配置：

- `1 天 2000 万 Token/天`

本质只是再新建一条模板：

- `duration_days=1`
- `plan_kind=daily_quota`
- `quota_metric=total_tokens`
- `quota_value=20000000`

### 模型二：用户订阅实例 `user_subscription`

现有表建议保留，但要扩展为“用户已购买 / 已发放的实际权益快照”。

建议新增字段：

- `plan_id`
- `plan_kind_snapshot`
- `duration_days_snapshot`
- `quota_metric`
- `quota_value`
- `reset_period`
- `reset_timezone`
- `status`
- `cancelled_at`

说明：

- 发放成功后应写入快照，避免管理员后续修改模板影响已生效用户
- 当前表里只有 `plan_name / plan_type / start_time / end_time`，不够用

### 模型三：额度周期用量 `subscription_usage_cycle`

这是本次最关键的新表。

作用：

- 存储某个用户订阅在某个周期内的累计用量
- 用于“每天 100 美元 / 1000 万 Token”的实时判定

建议字段：

- `id`
- `subscription_id`
- `user_id`
- `cycle_date`
  - 业务日期，例如 `2026-04-21`
- `cycle_start_at`
- `cycle_end_at`
- `quota_metric`
- `quota_limit`
- `used_amount`
- `request_count`
- `last_request_id`
- `created_at`
- `updated_at`

唯一索引建议：

- `unique(subscription_id, cycle_date)`

说明：

- `used_amount` 建议统一使用 `DECIMAL(20,6)`
- 对于 `Token` 套餐，按整数写入即可
- 对于 `cost_usd` 套餐，写实际 `total_cost`

### 模型四：用户当前计费模式缓存 `sys_user`

建议保留当前 `sys_user.subscription_type` 作为“快速路由字段”，但扩展语义为：

- `balance`
- `unlimited`
- `quota`

并继续保留：

- `subscription_expires_at`

原因：

- 当前鉴权和代理入口已经严重依赖该字段
- 直接删除会让改造面过大
- 作为“当前用户默认权益模式缓存”仍有价值

但它不再是完整真相，完整真相应以 `user_subscription` 为准。

### 旧无限套餐兼容策略

你已经明确说明：

- 线上有大量老用户开通的是现有包月无限额度套餐

因此本期必须保证：

- 旧接口 `activate_subscription(user_id, plan_name, plan_type, duration_days)` 仍可继续开通无限套餐
- 已有 `subscription_type=unlimited` 用户不需要迁移后才能继续使用
- 新模板化能力上线后：
  - 旧无限套餐记录视为 `unlimited` 快照订阅
  - 新发放的无限套餐优先走模板接口

建议兼容落地方式：

- 保留原 `/api/admin/subscription/activate` 接口
  - 作为“旧无限套餐开通接口”
- 新增模板管理与模板发放接口
  - 用于新套餐体系

这样可以先完成能力扩展，不阻断现有运营动作。

### 多个订阅并存时的生效规则

这一点必须在实现前先定死，否则后端解析当前权益会变得非常混乱。

首期建议规则：

- 同一用户同一时刻只允许一个“当前生效订阅”
- 新发放套餐默认采用“顺延”策略
  - 如果用户当前已有未过期套餐
  - 新套餐从当前套餐结束时间后开始生效
- 管理端如需强制立即生效，必须显式选择“立即覆盖”

这样可以避免：

- 老无限套餐和新限额套餐重叠
- 两个限额套餐同一天同时生效
- 服务层无法判断到底该用哪个 `subscription_usage_cycle`

因此用户订阅实例建议额外补充：

- `activation_mode`
  - `append`
  - `override`
- `activated_at`
- 预留 `superseded_by_subscription_id`

## 为什么不建议把“日额度”直接挂在 `sys_user`

例如新增：

- `daily_quota_metric`
- `daily_quota_value`
- `daily_quota_used`

这种方案短期看简单，长期会有明显问题：

- 无法支持多个套餐模板
- 无法保留历史发放记录
- 无法支持续费叠加与快照
- 无法按订阅实例审计
- 难以扩展到未来的月额度、总额度、试用包

所以不推荐。

## 请求执行链路改造

### 1. 鉴权阶段

涉及：

- `backend/app/core/dependencies.py`

改造目标：

- `subscription_type == "unlimited"` 时继续检查过期
- `subscription_type == "quota"` 时同样检查是否存在有效套餐且未过期

若无有效套餐：

- 返回 `SUBSCRIPTION_EXPIRED`

### 2. 请求前额度预检

涉及：

- `backend/app/services/proxy_service.py`

建议新增统一入口，例如：

- `SubscriptionService.resolve_active_entitlement(...)`
- `SubscriptionService.check_quota_before_request(...)`

逻辑：

1. 若 `balance` 模式
   - 维持现有余额校验
2. 若 `unlimited` 模式
   - 直接放行
3. 若 `quota` 模式
   - 找到当前有效订阅
   - 根据业务时区计算当前 `cycle_date`
   - 读取或创建 `subscription_usage_cycle`
   - 判断 `used_amount >= quota_limit` 时直接拒绝

这里需要注意：当前系统有 3 条文本代理入口，都要统一接入，而不是只改一条：

- OpenAI Chat 代理入口
- Anthropic Messages 代理入口
- OpenAI Responses 代理入口

对于你当前首期套餐，关键判定就是：

- 日度畅享包
  - 只允许在 1 天有效期内，每天最多 `10,000,000 Token`
- 周度畅享包
  - 只允许在 7 天有效期内，每天最多 `10,000,000 Token`
- 月度畅享包
  - 只允许在 30 天有效期内，每天最多 `10,000,000 Token`

首期建议返回明确错误码，例如：

- `SUBSCRIPTION_DAILY_QUOTA_EXCEEDED`

### 3. 请求成功后的额度结算

结算口径建议：

- `quota_metric = cost_usd`
  - 使用 `ConsumptionRecord.total_cost`
- `quota_metric = total_tokens`
  - 使用 `ConsumptionRecord.total_tokens`

结算动作：

1. 成功后锁定 `subscription_usage_cycle`
2. 将本次实际消耗累加到 `used_amount`
3. 请求数 `+1`
4. 写入 `consumption_record`
5. 写入 `request_log`

### 4. 请求失败不扣额度

与当前余额 / 图片积分逻辑保持一致：

- 上游失败时只记失败日志
- 不增加周期用量

### 5. 图片积分请求不纳入首期套餐额度

当前系统图片模型走的是独立的 `image_credit` 体系，而不是 token 余额体系。

首期建议明确：

- `daily_quota(total_tokens / cost_usd)` 仅作用于文本请求链路
- 图片生成接口继续沿用现有 `image_credit` 扣费逻辑
- 无限套餐也不改动图片积分逻辑

这样能避免把文本套餐和图片积分体系混在一起，缩小首期改造面。

如果后续要支持“图片生成也走套餐权益”，再单独扩展：

- `quota_metric=image_credits`
- 或单独的图片套餐模板

### 5. 关于“严格硬限制”与“单请求穿透”

这里需要明确一个产品与技术权衡：

#### 方案 A：首期推荐落地方案

- 请求前只校验“当前已用是否达到上限”
- 请求成功后按真实消耗累加

优点：

- 改造面较小
- 复用现有成功后结算链路
- 对当前代码侵入更低

缺点：

- 最后一笔大请求可能把额度打穿一点
- 流式大请求在 `daily_quota` 场景下也存在同样问题

#### 方案 B：二期增强方案

- 请求前做“额度预占”
- 成功后按实际值冲正差额
- 失败后释放预占

优点：

- 更接近硬封顶

缺点：

- 需要引入请求预估与预占状态管理
- 流式请求、失败重试、异常中断时实现复杂度更高

结论：

- 本期 plan 建议先按方案 A 落地
- 在服务设计上预留升级到方案 B 的接口

这样能更快上线套餐分层能力，同时避免第一版过度复杂。

## 日额度刷新策略

### 推荐方案：按业务日期惰性切换

不要做“每天零点批量重置所有用户额度”。

推荐逻辑：

1. 系统维护一个业务时区配置
   - 首期默认 `Asia/Shanghai`
2. 每次请求到来时：
   - 将当前 UTC 时间转换为业务时区
   - 取其自然日作为 `cycle_date`
3. 若当前订阅当天没有 `subscription_usage_cycle`
   - 自动创建新周期记录，`used_amount = 0`

这样第二天的“自动刷新”自然成立。

### 为什么这样更合适

- 不依赖凌晨定时任务是否执行成功
- 没有全表重置压力
- 天然适配“某些用户当天根本没用，不需要生成空记录”
- 以后扩展周刷新 / 月刷新时仍可沿用

## 套餐过期处理

当前已有：

- `SubscriptionService.check_and_expire_subscriptions`

但未接入 scheduler。

建议本期同时补齐：

- 在 `backend/app/tasks/__init__.py` 中新增订阅维护任务
- 至少周期性执行“套餐过期状态同步”

说明：

- 额度日刷新不依赖任务
- 套餐过期状态同步仍建议保留定时处理，避免用户状态缓存长期滞后

## 管理端方案

### `/admin/subscription` 页面建议重构为两块

#### 1. 套餐模板管理

支持：

- 新增模板
- 编辑模板
- 启用 / 停用模板
- 查看模板列表

模板字段建议包含：

- 套餐名称
- 套餐编码
- 时长类型
- 时长天数
- 套餐模式
  - 无限
  - 每日限额
- 限额口径
  - 美元
  - Token
- 每日额度值
- 刷新时区
- 描述

并建议在页面里内置“快速创建模板”能力：

- 日度无限包
- 周度无限包
- 月度无限包
- 日度畅享包（1000 万 Token/天）
- 周度畅享包（1000 万 Token/天）
- 月度畅享包（1000 万 Token/天）

同时允许管理员手工新增：

- 任意天数
- 任意每日 Token 数
- 后续预留每日美元额度

#### 2. 用户套餐发放

支持：

- 选择用户
- 选择模板
- 选择是否立即生效
- 允许自定义开始时间 / 天数覆盖
- 发放后生成 `user_subscription`

### 当前页面的处理建议

当前 `SubscriptionManage.vue` 可保留页面路由，但内部改成 Tab：

- 套餐模板
- 用户开通记录

避免新增太多散乱菜单。

## 用户端展示方案

### Dashboard

涉及：

- `frontend/src/views/user/Dashboard.vue`

建议新增展示：

- 当前计费模式
- 当前套餐名称
- 当前套餐到期时间
- 今日额度
- 今日已用
- 今日剩余

### Balance / Usage 页面

涉及：

- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Profile.vue`

建议新增展示：

- 本次请求是否走套餐额度
- 当前周期剩余额度
- 套餐耗尽提示文案

### Admin 用户列表

涉及：

- `frontend/src/views/admin/UserManage.vue`

建议增强：

- 展示 `无限套餐 / 每日限额套餐 / 按量余额`
- 若为每日限额套餐，显示：
  - 套餐到期时间
  - 今日剩余额度摘要

## 日志与统计方案

### `consumption_record` 建议新增字段

建议新增：

- `subscription_cycle_id`
- `quota_metric`
- `quota_consumed_amount`
- `quota_used_after`
- `quota_cycle_date`

作用：

- 让账本层能准确知道某次消费占用了哪个套餐周期
- 也能清楚知道这次消费是否来自“每日额度套餐”

### `request_log` 建议新增字段

建议新增：

- `subscription_cycle_id`
- `quota_metric`
- `quota_consumed_amount`
- `quota_limit_snapshot`
- `quota_used_after`
- `quota_cycle_date`

### Token 套餐的计量口径要与系统价格倍率解耦

当前 `proxy_service` 会先应用：

- `token_multiplier`

再生成当前账单上的 `input_tokens / output_tokens / total_tokens`。

如果直接拿现有 `total_tokens` 去扣减“每天 1000 万 Token”套餐，会出现问题：

- 一旦系统把 `token_multiplier` 调成 `1.2` 或 `2.0`
- 套餐用户的日额度会被同步放大扣减
- 这和用户购买的“真实 Token 额度”语义不一致

因此首期建议增加一套“原始 token 用量”口径，例如：

- `raw_input_tokens`
- `raw_output_tokens`
- `raw_total_tokens`

或至少新增：

- `quota_token_consumed`

规则是：

- `cost_usd` 套餐按账单成本口径累计
- `total_tokens` 套餐按原始 token 口径累计

不要直接复用价格倍率后的 `total_tokens`。

作用：

- 让前端列表不必二次 join 账本表才能展示

### 统计能力建议

后续可直接支持：

- 某套餐今日使用率
- 某类套餐的平均消耗
- 哪些用户经常打满日额度
- 限额套餐与无限套餐的运营对比

这对于后续继续细分套餐非常有帮助。

## 数据迁移与兼容策略

### 1. 补齐并统一 SQL

本期必须补齐：

- `sql/init.sql`
- `backend/sql/init.sql`
- 新增升级脚本，如：
  - `sql/upgrade_subscription_quota_packages_20260421.sql`
  - `backend/sql/upgrade_subscription_quota_packages_20260421.sql`

至少要统一：

- `user_subscription`
- `subscription_plan`
- `subscription_usage_cycle`
- `consumption_record` 扩展字段
- `request_log` 扩展字段

### 2. 老用户兼容

现有老用户分两类：

- 余额用户
- 无限套餐用户

兼容规则：

- `balance` 用户不变
- `unlimited` 用户继续可用
- 新增 `quota` 用户作为第三类

### 2.1 已有无限套餐用户

必须确保：

- 原有无限套餐用户无感继续使用
- 不要求先迁移为模板订阅后才能发请求
- 即使短期内数据库里存在“老无限套餐记录 + 新模板套餐记录”并存，服务层也能正确解析当前有效权益

### 2.2 用户摘要接口要同步升级

当前以下接口 / 页面都默认只理解：

- `balance`
- `unlimited`

相关代码至少包括：

- `AuthService.get_current_user_info`
- `AuthService.list_users`
- `/api/user/profile`
- `/api/user/balance`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/admin/UserManage.vue`

因此首期不能只改请求扣费链路，还要同步输出：

- 当前套餐名称
- 套餐模式
- 到期时间
- 今日额度上限
- 今日已用
- 今日剩余

### 3. 老套餐记录兼容

现有 `user_subscription` 历史记录如果已经在线上库存在，可按以下策略兼容：

- 旧记录默认视为 `plan_kind_snapshot = unlimited`
- 不做历史周期用量回填

## 风险点

### 风险 1：并发请求下日额度超用

如果多个请求同时打到同一个用户，需要：

- 对 `subscription_usage_cycle` 使用 `SELECT ... FOR UPDATE`
- 保证写入串行化

### 风险 2：业务时区与服务器 UTC 混用

当前项目大量使用 `datetime.utcnow()`。

如果不显式引入“套餐额度业务时区”，就会出现：

- 用户以为第二天了，但系统还没刷新
- 或系统提前刷新

因此本期必须把“额度周期时区”作为显式规则，而不是隐式跟随服务器。

### 风险 3：初始化脚本与 ORM 再次漂移

这次已经看到订阅模块存在脚本缺口。

因此本期开发时要把：

- ORM
- 升级 SQL
- init SQL

三者同时维护，否则后续部署会继续出问题。

### 风险 4：日志口径不一致

当前：

- 余额模式看 `total_cost`
- 套餐模式更多是“理论成本统计”

新增限额套餐后，必须明确：

- `quota_metric=cost_usd` 才按 `total_cost` 累计
- `quota_metric=total_tokens` 才按 `total_tokens` 累计

不能把两者混用。

## 实施步骤概要

1. 统一并补齐数据库结构，先解决订阅 SQL 脚本缺口
2. 新增套餐模板与额度周期表
3. 扩展 `user_subscription`、`request_log`、`consumption_record`
4. 重构 `SubscriptionService`，支持模板 CRUD、发放、当前有效权益解析
5. 改造 API 鉴权与代理请求预检逻辑，接入 `quota` 模式
6. 改造成功结算链路，把实际用量写入周期表
7. 预置首批 6 个套餐模板，并兼容旧无限套餐
8. 补齐订阅过期调度任务
9. 重构 `/admin/subscription` 管理页
10. 增强 `/admin/users`、用户 Dashboard、账单页展示
11. 补测试与回归验证

## To-Do 拆解

### 数据库与模型

- `sql/init.sql`
  - 补齐 `user_subscription`、`subscription_plan`、`subscription_usage_cycle` 等表
- `backend/sql/init.sql`
  - 与根目录 init SQL 同步，避免双份脚本继续漂移
- `sql/upgrade_subscription_quota_packages_20260421.sql`
  - 新增升级脚本
- `backend/sql/upgrade_subscription_quota_packages_20260421.sql`
  - 后端目录同步升级脚本
- `backend/app/models/user.py`
  - 扩展 `subscription_type` 语义
- `backend/app/models/log.py`
  - 扩展 `UserSubscription` 与日志表字段
  - 新增 `SubscriptionPlan`
  - 新增 `SubscriptionUsageCycle`
- `backend/app/models/__init__.py`
  - 导出新模型

### 后端接口与服务

- `backend/app/api/admin/subscription.py`
  - 新增模板 CRUD
  - 调整用户发放接口
  - 保留旧无限套餐开通接口兼容
- `backend/app/services/subscription_service.py`
  - 重构为模板管理 + 用户订阅实例管理 + 周期额度结算
  - 内置首批模板初始化/查询能力
- `backend/app/services/proxy_service.py`
  - 接入 `quota` 模式预检与成功结算
- `backend/app/core/dependencies.py`
  - 调整 API Key 鉴权中的套餐有效性判断
- `backend/app/services/auth_service.py`
  - 用户列表 / 用户详情返回当前套餐摘要
- `backend/app/services/log_service.py`
  - 支持套餐额度相关日志字段的输出
- `backend/app/schemas/user.py`
  - 增补管理端 / 用户端需要的套餐摘要字段

### 定时任务

- `backend/app/tasks/__init__.py`
  - 增加订阅过期维护任务
- `backend/app/main.py`
  - 启动新的订阅维护任务

### 前端管理端

- `frontend/src/api/subscription.js`
  - 增加套餐模板接口
- `frontend/src/views/admin/SubscriptionManage.vue`
  - 重构为“模板管理 + 用户发放 + 订阅记录”
  - 直接内置你当前 6 个模板的便捷录入/展示
- `frontend/src/views/admin/UserManage.vue`
  - 展示当前套餐模式和当日额度摘要

### 前端用户端

- `frontend/src/views/user/Dashboard.vue`
  - 展示当前套餐、今日额度、剩余额度
- `frontend/src/views/user/BalanceLog.vue`
  - 展示套餐额度计费细节
- `frontend/src/views/user/Profile.vue`
  - 展示基础套餐摘要

### 测试与验证

- 套餐模板 CRUD 正常
- 发放无限套餐正常
- 旧无限套餐用户不回归
- 发放每日美元额度套餐正常
- 发放每日 Token 套餐正常
- 你当前 6 个套餐模板都能正确创建与发放
- 可自定义新增 `1 天 2000 万 Token/天` 模板
- 次日首次请求自动刷新周期
- 套餐过期自动失效
- 余额用户链路不回归
- 无限套餐链路不回归
- 并发请求下周期用量累计正确

## 建议的产品落地顺序

如果你准备按这个 plan 实施，我建议按下面顺序推进，而不是一次做满：

### 第一阶段

- 套餐模板
- 用户发放
- `quota = cost_usd`
- 每日刷新
- 用户端展示剩余额度

这样最容易直接转化成商业套餐。

### 第二阶段

- `quota = total_tokens`
- Admin 维度的套餐运营报表
- 更细的日志展示

### 第三阶段

- 额度预占，解决单请求穿透问题
- 套餐耗尽后自动切余额
- 图片积分套餐模板化

## 最终建议

这次需求如果只是“在当前月卡表单里多加几个字段”，短期能跑，长期一定会反复返工。

更合适的方向是：

- 用 `subscription_plan` 解决“卖什么套餐”
- 用 `user_subscription` 解决“谁买了什么套餐”
- 用 `subscription_usage_cycle` 解决“今天用了多少，还剩多少”

这样既能满足你现在提到的：

- 日卡有限套餐
- 月卡有限套餐
- 自定义时长套餐
- 每天美元额度 / Token 额度

也能为后面继续扩套餐层级留出空间，不会再被“无限套餐 or 余额模式”这两态结构卡住。
