# Plan: subscription-daily-reset-packages

日期：20260425

##1. 背景与目标

当前系统已具备两条并行权益链路：

1. `admin/subscription` 为用户开通时间型套餐
2. `admin/users` 为用户充值余额

你这次的目标不是简单再加几个“日卡/月卡”选项，而是把套餐体系扩展为：

- 无限套餐
- 有限套餐
- 日卡 / 月卡 / 自定义时长套餐
- 套餐在有效期内按“每日额度”限制使用
-额度口径支持：
 - 美元额度（如每天100 美元）
 - Token额度（如每天1000 万 Token）
- 次日自动刷新
- 管理员可配置套餐模板及对应额度规则，再发放给用户

从当前代码看，这套能力的主体已经做了第一阶段落地，并且与本次需求高度匹配，但仍有一些关键缺口需要在本轮方案中明确收口。

---

##2. 当前代码现状分析

###2.1 套餐模型层：已经具备“模板 +订阅实例 + 日周期额度”骨架

现有模型在 `backend/app/models/log.py`：

- `SubscriptionPlan`：套餐模板
- `UserSubscription`：用户订阅实例
- `SubscriptionUsageCycle`：套餐每日用量周期

关键字段已经具备：

- `SubscriptionPlan.plan_kind`：`unlimited` / `daily_quota`
- `SubscriptionPlan.duration_mode`：`day` / `month` / `custom`
- `SubscriptionPlan.duration_days`
- `SubscriptionPlan.quota_metric`：`total_tokens` / `cost_usd`
- `SubscriptionPlan.quota_value`
- `SubscriptionPlan.reset_period`
- `SubscriptionPlan.reset_timezone`

对应代码位置：
- `backend/app/models/log.py:298`
- `backend/app/models/log.py:271`
- `backend/app/models/log.py:320`

这说明当前系统已经不是“只能开无限套餐”的旧状态，而是已经支持：

- 无限包
- 每日限额包
-以模板形式配置
-以实例形式发放给用户
-以自然日周期记录消耗

这和你的目标方向是一致的。

###2.2 SubscriptionService 已经落地“每日额度套餐”核心逻辑

关键实现位于 `backend/app/services/subscription_service.py`：

#### 已实现能力

1. **预置模板**
 - 日度无限包、周度无限包、月度无限包
 - 日度/周度/月度1000 万 Token 每日限额包
 -见 `backend/app/services/subscription_service.py:34`

2. **模板校验与管理**
 - 支持创建/更新套餐模板
 - 校验 `plan_kind`、`quota_metric`、`quota_value`
 -见 `backend/app/services/subscription_service.py:198`

3. **套餐发放**
 - 支持通过模板发放给用户
 - 支持 `append` 顺延 / `override` 覆盖
 -见 `backend/app/services/subscription_service.py:877`

4. **日额度周期惰性创建**
 - 请求到来时按时区计算当前周期
 - 若无当日周期记录则自动创建
 -见 `backend/app/services/subscription_service.py:591`

5. **请求前额度预检**
 - 若是 `daily_quota` 套餐，则在请求前检查剩余额度
 - 可基于预估 token/cost 做超额拦截
 -见 `backend/app/services/subscription_service.py:703`

6. **请求后额度记账**
 - 请求成功后，把实际 token/cost计入周期
 - 写入本次请求消耗及剩余额度快照
 -见 `backend/app/services/subscription_service.py:756`

7. **用户当前套餐摘要**
 - 支持返回当前套餐、套餐类型、当日周期、剩余额度
 -见 `backend/app/services/subscription_service.py:674`

####结论

你的“日/月/自定义时间套餐 + 每天固定额度 + 第二天自动刷新”的核心业务模型，当前后端其实已经具备70%~85% 的现成实现，不需要推翻重做，应该以“扩展和收口”方式推进。

###2.3代理扣费链路已接入套餐额度，不再是单纯“不扣余额”

关键逻辑在 `backend/app/services/proxy_service.py`：

#### 请求前
- `ProxyService._assert_text_request_allowed` 会先刷新订阅状态
- 若用户有生效套餐：
 - 无限套餐直接放行
 - 每日限额套餐执行额度预检
