# 图片编辑渠道接入实施记录（2026-04-23）

## 任务概述
- 基于已接入的 `gpt-image-2` 图片渠道，为系统补充图片编辑能力。
- 新增代理接口：
  - `POST /v1/image/edit`
  - `POST /v1/images/edits`
- 扩展 `user/chat`、`admin/chat` 的图片模型交互，支持上传图片后编辑。
- 扩展 `user/quickstart` 页面，补充图片编辑接口示例与协议说明。
- 图片编辑继续按图片积分计费，当前 `gpt-image-2` 为 `0.5` 积分/次，`n` 固定为 `1`。

## 文件变更清单
- `backend/app/api/proxy/image_proxy.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/model_service.py`
- `backend/app/api/user/models.py`
- `backend/app/api/admin/model.py`
- `backend/app/test/test_openai_image_channel.py`
- `frontend/src/views/common/AiChat.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/views/user/QuickStart.vue`

## 核心实现说明
### 1. 后端图片编辑代理
- 在图片代理路由中新增 `POST /v1/image/edit` 和 `POST /v1/images/edits`。
- 新接口读取 multipart/form-data，请求中解析：
  - `model`
  - `prompt`
  - `image`
  - `response_format`
  - `image_size` / `imageSize` / `size`
  - `aspect_ratio`
  - `n`
- 上传文件在路由层读取为内存字节，之后统一交由 `ProxyService.handle_image_edit_request(...)` 处理。

### 2. 渠道调用与计费
- `ProxyService` 新增 OpenAI 兼容图片编辑上游 URL 解析与调用逻辑，转发到上游 `/v1/images/edits`。
- 对编辑请求做了以下限制：
  - 必须传 `model`
  - 必须传 `prompt`
  - 必须上传 `image`
  - `response_format` 仅允许 `b64_json`
  - `n` 固定为 `1`
  - 仅支持具备编辑能力的图片模型，目前为 `gpt-image-2`
- 保留现有 `image_size` / `aspect_ratio` 兼容逻辑，继续通过 prompt 增强方式适配 `gpt-image-2`。
- 成功返回后，按 `image_credit` 记账，并将请求日志类型区分为：
  - `image_generation`
  - `image_edit`

### 3. 聊天页图片编辑
- 在共享页面 `frontend/src/views/common/AiChat.vue` 中，图片模型新增“生成 / 编辑”模式切换。
- 编辑模式下支持：
  - 本地上传图片
  - 原图预览
  - 清空当前上传
  - 发送编辑请求到 `/v1/image/edit`
  - 5 分钟超时控制
- 结果消息卡片支持同时显示：
  - 用户上传原图预览
  - 编辑后的结果图
  - 模型名、尺寸、比例、积分消耗
- 调用方式面板会根据当前模式切换为：
  - 生图 JSON 示例
  - 编辑图片 multipart 示例

### 4. QuickStart 页面
- 将“生图接口”扩展为“图片接口”。
- 增补 `POST /v1/image/edit` 的调用示例、编辑参数说明与响应示例。
- 文档中补充说明 `gpt-image-2` 同时支持文生图与图片编辑，统一按 `0.5` 图片积分/次计费。

## 测试验证
### 后端单测
在 `backend/` 目录执行：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest app.test.test_openai_image_channel app.test.test_image_billing
```

结果：
- 14 个测试全部通过
- Redis 在当前环境不可连通，测试自动降级为无缓存模式，不影响本次功能验证

### 前端构建
在 `frontend/` 目录执行：

```bash
npm run build
```

结果：
- 构建成功
- 仅存在仓库原有 ESLint / 打包体积 warning，无新增构建错误

## 备注
- 本次未新增数据库表结构或 SQL 迁移，复用既有 `gpt-image-2` 模型、渠道与图片积分计费配置。
- 图片原图预览与结果图预览均为前端运行时缓存，刷新页面后不会持久保留。
