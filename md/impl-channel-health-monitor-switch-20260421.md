## 任务概述

本次实现为渠道新增“是否参与健康监控”开关，满足：

- 在 `/admin/channels` 单独控制渠道是否参与健康检测
- 关闭后不参与定时健康检查
- 关闭后不参与 `/admin/health` 中的“全部检查”
- 渠道本身仍可继续用于实际请求转发

## 文件变更清单

### 后端

- [backend/app/models/channel.py](/Volumes/project/modelInvocationSystem/backend/app/models/channel.py)
- [backend/app/schemas/channel.py](/Volumes/project/modelInvocationSystem/backend/app/schemas/channel.py)
- [backend/app/services/channel_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/channel_service.py)
- [backend/app/services/health_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py)
- [backend/app/test/test_channel_health_monitor_switch.py](/Volumes/project/modelInvocationSystem/backend/app/test/test_channel_health_monitor_switch.py)

### SQL

- [backend/sql/init.sql](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [sql/init.sql](/Volumes/project/modelInvocationSystem/sql/init.sql)
- [backend/sql/upgrade_channel_health_monitor_20260421.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_channel_health_monitor_20260421.sql)

### 前端

- [frontend/src/views/admin/ChannelManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/ChannelManage.vue)

## 核心实现说明

### 1. 新增渠道字段 `health_check_enabled`

`channel` 新增：

- `health_check_enabled`

语义：

- `1`：参与健康监控
- `0`：不参与健康监控

默认值保持为 `1`，因此历史渠道默认行为不变。

### 2. 健康检查只扫描开启监控的渠道

`HealthService` 新增内部筛选：

- `Channel.enabled == 1`
- `Channel.health_check_enabled == 1`

并用于：

- `check_all_channels`
- `get_health_status`

这意味着：

- 定时健康检查不会扫描关闭监控的渠道
- `/admin/health` 只显示参与监控的渠道
- “全部检查”也只检查参与监控的渠道

### 3. 单渠道检查仍保留

`/admin/health/check/{channel_id}` 仍允许管理员手动单独检查某个渠道。

这样即使某个 Google 生图渠道关闭了自动健康监控，管理员仍然可以在需要时手动探测一次。

### 4. `/admin/channels` 可直接配置

渠道管理页新增：

- 列表列：`健康监控`
- 表单开关：`参与健康监控`

关闭后会明确提示：

- 不参与定时健康检查
- 不参与“全部检查”
- 但仍可用于请求转发

## SQL 变更详情

本次新增增量脚本：

- [backend/sql/upgrade_channel_health_monitor_20260421.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_channel_health_monitor_20260421.sql)

变更内容：

1. 给 `channel` 增加 `health_check_enabled`
2. 历史数据默认回填为 `1`

全量初始化文件同步补充：

- [backend/sql/init.sql](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [sql/init.sql](/Volumes/project/modelInvocationSystem/sql/init.sql)

## 测试验证

已执行：

```bash
python -m py_compile backend/app/models/channel.py backend/app/schemas/channel.py backend/app/services/channel_service.py backend/app/services/health_service.py backend/app/test/test_channel_health_monitor_switch.py
```

```bash
cd backend
python -m unittest app.test.test_channel_health_monitor_switch
```

## 最终效果

改造完成后，像 Google 生图渠道这类不适合做健康检测的渠道，可以在 `/admin/channels` 里关闭健康监控，而不影响其正常承载用户请求。
