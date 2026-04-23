# 图片编辑渠道接入方案（2026-04-23）

## 用户原始需求
- 基于当前已接入的 `gpt-image-2` 生图渠道，新增图片编辑能力。
- 在系统内新增编辑图片接口，例如 `POST /v1/image/edit`，支持上传图片并传入提示词进行编辑。
- `n` 固定为 `1`。
- 图片编辑按 `0.5` 图片积分/次计费。
- 在 `user/quickstart` 页面 API 协议深度集成区域补充编辑图片接口调用方法。
- 在 `user/chat` 和 `admin/chat` 页面支持上传图片后调用图片编辑，并可查看对应调用代码。
- 如有必要，允许系统自行补充必要的兼容处理。

## 技术方案设计
1. 后端接口层
- 在现有图片代理路由中新增 `POST /v1/image/edit`。
- 同时补充兼容路由 `POST /v1/images/edits`，便于 OpenAI 兼容客户端直接调用。
- 路由层读取 multipart/form-data，请求字段至少包含：`model`、`prompt`、`image`，可兼容 `n`、`response_format`、`image_size`、`aspect_ratio`。

2. 服务层复用与扩展
- 在 `ProxyService` 中把当前仅支持文生图的逻辑扩展为两类图片请求：
  - image generation
  - image edit
- 对 `gpt-image-2` 的编辑请求统一走 OpenAI 兼容上游 `/v1/images/edits`。
- 继续固定上游模型名为渠道映射后的实际模型；当前该渠道统一为 `gpt-image-2`。
- 保持 `n=1` 校验，编辑接口同样不支持 stream，仅支持 `b64_json` 返回。
- 对当前系统的 `image_size` / `aspect_ratio` 兼容能力继续保留，通过 prompt 拼接方式传递给上游。
- 编辑请求的计费沿用图片积分，成功后扣减 0.5 积分，并写入请求日志；日志请求类型区分为 `image_edit`。

3. 前端聊天页
- 在共享页面 `frontend/src/views/common/AiChat.vue` 中为图片模型新增模式切换：生成 / 编辑。
- 编辑模式增加本地图片上传、预览、清除能力；无图时禁止发送编辑请求。
- 编辑模式调用 `POST /v1/image/edit`，使用 `FormData` 提交；仍沿用当前 5 分钟超时。
- 结果区分“生成结果 / 编辑结果”，消息卡片展示原图预览、输出图片、积分消耗、尺寸比例等信息。
- 调用指南面板根据当前模式输出 JSON 生图示例或 multipart 图片编辑示例（Python/cURL/Node）。

4. QuickStart 页面
- 在“生图接口”区域下补充“编辑图片接口”说明。
- 展示 `POST /v1/image/edit` 的 multipart 调用示例、参数说明与返回示例。

5. 测试与验证
- 增加/更新后端单测，覆盖：
  - OpenAI 图片编辑 URL 解析
  - OpenAI 图片编辑请求路由
  - `n=1` / `response_format=b64_json` 校验
- 运行后端相关测试与前端构建，确保共享聊天页正常打包。

## 涉及文件清单
- `backend/app/api/proxy/image_proxy.py`
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `backend/app/test/test_image_billing.py`
- `frontend/src/views/common/AiChat.vue`
- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/utils/chatStorage.js`
- `frontend/src/views/user/QuickStart.vue`
- `md/impl-image-edit-channel-20260423.md`
- `md/review-image-edit-channel-20260423.md`

## 实施步骤概要
1. 梳理现有图片代理、生图计费与聊天页生图实现。
2. 为图片代理新增编辑接口与 multipart 请求解析。
3. 扩展 `ProxyService` 支持图片编辑上游调用、日志与积分扣减。
4. 补充相关后端测试。
5. 扩展 QuickStart 页面编辑图片接口说明与示例。
6. 扩展共享聊天页上传编辑能力和调用代码示例。
7. 运行测试 / 构建并整理 impl、review 文档。
