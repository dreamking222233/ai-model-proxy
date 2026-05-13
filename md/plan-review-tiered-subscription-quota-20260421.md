## Review Conclusion

方案主方向可行：

- 用 `subscription_plan + user_subscription + subscription_usage_cycle` 支撑当前 6 个套餐与后续自定义每日额度是合理的
- 保留旧 `unlimited` 用户兼容也是必要的
- 日额度按业务日期惰性切换，比零点批量重置更稳

但在正式实施前，需要补齐以下关键约束，否则后续很容易返工。

## 需要补充的点

### 1. 必须定义“多个订阅并存”的生效规则

当前系统老逻辑支持用户续费顺延，新方案如果再引入模板发放而不定义规则，会出现：

- 老无限套餐与新限额套餐重叠
- 两个限额套餐同时生效
- 服务层无法判断当前到底该用哪个订阅

建议：

- 同一时刻只允许一个当前生效订阅
- 新发放默认顺延
- 如需立即替换，管理员显式选择覆盖

### 2. 请求入口不能只改一条

当前文本请求至少有 3 个入口在做余额判断：

- OpenAI Chat
- Anthropic Messages
- OpenAI Responses

如果只改其中一条，套餐额度会被绕过。

建议：

- 抽统一的 entitlement / quota 校验入口
- 三条代理链路全部复用

### 3. Token 套餐不能直接复用现有 `total_tokens`

当前 `proxy_service` 会先应用系统 `token_multiplier`，再写入 `total_tokens`。

如果直接用它来扣“每天 1000 万 Token”套餐，会导致：

- 系统价格倍率变化时
- 套餐用户的 Token 额度也跟着异常缩放

建议：

- `cost_usd` 套餐按账单成本累计
- `total_tokens` 套餐按原始 token 口径累计
- 至少新增 `raw_total_tokens` 或 `quota_token_consumed`

### 4. 首期要明确图片积分请求不纳入套餐额度

当前图片模型走的是独立 `image_credit` 体系。

建议首期明确：

- 套餐限额仅作用于文本请求
- 图片请求继续走图片积分
- 无限套餐也不改动图片积分逻辑

否则首期会把两套计费体系耦在一起，改造面过大。

### 5. 用户侧摘要接口与页面要同步升级

当前很多接口和页面只理解：

- `balance`
- `unlimited`

如果只改扣费逻辑，不改摘要输出，管理端和用户端会看不见新套餐状态。

至少要同步改造：

- `AuthService.get_current_user_info`
- `AuthService.list_users`
- `/api/user/profile`
- `/api/user/balance`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`
- `frontend/src/views/user/BalanceLog.vue`

## 额外发现

当前订阅模块存在数据库脚本漂移：

- ORM 已有 `user_subscription`
- 服务层也已依赖 `user_subscription`
- 但 `sql/init.sql` 与 `backend/sql/init.sql` 没有完整建表

这部分必须优先统一，否则后续开发和部署会继续出问题。

## 结论

方案可以进入实施，但建议按下面顺序执行：

1. 先修订 plan，补齐并发与生效规则、图片积分边界、Token 计量口径
2. 先做数据库结构统一与迁移脚本
3. 再做后端 entitlement / quota 服务
4. 最后接前端模板管理与展示