- 若无套餐，则检查余额
-见 `backend/app/services/proxy_service.py:120`

#### 请求后
- 若 `subscription_type == balance`：按余额扣费
- 否则记为 `billing_mode = subscription`
- 对 `daily_quota` 套餐执行 `consume_quota_after_request`
- 并写入：
 - `subscription_id`
 - `subscription_cycle_id`
 - `quota_metric`
 - `quota_consumed_amount`
 - `quota_limit_snapshot`
 - `quota_used_after`
 - `quota_cycle_date`
-见 `backend/app/services/proxy_service.py:7364`

####结论

“套餐用户不扣余额，改为扣套餐额度”这件事目前已经接入主请求链路，并且日志也能审计。

###2.4 管理端页面也已经初步支持模板管理

前端位置：
- `frontend/src/views/admin/SubscriptionManage.vue:1`
- `frontend/src/api/subscription.js:1`

当前页面已支持：

- 套餐模板列表
- 新建/编辑套餐模板
- 模板发放给用户
-旧版无限套餐兼容开通
- 套餐记录查看
- 当前周期额度查看
- 套餐使用详情查看

并且 UI 上已经支持：

- `套餐模式`：无限额度 / 每日限额
- `时长模式`：日卡 / 月卡 / 自定义
- `限额口径`：Token/天 或 美元/天
- `每日额度值`

这与需求方向高度一致。

###2.5 用户管理页已显示套餐摘要，但缓存态还存在一处设计偏差

当前用户列表页 `frontend/src/views/admin/UserManage.vue:83` 已支持展示：

- 按量计费
- 时间套餐
- 每日限额套餐
- 当前剩余额度

但后端 `refresh_user_subscription_state` 存在一个兼容性处理：

- 无论是 unlimited还是 daily_quota
- 都把 `sys_user.subscription_type` 写成 `unlimited`
-见 `backend/app/services/subscription_service.py:583`
- `backend/app/services/subscription_service.py:586`

与此同时，`get_current_subscription_summary` 又会返回真实的 `quota` 摘要。

这导致：

- 明细接口能看出 quota
-但 `sys_user.subscription_type`作为缓存态并不准确
- 前端部分地方如果仅看 `subscription_type` 会出现语义偏差

这块是本轮很值得修正的重点之一。

###2.6 数据库迁移已经覆盖新字段，但初始化脚本一致性仍需确认

已存在升级 SQL：
- `backend/sql/upgrade_subscription_quota_packages_20260421.sql:1`

它已经创建并补齐：

- `subscription_plan`
- `user_subscription`
- `subscription_usage_cycle`
- `request_log` / `consumption_record` 的 quota 审计字段

因此当前不是“从零设计数据库”，而是需要确认以下两点：

1.线上库是否已完整执行迁移
2. `sql/init.sql` / `backend/sql/init.sql` 是否已经与 ORM、升级脚本统一

如果初始化脚本仍落后，后续新环境初始化会出现结构漂移。

---

##3.需求与现状的差距

虽然主体能力已有，但离“真正稳定可运营的套餐体系”还有以下差距。

###3.1 套餐类型表达还不够产品化

当前后端把“是否限额”主要表达为：

- `plan_kind = unlimited`
- `plan_kind = daily_quota`

这已经够支撑首期业务，但从你描述看，业务侧真正想配置的是：

- 日卡有限套餐
- 月卡有限套餐
- 自定义时长有限套餐
- 每天额度按 Token 或美元计

当前实际上是通过 `duration_mode + duration_days + plan_kind + quota_metric + quota_value`组合表达的。

这在技术上没问题，但需要在 plan 中明确：

- 不再新增“月卡有限”“日卡有限”这种额外枚举
- 而是继续坚持模板组合建模

否则会重新回到枚举爆炸问题。

###3.2 reset_period目前默认 day，但没有真正扩成通用周期体系

现在代码默认：
- `DEFAULT_RESET_PERIOD = "day"`
-见 `backend/app/services/subscription_service.py:32`

并且 `_get_cycle_window`只实现了“按天切周期”：
- `backend/app/services/subscription_service.py:183`

也就是说，当前系统真正支持的是：
- 每天刷新

