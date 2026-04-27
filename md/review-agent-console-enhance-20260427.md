# 代理端后台体验增强 Review

## 问题 1：高，套餐发放记录查不到新发放的套餐

`AgentAssetService.grant_user_subscription` 调用 `SubscriptionService.activate_plan_subscription(..., auto_commit=False)` 创建订阅，但 `SubscriptionService._build_subscription_record` 没有写入 `agent_id`。而代理发放记录接口按 `UserSubscription.agent_id == 当前代理ID` 查询。

结果：代理成功发放套餐后，`/api/agent/subscription/records` 可能返回空或漏数据，需求“代理端可以看到发放的套餐记录”未闭环。

建议：给 `activate_plan_subscription` / `_build_subscription_record` 增加可选 `agent_id` 参数，代理发放时传入当前代理 ID；同时补充测试。

## 问题 2：中，套餐记录状态筛选口径错误

前端提供 `active/expired/cancelled` 筛选，但后端序列化状态是运行时计算的，查询过滤却直接按数据库 `status` 字段过滤。这样 `expired` 记录通常查不到，`active` 也可能包含已经过期但字段仍为 `active` 的记录。

建议：按业务状态写 SQL 条件：

- `active`：active 状态且 `start_time <= now <= end_time`
- `expired`：非 cancelled 且 `end_time < now`
- `cancelled`：原始字段为 cancelled

## 问题 3：中低，请求趋势统计与“今日统计”时间口径不一致

仪表盘今日统计使用北京时间窗口，但趋势统计使用 `datetime.utcnow() - days` 和数据库日期分组。页面展示“近 7 天”时可能是滚动 7*24 小时，并且无请求日期不会补 0。

建议：复用统一的北京时间自然日窗口，返回固定 N 天数组，无数据日期补 0。

## 结论

`agent/dashboard` 和 `agent/users` 的主体能力基本符合需求；主要阻塞点在 `agent/subscription` 发放记录链路。修复后需要重新执行后端单测和前端构建。

