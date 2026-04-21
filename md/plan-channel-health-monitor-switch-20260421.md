## 用户原始需求

当前系统已有渠道健康度检测和管理端：

- `/admin/health`
- `/admin/channels`

需要扩展为：

- 在 `/admin/channels` 可配置某个渠道是否参与健康度监控
- 对于不需要健康检测的渠道，例如 Google 生图渠道，可关闭自动健康检测
- 关闭后，不应再参与定时健康检查，也不应在“全部检查”里被扫描
- 用户请求转发逻辑保持不变

## 当前项目现状

### 1. 健康检测只依赖 `channel.enabled`

当前 `HealthService.check_all_channels` 会查询：

- `Channel.enabled == 1`

然后对所有启用渠道执行健康检查。

这意味着：

- 只要渠道启用，就默认会被健康检查扫描
- 没有单独的“参与健康监控”开关

### 2. 图片专用渠道虽然有低频检查，但仍会进入健康系统

当前已有：

- 图片专用渠道低频检查

但这只是“少检查”，不是“不检查”。

对于某些 Google 生图渠道，用户希望：

- 完全不参与健康检测

### 3. 管理端没有对应配置项

当前 `/admin/channels` 可配置：

- 名称
- base_url
- api_key
- 协议
- Google 渠道类型
- auth header
- priority
- enabled
- description

但没有：

- `health_check_enabled`

## 技术方案设计

### 方案总览

新增渠道级字段：

- `health_check_enabled`

语义：

- `1`：参与健康监控
- `0`：不参与健康监控

并在以下层面打通：

1. 数据库 / ORM / schema
2. Channel CRUD
3. 定时健康检查
4. 手动“全部检查”
5. `/admin/channels` 管理页
6. `/admin/health` 展示页

### 为什么不用复用 `enabled`

`enabled` 的语义是：

- 是否允许该渠道参与实际请求转发

但用户需要的是：

- 渠道继续可用
- 只是不要被健康检查

所以必须拆成独立字段，而不是复用 `enabled`。

### 字段设计

建议新增：

- `channel.health_check_enabled`

类型：

- `TINYINT`

默认值：

- `1`

这样能保持现有渠道默认行为不变。

### 健康检测行为调整

#### 定时健康检查

`HealthService.check_all_channels` 调整为仅扫描：

- `enabled = 1`
- `health_check_enabled = 1`

#### 手动全部检查

继续复用 `check_all_channels` 的筛选逻辑，因此：

- 关闭健康监控的渠道，不参与“全部检查”

#### 单渠道检查

对 `/admin/health/check/{channel_id}`：

- 仍允许单独检查

原因：

- 管理员虽然关闭了自动监控，但仍可能临时想手动探测一次

### 管理端展示建议

#### `/admin/channels`

新增开关：

- `参与健康监控`

推荐交互：

- 默认为开启
- 关闭后，渠道仍可启用并参与请求转发

#### `/admin/health`

建议展示：

- 仅展示 `health_check_enabled = 1` 的渠道

这样健康页语义更清晰，避免出现“明明关闭了健康监控却还在健康页看到它”的混乱。

### SQL 方案

新增升级脚本：

- `backend/sql/upgrade_channel_health_monitor_20260421.sql`

内容包括：

1. 给 `channel` 增加 `health_check_enabled`
2. 历史数据默认回填为 `1`
3. `init.sql` 同步补字段

## 涉及文件

### 后端

- `backend/app/models/channel.py`
- `backend/app/schemas/channel.py`
- `backend/app/services/channel_service.py`
- `backend/app/services/health_service.py`

### SQL

- `backend/sql/init.sql`
- `sql/init.sql`
- `backend/sql/upgrade_channel_health_monitor_20260421.sql`

### 前端

- `frontend/src/views/admin/ChannelManage.vue`
- `frontend/src/views/admin/HealthMonitor.vue`

### 文档

- `md/plan-channel-health-monitor-switch-20260421.md`
- `md/impl-channel-health-monitor-switch-20260421.md`

## 实施步骤概要

1. 新增数据库字段和 ORM/schema 支持。
2. 打通 channel CRUD 读写 `health_check_enabled`。
3. 调整健康检查服务的筛选逻辑。
4. 更新 `/admin/channels` 配置项。
5. 更新 `/admin/health` 展示逻辑。
6. 补充测试与实现文档。