而不是：
- 每周刷新
- 每月刷新
- 每 X 天刷新

这对你当前需求是够的，因为你明确举例是“第二天自动刷新”。

所以本轮方案应该把范围收敛为：
- 首期只支持 `daily reset`
- 字段保留扩展空间，但不在本轮开放更多刷新周期

###3.3 套餐与余额的优先级策略需要明确固化

当前逻辑是：

- 有生效套餐 ->走套餐
- 无套餐 ->走余额
- 套餐额度耗尽 ->直接拦截
- 不自动降级为余额

这与风控上更安全，也和你“有限套餐要真限制住”的诉求一致。

但这个规则要在方案里明确写死，不然之后容易出现业务理解分歧。

推荐首期策略：

1. 套餐优先于余额
2. 套餐有效期内，若是无限套餐则不扣余额
3. 套餐有效期内，若是每日限额套餐则只消耗套餐额度
4. 当日额度用尽直接拦截
5. 不自动回退扣余额
6. 套餐过期后再恢复余额模式

###3.4 sys_user.subscription_type 的缓存兼容设计需要收口

当前这里存在明显历史兼容逻辑：

- `backend/app/models/user.py:28`
- `backend/app/services/subscription_service.py:583`
- `backend/app/services/proxy_service.py:7372`

问题是：

- `sys_user.subscription_type`既被当成缓存字段
- 又被部分逻辑当成真实计费模式判断

当前通过“请求前刷新订阅状态”规避了大部分问题，但仍有几个隐患：

1. 用户列表返回的 `subscription_type` 与实际套餐类型可能不一致
2. 某些旧逻辑如果只看缓存态，可能误判 quota/unlimited
3. 前端展示层容易分裂：有些地方看 summary，有些地方看 subscription_type

因此建议本轮明确：

- `sys_user.subscription_type`只做粗粒度缓存态
- 所有展示与计费判断以 `SubscriptionService.get_current_subscription_summary()` / `resolve_active_subscription()` 为准
- 如条件允许，兼容升级为真正支持 `balance/unlimited/quota`

这里需要根据线上表结构兼容情况决定是否升级字段注释与写值策略。

###3.5 管理端虽然已有模板页，但还缺少“产品运营级”配置约束

当前前端模板表单可用，但从运营使用角度还可进一步增强：

1. 套餐编码规范校验不够强
2. `duration_mode` 与 `duration_days` 的关系缺少显式引导
 - 日卡默认1 天
 - 月卡建议默认30 天
 - 自定义则允许任意天数
3. `plan_kind = unlimited` 时应更明确隐藏/禁用额度字段
4. `plan_kind = daily_quota` 时描述文案可更清晰
5. 可考虑增加模板示例或快速填充

这不是架构阻塞项，但属于落地时的重要交互优化点。

###3.6过期检查存在接口，但自动任务挂载需确认

当前已有：
- `SubscriptionService.check_and_expire_subscriptions` `backend/app/services/subscription_service.py:1082`
- 管理接口 `/api/admin/subscription/check-expired` `backend/app/api/admin/subscription.py:178`

但需要确认它是否已真正挂到 scheduler。

不过就“每日额度刷新”本身而言，当前采用的是**惰性新建周期**，并不依赖零点任务做 reset，这个设计是正确的。

因此调度器在本需求中的作用主要是：

- 定时清理/纠正过期套餐缓存态
-不是做额度刷新

---

##4. 本次实施目标定义

##4.1 本期必须实现

1. 支持管理员配置以下套餐模板：
 - 日卡无限套餐
 - 月卡无限套餐
 - 自定义时长无限套餐
 - 日卡每日限额套餐
 - 月卡每日限额套餐
 - 自定义时长每日限额套餐

2. 每日限额套餐支持两种额度口径：
 - `cost_usd`
 - `total_tokens`

3. 用户使用时满足以下规则：
 - 套餐有效期内优先走套餐
 - unlimited 不扣余额
 - daily_quota 不扣余额、扣套餐周期额度
 - 当日额度超出直接拦截
 - 次日自动刷新（通过新周期自然生效）

4. 管理端可查看：
 - 套餐模板
 - 套餐记录
 - 当前周期已用/剩余额度
 - 套餐使用明细

