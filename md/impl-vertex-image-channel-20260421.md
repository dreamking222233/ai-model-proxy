## 任务概述

本次实现为当前系统新增 Google Vertex 图片渠道，并保持用户侧图片接口与参数协议不变：

- `/v1/images/generations`
- `/v1/image/created`

用户仍继续使用：

- `model`
- `prompt`
- `response_format`
- `image_size / imageSize / size`
- `aspect_ratio`

系统内部则在 Google 官方图片渠道与 Vertex 图片渠道之间按渠道配置做无感切换。

## 文件变更清单

### 后端

- [backend/app/models/channel.py](/Volumes/project/modelInvocationSystem/backend/app/models/channel.py)
- [backend/app/schemas/channel.py](/Volumes/project/modelInvocationSystem/backend/app/schemas/channel.py)
- [backend/app/services/channel_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/channel_service.py)
- [backend/app/services/google_vertex_image_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/google_vertex_image_service.py)
- [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py)
- [backend/app/services/health_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py)
- [backend/app/test/test_vertex_image_channel.py](/Volumes/project/modelInvocationSystem/backend/app/test/test_vertex_image_channel.py)
- [backend/requirements.txt](/Volumes/project/modelInvocationSystem/backend/requirements.txt)

### SQL

- [backend/sql/init.sql](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)
- [backend/sql/upgrade_vertex_image_channel_20260421.sql](/Volumes/project/modelInvocationSystem/backend/sql/upgrade_vertex_image_channel_20260421.sql)
- [sql/init.sql](/Volumes/project/modelInvocationSystem/sql/init.sql)

### 前端

- [frontend/src/views/admin/ChannelManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/ChannelManage.vue)

### 方案文档

- [md/plan-vertex-image-channel-20260421.md](/Volumes/project/modelInvocationSystem/md/plan-vertex-image-channel-20260421.md)
- [md/plan-review-vertex-image-channel-20260421.md](/Volumes/project/modelInvocationSystem/md/plan-review-vertex-image-channel-20260421.md)

## 核心实现说明

### 1. 为渠道增加 Google 子类型

`channel` 新增 `provider_variant`，用于显式区分：

- `default`
- `google-official`
- `google-vertex-image`

这样系统可以继续保留 `protocol_type=google` 的统一语义，同时在内部区分：

- Google 官方图片接口
- Google Vertex 图片接口

管理端 `/admin/channels` 也新增了该字段的展示与编辑能力。

### 2. 图片请求链路改为按渠道子类型分发

`ProxyService` 中原先单一的 Google 图片调用逻辑被拆成：

- Google 官方链路
  - 继续走当前 HTTP `generateContent`
- Vertex 链路
  - 通过 `google-genai` SDK 调用

用户接口不变，但内部会根据渠道的 `provider_variant` 自动分发。

### 3. 新增 Vertex 图片服务封装

新增 `GoogleVertexImageService`，负责：

- 懒加载 `google-genai`
- 解析 Vertex 渠道中的候选模型列表
- 区分 Gemini 图片模型与 Imagen 模型
- 封装 Vertex SDK 调用
- 统一解析返回结果为当前系统的 `b64_json + mime_type`

由于当前主链路是异步 FastAPI，而 `google-genai` 以同步 SDK 为主，因此实际调用通过：

- `asyncio.to_thread(...)`

接入，避免重构现有异步代理结构。

### 4. 支持 Vertex 渠道内的候选模型回退

现有 `model_channel_mapping` 结构不适合让同一统一模型在同一渠道下挂多条实际模型。

因此本次将 `gemini-2.5-flash-image` 在 Vertex 下的承接方式实现为单条 mapping 的候选模型列表：

```text
imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002
```

运行时会按顺序尝试，某个候选模型成功即返回。

这使得系统可以：

- 对用户继续暴露 `gemini-2.5-flash-image`
- 在 Vertex 渠道内部改由 Imagen 3 承接
- 不改现有统一模型结构

### 5. 保留当前图片计费与分辨率协议

本次没有改动当前用户侧生图参数协议。

仍继续复用已有逻辑：

- `image_size`
- `imageSize`
- `size`
- `aspect_ratio`

也继续复用当前：

- Google 图片模型分辨率白名单
- 分辨率计费规则
- 成功后扣费、失败不扣费
- 请求日志与积分流水中的 `image_size`

对于 Vertex 链路：

- Gemini 图片模型会尽量透传图片配置
- Imagen 模型会按 SDK 可接受的配置构建请求
- 若 SDK 版本不支持 `imageSize` 字段，会回退到无该字段的配置以优先保证可生成图片

### 6. 健康检查支持 Vertex 渠道

`HealthService` 现在会根据 `provider_variant` 区分：

- `google-official`
  - 保持当前 HTTP 探测
- `google-vertex-image`
  - 改为 Vertex SDK 探测

Vertex 渠道默认仍建议用轻量文本模型做健康检查，例如：

- `gemini-2.5-flash`

避免使用图片模型做频繁探测。

### 7. SQL 初始化与升级支持 Vertex 渠道

本次新增：

- `backend/sql/upgrade_vertex_image_channel_20260421.sql`

用于：

1. 给 `channel` 表增加 `provider_variant`
2. 回填历史 Google 渠道为 `google-official`
3. 可选创建 Vertex 图片渠道
4. 可选为 3 个统一图片模型写入 Vertex 推荐映射

`init.sql` 也同步补充了：

- `provider_variant` 字段
- Google 官方渠道 bootstrap
- Vertex 渠道 bootstrap

## 测试验证

已执行：

```bash
python -m py_compile backend/app/models/channel.py backend/app/schemas/channel.py backend/app/services/channel_service.py backend/app/services/google_vertex_image_service.py backend/app/services/proxy_service.py backend/app/services/health_service.py backend/app/test/test_vertex_image_channel.py
```

```bash
cd backend
python -m unittest app.test.test_image_billing app.test.test_google_image_resolution_rules app.test.test_vertex_image_channel
```

```bash
cd frontend
npm run build
```

结果：

- 后端语法编译通过
- 后端相关单测通过
- 前端构建通过
- 前端仍存在仓库原有 ESLint warning 与打包体积 warning，本次未额外处理

## 当前实现边界

1. Vertex 依赖需要部署环境安装 `google-genai`
2. Vertex 图片调用基于当前文档与本地验证脚本接入，但本次未在当前沙箱环境做真实联网联调
3. Vertex SDK 对 `imageSize` 的字段兼容性存在版本差异，本次实现采用“优先尝试透传，失败则降级为可生成配置”的策略

## 最终效果

改造完成后，系统可以同时管理：

- Google 官方图片渠道
- Google Vertex 图片渠道

管理员可在 `/admin/channels` 控制启用状态，用户侧则继续无感使用原有生图 API 和统一模型名。
