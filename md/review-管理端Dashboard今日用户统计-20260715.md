# 管理端Dashboard今日用户统计 Review

## 第一轮审查结论

最终不通过，建议修改后复审。未发现严重级别问题，但存在 3 个中等级问题。

## 中等问题

### 1. Dashboard 今日指标结束边界不一致

- `today_new_users`、`today_active_users` 使用 `created_at <= now`。
- `today_requests`、`today_tokens`、`today_cost` 只有 `created_at >= today`。
- 详细统计统一使用 `created_at <= until`。

未来时间记录可能导致顶部指标与活跃用户、详细统计口径不一致。建议三个原有聚合统一增加 `created_at <= now`，并补未来请求和消费记录测试。

### 2. 移动端今日新增存在截断风险

移动端卡片固定高度为 136px，380px 以下进一步缩短为 128px；用户总数卡片新增两段描述后可能换行并被卡片的 `overflow: hidden` 截断。建议增加移动端卡片高度或使用 `min-height`，并检查常见窄屏宽度。

### 3. 新增用户查询缺少时间范围索引

新增统计按 `role + created_at` 查询，代理场景增加 `agent_id`，但 `sys_user.created_at` 没有相关复合索引。自动刷新会重复执行查询，用户量增长后可能出现扫描压力。建议增加：

- `(role, created_at)`
- `(agent_id, role, created_at)`

索引需同步升级 SQL、初始化 SQL 和 ORM 定义。

## 低等级问题

测试可继续补充：

- 起始时间与 `now` 精确边界。
- 未来请求、Token、消费排除。
- `agent_id` 隔离。
- 同一用户跨 2 小时桶分别计活跃。
- 按日模式有新增但无请求的日期补数。
- 真实 MySQL 执行计划与前端真实窄屏渲染。

## 已确认项

- 活跃用户按普通用户去重，失败请求计入。
- 无请求桶能够保留新增用户数。
- 当天 12 个两小时桶、7/30 天日期桶补零正确。
- 三项趋势已改为不同颜色柱状系列并使用独立轴。
- 桌面及移动端详细统计已增加活跃用户、新增用户。
- 后端测试、Python 编译、前端 lint/build、`git diff --check` 已通过。

## 第一轮通过条件

修复统计结束边界和移动端截断问题，通过索引或生产执行计划解决新增用户查询性能风险，并补充对应回归测试。

## 第二轮审查结论

通过，可以进入交付阶段。

### 第一轮问题关闭情况

1. 今日请求数、Token、金额、活跃用户、新增用户已统一采用 `[today, now]` 闭区间，未来数据回归测试通过。
2. 移动端卡片改为 `height: auto; min-height: 152px`，380px 以下不再缩短卡片，今日新增信息截断风险已关闭。
3. 已新增 `(role, created_at)`、`(agent_id, role, created_at)` 复合索引，ORM、正式初始化 SQL、后端初始化 SQL和升级 SQL保持一致。

### 第二轮验证

- 7 个后端测试全部通过。
- Python 编译、前端 lint、生产构建与 `git diff --check` 通过。
- 升级 SQL 使用 `information_schema` 检查索引名称与 `agent_id` 字段，可安全重复执行。
- 低等级保留项：未自动覆盖同名错误索引的人工漂移场景；后续可将真实 MySQL `EXPLAIN` 纳入持续集成。

## 最终结论

无严重或中等级问题，Review 通过。