5.兼容存量旧版无限套餐开通逻辑

##4.2 本期不做

1. 套餐额度耗尽后自动切余额
2. 总额度套餐（例如30 天总共100 美元）
3. 每周刷新 / 每月刷新额度
4. 图片积分纳入同一套餐模板体系
5. 用户自助购买/支付闭环

这样可以控制改动范围，避免把本次需求扩展成完整计费平台重构。

---

##5. 推荐实施方案

### 阶段一：确认并统一数据结构

####目标
确认现有 ORM、线上库、初始化 SQL 三者一致，防止后续继续出现结构漂移。

####任务
1. 核查以下表是否在目标环境完整存在：
 - `subscription_plan`
 - `user_subscription`
 - `subscription_usage_cycle`

2. 核查以下字段是否存在：
 - `consumption_record.subscription_id`
 - `consumption_record.subscription_cycle_id`
 - `consumption_record.quota_metric`
 - `consumption_record.quota_consumed_amount`
 - `consumption_record.quota_limit_snapshot`
 - `consumption_record.quota_used_after`
 - `consumption_record.quota_cycle_date`
 - `request_log.subscription_cycle_id`
 - `request_log.quota_metric`
 - `request_log.quota_consumed_amount`
 - `request_log.quota_limit_snapshot`
 - `request_log.quota_used_after`
 - `request_log.quota_cycle_date`

3. 对齐：
 - `backend/sql/init.sql`
 - `sql/init.sql`
 -现有 upgrade SQL
 - ORM 定义

####结果
后续新环境可以直接初始化出完整套餐能力，不再依赖补丁迁移拼装。

### 阶段二：收口 subscription_type 缓存语义

####目标
避免 `sys_user.subscription_type` 与真实套餐类型长期不一致。

#### 推荐方案
方案 A（推荐，改动较小）：
- 保持该字段为缓存态
- 在展示和计费逻辑中统一改为优先读取 `subscription_summary`
- `subscription_type`仅保留 `balance/unlimited` 粗分语义

方案 B（更彻底）：
- 真正允许缓存态写入 `balance/unlimited/quota`
- `refresh_user_subscription_state` 对应写真实值
- 全链路兼容 `quota`

#### 本项目建议
从代码看：
- `backend/app/models/user.py:28` 注释已包含 `quota`
- `ProxyService` 与 `dependencies`也已经兼容 `quota`

因此本轮更建议走 **方案 B**：
- active unlimited -> `subscription_type = "unlimited"`
- active daily_quota -> `subscription_type = "quota"`
- no active -> `subscription_type = "balance"`

需要同步检查：
- 用户列表展示
- 登录态返回
-旧兼容测试

### 阶段三：规范套餐模板体系

####目标
把“日卡有限/月卡有限/自定义有限”收敛成统一模板模型，而不是继续新增枚举。

####统一建模方式
- `duration_mode`
 - `day`
 - `month`
 - `custom`
- `duration_days`
 -1 /30 / 自定义
- `plan_kind`
 - `unlimited`
 - `daily_quota`
- `quota_metric`
 - `total_tokens`
 - `cost_usd`
- `quota_value`
 - 每日额度值

#### 示例映射
- 日卡无限套餐
 - `duration_mode=day`
 - `duration_days=1`
 - `plan_kind=unlimited`
- 月卡有限套餐（每天100 美元）
 - `duration_mode=month`
 - `duration_days=30`
 - `plan_kind=daily_quota`
 - `quota_metric=cost_usd`
 - `quota_value=100`
- 自定义45 天有限套餐（每天500 万 token）
 - `duration_mode=custom`
 - `duration_days=45`
 - `plan_kind=daily_quota`
 - `quota_metric=total_tokens`
 - `quota_value=5000000`

####结果
未来新增套餐无需改代码，只需新增模板。

### 阶段四：完善管理端配置体验

####目标
让运营/管理员能稳定配置套餐，而不是必须理解底层字段组合。

