# 图片编辑多图上传与 QuickStart 文档拆分方案（2026-04-23）

## 用户原始需求
- 把本地图片编辑接口改为支持多图上传。
- 同步更新 `user/quickstart` 页面对应文档。
- 在“API 协议深度集成”区域中，不要把生图和编辑图片统一成一个图片接口说明。
- 生图与编辑图片需要分别说明，包含：
  - 具体调用接口
  - 请求参数
  - 返回内容
  - 参考 Python 调用代码
- 列出详细 tasks 并开始构建。

## 技术方案设计

### 1. 后端图片编辑接口扩展
- 保持现有接口不变：
  - `POST /v1/image/edit`
  - `POST /v1/images/edits`
- 路由层从 `multipart/form-data` 中读取多个同名 `image` 字段，改为 `form.getlist("image")`。
- 解析结果统一写入 `request_data["images"]`，每个元素包含：
  - `filename`
  - `content_type`
  - `content`
- 为兼容现有调用链，同时保留首图到 `request_data["image"]`，避免已存在单图逻辑调用点立即失效。

### 2. 服务层多图透传
- 图片编辑校验逻辑从“单图必传”改为“至少一张图片必传”。
- OpenAI 兼容编辑请求从单个 `files` 字典改为 multipart 列表，重复传递多个 `image` 字段：
  - `("image", (...))`
  - `("image", (...))`
- 继续固定：
  - 上游模型 `gpt-image-2`
  - `n=1`
  - `response_format=b64_json`
  - 5 分钟超时
- 保持现有 `image_size` / `aspect_ratio` 兼容逻辑，通过 prompt 增强适配上游。
- 计费维持每次请求 `0.5` 图片积分，不因上传张数变化而增加；日志中的 `image_count` 记录返回图片数量，符合现有系统口径。

### 3. QuickStart 页面文档拆分
- 在 `API 协议深度集成` 的图片能力区域，拆分为两个独立说明块：
  - 图片生成接口
  - 图片编辑接口
- 每块单独展示：
  - 接口地址
  - 使用说明
  - 请求参数表
  - 返回字段表
  - 响应示例
  - Python 示例代码
  - cURL 示例
- 编辑图片说明明确支持多张 `image` 文件重复上传。

## 涉及文件清单
- `backend/app/api/proxy/image_proxy.py`
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `frontend/src/views/user/QuickStart.vue`
- `md/impl-image-edit-multi-upload-20260423.md`
- `md/review-image-edit-multi-upload-20260423.md`

## 详细 Tasks
1. 审查当前 `v1/image/edit` 路由和 `ProxyService` 图片编辑透传实现，确认单图限制点。
2. 新建本次任务方案文档，明确多图上传和 QuickStart 拆分结构。
3. 修改 `image_proxy.py`，支持从表单中读取多个 `image` 文件并构造成统一请求体。
4. 修改 `proxy_service.py`，将图片编辑请求校验与上游转发从单图升级为多图 multipart。
5. 补充或调整后端单测，验证多图编辑请求会被正确转发。
6. 修改 `frontend/src/views/user/QuickStart.vue`，把生图与编辑图片拆成两个独立说明块。
7. 为生图和编辑图片分别补充参数表、返回字段表、响应示例、Python 示例与 cURL 示例。
8. 运行后端测试与前端构建，确认改动可用。
9. 生成实施记录 `impl` 文档。
10. 执行自审并生成 `review` 文档，必要时继续修复。
