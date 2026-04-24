## 目的

本次数据库更新用于兼容老环境中的 `sys_user.subscription_type` 字段约束。

在本轮真实联调中发现：

- 旧环境里该字段可能仍是只支持 `balance / unlimited` 的枚举或受限列定义
- 当日限额套餐用户请求时，应用在刷新套餐缓存状态阶段可能触发：

```sql
Data truncated for column 'subscription_type'
```

虽然当前代码已经通过兼容逻辑避免继续依赖 `quota` 写入该字段，但正式环境仍建议把该字段升级为更宽松的 `VARCHAR(16)`，避免后续版本或历史缓存写入再次触发库级异常。

## 推荐执行文件

- [`sql/upgrade_sys_user_subscription_type_compat_20260425.sql`](/Volumes/project/modelInvocationSystem/sql/upgrade_sys_user_subscription_type_compat_20260425.sql)

后端目录同样保留一份：

- [`backend/sql/upgrade_sys_user_subscription_type_compat_20260425.sql`](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_sys_user_subscription_type_compat_20260425.sql)

## 变更内容

将：

- `sys_user.subscription_type`

统一调整为：

```sql
VARCHAR(16) NOT NULL DEFAULT 'balance'
```

字段注释同步更新为：

- `balance=按量计费, unlimited/quota=套餐缓存态`

## 执行方式

示例：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < sql/upgrade_sys_user_subscription_type_compat_20260425.sql
```

如果你的正式环境数据库名不是 `modelinvoke`，请替换为实际名称。

## 脚本特性

该脚本是可重复执行的安全脚本：

- 如果字段已经兼容，则不会重复修改
- 如果字段仍是旧的枚举或长度不足，则会自动升级

## 执行后验证

建议执行：

```sql
SHOW CREATE TABLE sys_user;
```

确认 `subscription_type` 已类似如下定义：

```sql
`subscription_type` varchar(16) NOT NULL DEFAULT 'balance'
```

## 与本轮代码的关系

本轮代码已经包含：

- 请求必记录
- 成功请求消费流水
- 套餐成功/失败/超额请求日志
- 老库 `subscription_type` 缓存写入兼容

这份 SQL 主要是为了让正式环境的表结构与当前代码语义完全对齐，减少后续版本在老库上再次踩到字段约束问题。