#### 后端
- 保持现有 `/api/admin/subscription/plans`结构
- 增加更严格的参数校验：
 - `duration_mode=day` 时默认建议 `duration_days=1`
 - `duration_mode=month` 时默认建议 `duration_days=30`
 - `daily_quota` 必须有 `quota_metric/quota_value`
 - `unlimited` 强制清空 quota 字段

#### 前端
优化 `frontend/src/views/admin/SubscriptionManage.vue`：
1. 模板新建表单增加联动默认值
2. 针对不同套餐类型展示更自然的文案
3. 增加预览摘要，例如：
 - “月卡 / 每天100 美元 / 有效期30 天”
4. 模板列表增加更直观列：
 - 套餐类型摘要
 - 重置时区
 - 每日额度说明

####结果
管理员能直接配置“日/月/自定义 + 每日额度”套餐，不需要理解内部实现细节。

### 阶段五：补齐订阅状态与展示一致性

####目标
让 admin/users、admin/subscription、用户个人中心看到的是同一套真实状态。

#### 涉及位置
- `backend/app/services/auth_service.py:196`
- `backend/app/api/user/balance.py:16`
- `frontend/src/views/admin/UserManage.vue:83`
-可能还有 dashboard/profile 页面

####需要统一的展示口径
返回给前端的统一结构应以 `subscription_summary` 为准，至少包含：
- `subscription_type`
- `plan_name`
- `plan_code`
- `plan_kind`
- `start_time`
- `end_time`
- `quota_metric`
- `quota_value`
- `current_cycle.used_amount`
- `current_cycle.remaining_amount`
- `current_cycle.cycle_date`

####结果
所有页面都能正确显示：
- 当前是什么套餐
- 是无限还是每日限额
- 今天用了多少
- 今天还剩多少
-何时到期

### 阶段六：校验请求链路边界情况

####目标
确保每日限额套餐在高并发与边界时刻行为稳定。

####重点验证
1. 同用户并发请求时额度是否超扣
 - 当前 `_get_or_create_cycle(..., lock=True)` 已具备一定并发保护
 -需补测试验证

2. 跨日切换时区边界
 - `Asia/Shanghai` 下23:59:59 与00:00:01
 -见 `backend/app/services/subscription_service.py:183`

3.预估额度与实际额度差异
 - 请求前预估没超，但实际响应超了怎么办
 - 当前请求后 `consume_quota_after_request` 会再次兜底校验，这是合理的

4. 套餐过期与顺延切换
 - append 模式下新套餐起始时间
 - override 模式下旧套餐取消后是否正确切换

5. 无套餐 + 有余额
6. 有套餐 +余额为0
7. 套餐过期 + 有余额
8. 套餐额度耗尽 +余额充足
 -预期：仍然拦截，不回退余额

### 阶段七：补齐自动运维任务

####目标
让过期套餐状态自动收敛。

####方案
在现有 scheduler 中补挂：
- 定时执行 `SubscriptionService.check_and_expire_subscriptions()`

说明：
-这不是用来“刷新每日额度”
- 每日额度刷新仍然通过周期自然切换完成
- scheduler只负责过期状态清理与缓存态同步

---

##6.关键设计决策

### 决策1：每日刷新采用“按周期建账”，不做零点批量清零

原因：
- 当前实现已采用正确方向
- 无需批量 UPDATE
- 可审计
- 可自然支持时区
- 后续可扩展周/月周期

### 决策2：套餐与余额保持解耦

原因：
-余额是钱包
- 套餐是权益
- 当前业务更需要“限住套餐用户”，不是“超了继续扣余额”

首期策略：
- 套餐耗尽直接拦截
- 不自动切余额

### 决策3：不再新增业务枚举“日卡有限/月卡有限”等 plan_type

统一通过模板组合表达：
- duration + kind + metric + quota

原因：
- 更稳定
- 更少分支
- 后续更可扩展

### 决策4：真实判断以订阅实例和 summary 为准

不要把 `sys_user.subscription_type`继续当成唯一真相。

---

##7. 推荐实施顺序

### Step1
核查并统一数据库结构与初始化脚本。

### Step2
修正 `refresh_user_subscription_state`，让 `subscription_type` 能真实反映 `balance/unlimited/quota`。

### Step3
检查并补强模板校验逻辑，确保 `daily_quota` 与 `unlimited` 的字段组合始终合法。

