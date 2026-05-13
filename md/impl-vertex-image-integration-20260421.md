## 任务概述

为当前项目整理 Vertex AI 图片生成接入文档，明确：

- Vertex 当前支持的主线图片模型
- 当前账号实测可用模型
- API key 场景下的推荐调用方式
- 项目接入建议与示例代码

## 文件变更清单

- `md/plan-vertex-image-integration-20260421.md`
- `docs/vertex-image-integration.md`

## 核心内容说明

- 基于 Vertex 官方图片文档、Gemini / Imagen 模型页、GoogleCloudPlatform 官方 notebook，整理了当前主线图片模型。
- 将“官方支持”与“当前账号实测可用”分开记录，避免把账号权限问题误判为模型已下线。
- 记录了当前 API key 场景下推荐使用 `google-genai` SDK，而不是以 `vertexai.preview.vision_models.ImageGenerationModel` 作为主方案。
- 补充了“当前系统已有 3 个统一模型名”在接入 Vertex 渠道后的映射方案：
  - `gemini-3.1-flash-image-preview` -> `gemini-3.1-flash-image-preview`
  - `gemini-3-pro-image-preview` -> `gemini-3-pro-image-preview`
  - `gemini-2.5-flash-image` -> `imagen-3.0-fast-generate-001` / `imagen-3.0-generate-001` / `imagen-3.0-generate-002`
- 明确记录了 `gemini-2.5-flash-image` 在 Vertex 渠道中应视为“兼容统一模型名”，由 3 个 `Imagen 3` 模型承接，以保持 `1 积分/次` 规则不变。
- 给出了：
  - Imagen 调用示例
  - Gemini 图片模型调用示例
  - 当前系统统一模型到 Vertex 实际模型的映射表
  - 项目级模型白名单建议
  - 常见报错与排查说明

## 测试验证

本次通过当前 Vertex API key 对以下模型进行了真实调用验证：

### Gemini 图片模型

- `gemini-3-pro-image-preview`：成功
- `gemini-3.1-flash-image-preview`：成功
- `gemini-2.5-flash-image`：失败，返回 `404 NOT_FOUND`

### Imagen 模型

- `imagen-3.0-generate-001`：成功
- `imagen-3.0-fast-generate-001`：成功
- `imagen-3.0-generate-002`：成功
- `imagen-4.0-fast-generate-001`：成功
- `imagen-4.0-generate-001`：成功
- `imagen-4.0-ultra-generate-001`：成功

### 非推荐 capability 版本

- `imagen-3.0-capability-001`：失败，返回 `400 INVALID_ARGUMENT`
- `imagen-3.0-capability-002`：失败，返回 `400 INVALID_ARGUMENT`

### 本地脚本

- 已通过 `backend/app/test/test_vertex_api.py` 成功生成 `imagen-4.0-generate-001` 图片
- 输出目录：`backend/app/test/output/`
