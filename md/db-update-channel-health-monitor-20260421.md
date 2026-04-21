## 目的

本次数据库更新用于支持：

- 渠道级“是否参与健康监控”开关
- 让某些渠道可继续承载请求，但不进入健康检查系统

## 推荐执行文件

正式环境推荐执行：

- [`backend/sql/upgrade_channel_health_monitor_20260421.sql`](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_channel_health_monitor_20260421.sql)

全量结构同步见：

- [`backend/sql/init.sql`](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [`sql/init.sql`](/Volumes/project/modelInvocationSystem/sql/init.sql)

## 本次变更内容

### 扩展 `channel`

新增字段：

- `health_check_enabled`

含义：

- `1`：参与健康监控
- `0`：不参与健康监控

默认值：

- `1`

## 执行方式

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p modelinvoke < backend/sql/upgrade_channel_health_monitor_20260421.sql
```

## 执行后验证

```sql
DESC channel;
```

确认存在：

- `health_check_enabled`

检查渠道配置：

```sql
SELECT id, name, protocol_type, enabled, health_check_enabled, health_check_model
FROM channel
ORDER BY id;
```

## 使用建议

对于以下类型渠道，建议关闭健康监控：

- Google 生图渠道
- 高成本图片渠道
- 不希望被定时探测的专用渠道

示例：

```sql
UPDATE channel
SET health_check_enabled = 0
WHERE protocol_type = 'google';
```

或更精确：

```sql
UPDATE channel
SET health_check_enabled = 0
WHERE provider_variant IN ('google-official', 'google-vertex-image');
```