### Step4
优化管理端套餐模板表单与展示文案，突出：
- 有效期
- 每日额度
-额度口径
- 时区

### Step5
统一 admin/users、user/profile、user/balance 等页面的套餐摘要展示。

### Step6
补充测试：
- 套餐预检
- 套餐扣减
- 跨日刷新
-过期切换
- append/override
- 套餐与余额边界策略

### Step7
将过期检查任务接入 scheduler。

---

##8. 测试清单

### 后端单测/集成测试

1. 创建 unlimited 模板成功
2. 创建 daily_quota + token 模板成功
3. 创建 daily_quota + usd 模板成功
4. invalid quota_metric 被拒绝
5. quota_value <=0 被拒绝
6. 发放 append 套餐时起止时间正确
7. 发放 override 套餐时旧套餐被取消
8. daily_quota 用户在剩余额度足够时通过
9. daily_quota 用户在请求前预估超额时被拒绝
10. daily_quota 用户在请求后实际超额时被拒绝
11. 跨日后生成新 cycle，额度恢复满额
12. 套餐过期后切回 balance
13. 套餐过期但用户有余额时允许请求
14. 套餐额度用尽但余额充足时仍拦截
15. 用户摘要正确返回 current_cycle

### 前端联调验收

1. admin/subscription 可新增：
 - 日卡无限
 - 月卡无限
 - 日卡每日 token 限额
 - 月卡每日美元限额
 - 自定义时长每日限额
2. 套餐模板列表展示正确
3. 发放套餐成功
4. 套餐记录中可见已用/剩余额度
5. admin/users 可正确显示 quota 套餐类型
6. 用户余额页可正确显示套餐摘要

---

##9. 风险与注意事项

### 风险1：线上库结构与 ORM 不一致

这是当前最现实的风险。
必须先确认升级 SQL 已落地，否则代码虽有、功能不完整。

### 风险2：旧逻辑仍依赖 subscription_type 粗判断

如果只改展示不改缓存策略，可能继续出现：
- 某些页面显示 unlimited
- 某些页面显示 quota

建议统一收口。

### 风险3：cost_usd口径的预估能力弱于 token口径

因为请求前真正能较好预估的是 token，不一定总能精确预估 cost。
但当前方案仍然可行：
- 请求前做尽力预估
- 请求后做最终兜底校验

### 风险4：套餐叠加语义要保持简单

当前只建议支持：
- append
- override

不要在本期引入：
- 多套餐并行生效
- 套餐优先级混算
- 套餐 +余额自动兜底

否则复杂度会显著上升。

---

##10. 最终结论

###结论一
从当前项目代码看，你要的这套“日/月/自定义时间套餐 + 每天固定额度 + 次日自动刷新”的核心能力，其实已经基本建好了，不是从零开始。

###结论二
当前最合适的策略不是重构订阅系统，而是围绕既有实现做 **收口、补齐、统一、产品化**，重点包括：

1.统一数据库结构与初始化脚本
2. 修正 `subscription_type` 缓存态语义
3. 固化“套餐优先、额度耗尽即拦截、不自动切余额”的业务规则
4. 优化管理端模板配置体验
5. 补齐自动过期任务和边界测试

###结论三
如果按最小闭环推进，本次需求的最优落地路径应是：

-以现有 `SubscriptionPlan + UserSubscription + SubscriptionUsageCycle` 为核心
-继续采用“日周期惰性建账”做自动刷新
-统一把“有限套餐”抽象为 `daily_quota`
-通过 `duration_mode + duration_days + quota_metric + quota_value`组合支持日卡、月卡、自定义套餐

这条路径最符合当前项目现状，也最省改动成本。

---

##11. 建议的后续实施文档拆分

如果下一步要正式进入开发，建议拆成三份实施文档：

1. `impl-subscription-daily-reset-packages-20260425.md`
 -记录实际改动文件与接口
2. `review-subscription-daily-reset-packages-20260425.md`
 -记录 review 与回归结果
3. 如需补库：
 - `backend/sql/upgrade_subscription_state_alignment_20260425.sql`
 - 用于修正 `subscription_type`兼容行为或初始化脚本漂移
