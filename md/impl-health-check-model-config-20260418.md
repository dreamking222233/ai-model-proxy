## 任务概述

为管理端 `admin/health` 页面增加“渠道级健康检查测试模型”编辑能力，并让后端健康检查优先使用该配置；未配置时继续沿用现有的渠道映射自动选择逻辑。

## 文件变更清单

- `backend/app/models/channel.py`
- `backend/app/schemas/channel.py`
- `backend/app/services/channel_service.py`
- `backend/app/services/health_service.py`
- `backend/app/api/admin/channel.py`
- `backend/app/api/admin/health.py`
- `frontend/src/api/channel.js`
- `frontend/src/api/system.js`
- `frontend/src/views/admin/HealthMonitor.vue`
- `backend/sql/init.sql`
- `sql/init.sql`
- `sql/upgrade_channel_health_check_model_20260418.sql`

## 核心代码说明

### 1. 渠道持久化配置

在 `channel` 表新增 `health_check_model` 字段，用于保存每个渠道在健康检查时优先请求的具体模型型号。

### 2. 健康检查模型选择策略

健康检查时优先级如下：

1. 单次检查接口传入的 `model_name`
2. 渠道已保存的 `health_check_model`
3. 现有渠道映射中自动挑选的稳定模型
4. 兜底默认模型 `gpt-3.5-turbo`

### 3. 管理端页面能力

`HealthMonitor.vue` 新增“测试模型”列，支持：

- 展示当前已保存模型
- 基于渠道映射提供模型候选
- 手动输入自定义模型名
- 单独保存某个渠道的健康检查模型
- 使用当前输入值直接触发单渠道健康检查

## 测试验证

### 代码验证

- `python -m py_compile backend/app/models/channel.py backend/app/schemas/channel.py backend/app/services/channel_service.py backend/app/services/health_service.py backend/app/api/admin/channel.py backend/app/api/admin/health.py`
- `cd frontend && npm run build`

前端构建通过，仅保留项目原有 ESLint/产物体积 warning，无新增 error。

### 数据库验证

已执行本地数据库迁移：

- 数据库：`modelinvoke`
- 脚本：`sql/upgrade_channel_health_check_model_20260418.sql`

并通过 `DESC channel;` 确认字段 `health_check_model` 已成功创建。
