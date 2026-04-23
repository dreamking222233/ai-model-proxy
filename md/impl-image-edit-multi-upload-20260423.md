# 图片编辑多图上传与 QuickStart 文档拆分实施记录（2026-04-23）

## 任务概述
- 将本地图片编辑接口升级为支持多图上传。
- 保持现有接口路径不变：
  - `POST /v1/image/edit`
  - `POST /v1/images/edits`
- 更新 `user/quickstart` 页面，将“图片生成”和“图片编辑”拆分为两个独立接口说明块。
- 在文档中分别补充请求参数、返回字段、响应示例、Python 示例和 cURL 示例。

## 文件变更清单
- `backend/app/api/proxy/image_proxy.py`
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `frontend/src/views/user/QuickStart.vue`
- `md/plan-image-edit-multi-upload-20260423.md`

## 核心实现说明

### 1. 后端多图编辑表单解析
- 路由层将 `form.get("image")` 改为 `form.getlist("image")`。
- 解析所有上传图片，统一写入：
  - `images`: 多图列表
  - `image`: 首张图片，保留旧字段兼容性
- 若未上传任何图片，或任一图片为空文件，直接返回 `INVALID_IMAGE_FILE`。

### 2. 服务层多图透传上游
- 新增 `ProxyService._extract_image_edit_inputs()`，统一兼容：
  - 新结构 `images`
  - 旧结构 `image`
- OpenAI 兼容图片编辑请求改为 multipart 列表格式，重复传递多个 `image` 字段给上游 `/v1/images/edits`。
- 保持既有约束不变：
  - `n=1`
  - `response_format=b64_json`
  - 图片超时 5 分钟
  - `image_size` / `aspect_ratio` 通过 prompt 增强适配

### 3. QuickStart 接口文档重构
- 将原“图片接口”统一说明拆为两个独立说明块：
  - 图片生成接口
  - 图片编辑接口
- 生图部分明确：
  - `/v1/images/generations`
  - `/v1/image/created`
- 编辑部分明确：
  - `/v1/image/edit`
  - `/v1/images/edits`
- 编辑接口文档补充“支持重复上传多个 `image` 字段”的说明。
- 为两类接口分别补充：
  - 请求参数表
  - 返回字段表
  - 响应示例
  - Python 代码示例
  - cURL 代码示例

## 测试验证
- 后端测试：
  - `PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m pytest backend/app/test/test_openai_image_channel.py`
  - 结果：`11 passed`
- 前端构建：
  - `npm run build`
  - 结果：构建成功
- 构建过程中仍存在项目原有 ESLint warning 与打包体积 warning，本次改动未新增错误。

## 结果说明
- 当前系统的 `v1/image/edit` 与 `v1/images/edits` 已支持多张图片上传编辑。
- `user/quickstart` 的 API 协议深度集成区域已将生图和编辑图片拆分说明，且编辑文档已明确多图上传方式。
