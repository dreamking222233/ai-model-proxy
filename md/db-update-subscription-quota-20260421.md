## 目的

本次数据库更新用于支持：

- 套餐模板管理
- 用户套餐发放
- 每日额度周期刷新
- 文本请求按套餐额度结算
- 老无限套餐兼容

## 推荐执行文件

正式环境推荐执行这份“可重复执行”的安全脚本：

- [`sql/upgrade_subscription_quota_packages_safe_20260421.sql`](/Volumes/project/modelInvocationSystem/sql/upgrade_subscription_quota_packages_safe_20260421.sql)

后端目录也保留了同内容文件：

- [`backend/sql/upgrade_subscription_quota_packages_safe_20260421.sql`](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_subscription_quota_packages_safe_20260421.sql)

说明：

- 旧文件 [`sql/upgrade_subscription_quota_packages_20260421.sql`](/Volumes/project/modelInvocationSystem/sql/upgrade_subscription_quota_packages_20260421.sql) 是首次草稿
- 正式环境请优先执行 `*_safe_20260421.sql`
- `safe` 版本会先检查字段 / 索引 / 表是否已存在，再决定是否变更，适合线上存在部分历史改动的情况

## 本次变更内容

### 1. 扩展 `request_log`

新增字段：

- `raw_input_tokens`
- `raw_output_tokens`
- `raw_total_tokens`
- `subscription_cycle_id`
- `quota_metric`
- `quota_consumed_amount`
- `quota_limit_snapshot`
- `quota_used_after`
- `quota_cycle_date`

用途：

- 记录套餐额度结算明细
- 区分原始 token 和倍率后 token

### 2. 扩展 `consumption_record`

新增字段：

- `raw_input_tokens`
- `raw_output_tokens`
- `raw_total_tokens`
- `subscription_cycle_id`
- `quota_metric`
- `quota_consumed_amount`
- `quota_limit_snapshot`
- `quota_used_after`
- `quota_cycle_date`

用途：

- 在账本层表达“这次请求占用了哪个套餐周期，以及用了多少额度”

### 3. 新增 `subscription_plan`

用途：

- 存储套餐模板

首批模板已内置初始化：

- `daily-unlimited`
- `weekly-unlimited`
- `monthly-unlimited`
- `daily-10m-token`
- `weekly-10m-token`
- `monthly-10m-token`

### 4. 扩展 `user_subscription`

新增字段：

- `plan_id`
- `plan_code_snapshot`
- `plan_kind_snapshot`
- `duration_days_snapshot`
- `quota_metric`
- `quota_value`
- `reset_period`
- `reset_timezone`
- `activation_mode`
- `activated_at`

用途：

- 保存用户实际发放的套餐快照
- 兼容旧无限套餐与新模板套餐并存

### 5. 新增 `subscription_usage_cycle`

用途：

- 保存每日额度套餐在当天周期内的累计消耗
- 实现“次日自动刷新”

## 正式环境执行方式

示例命令：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < sql/upgrade_subscription_quota_packages_safe_20260421.sql
```

如果你的正式库不是 `modelinvoke`，请替换为实际数据库名。

## 执行后验证

建议执行以下 SQL 检查：

```sql
DESC request_log;
DESC consumption_record;
DESC user_subscription;
DESC subscription_plan;
DESC subscription_usage_cycle;
```

检查套餐模板是否已初始化：

```sql
SELECT plan_code, plan_name, plan_kind, duration_days, quota_metric, quota_value
FROM subscription_plan
ORDER BY sort_order;
```

预期至少能看到 6 条模板：

- `daily-unlimited`
- `weekly-unlimited`
- `monthly-unlimited`
- `daily-10m-token`
- `weekly-10m-token`
- `monthly-10m-token`

## 本地执行结果

本地 `modelinvoke` 数据库已经执行并验证通过。

已确认：

- `consumption_record` 缺失字段已补齐
- `user_subscription` 已扩展到新结构
- `subscription_plan` 已创建
- `subscription_usage_cycle` 已创建
- 默认 6 个套餐模板已写入

## 注意事项

### 1. 线上如果已经有旧版 `user_subscription`

安全脚本会在原表基础上补字段，不会直接删表重建。

### 2. 不要优先执行旧草稿升级脚本

线上请优先执行：

- `upgrade_subscription_quota_packages_safe_20260421.sql`

不要优先执行：

- `upgrade_subscription_quota_packages_20260421.sql`

### 3. 应用代码需与本次 SQL 同步发布

数据库更新后，需要同步发布以下代码变更，否则新字段不会被正确使用：

- 套餐模板接口
- 套餐发放逻辑
- 文本请求额度校验
- 管理端套餐页面
- 用户端套餐摘要展示
