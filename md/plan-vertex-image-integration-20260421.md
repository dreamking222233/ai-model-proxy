## 用户原始需求

用户希望梳理当前 Vertex AI 在图片生成方向支持哪些模型，明确当前账号实际可用的模型范围，并将接入方式、调用示例、注意事项整理成详细 Markdown 文档，供项目后续正式接入 Vertex 使用。

## 技术方案设计

本次任务以“官方文档 + 官方 notebook + 当前账号实测”三层结论为准：

- 第一层：阅读 Vertex AI 图片总览、Gemini 图片生成、模型页等官方文档，整理当前官方支持的生图模型。
- 第二层：阅读 GoogleCloudPlatform 官方 notebook，交叉确认 Gemini 图片模型 ID 与推荐调用方式。
- 第三层：使用当前 API key 通过 `google-genai` SDK 对目标模型做最小化真实调用，区分“官方支持”与“当前账号可用”。

输出文档需要覆盖：

1. Vertex 当前支持的图片生成模型列表
2. 当前账号实测可用 / 不可用模型
3. API key 接入方式与推荐 SDK
4. Gemini 图片模型与 Imagen 模型的调用差异
5. 项目接入步骤、示例代码、常见问题与排查建议

## 涉及文件清单

- `md/plan-vertex-image-integration-20260421.md`
- `docs/vertex-image-integration.md`
- `md/impl-vertex-image-integration-20260421.md`

## 实施步骤概要

1. 整理 Vertex 官方图片模型文档与官方 notebook。
2. 汇总当前官方支持的 Gemini / Imagen 图片模型。
3. 使用当前 Vertex API key 对核心模型执行真实调用验证。
4. 编写 `docs/vertex-image-integration.md`，输出接入方案与模型支持矩阵。
5. 编写 `impl` 文档，记录验证结果与交付内容。
