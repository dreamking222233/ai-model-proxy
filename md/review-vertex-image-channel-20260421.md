## Review 结论

本轮实现已满足核心需求，未发现阻断上线的结构性问题。

## 已确认符合需求

1. 用户侧图片接口与调用参数保持不变。
2. 系统已能在 Google 官方图片渠道与 Vertex 图片渠道之间按渠道配置切换。
3. 管理端 `/admin/channels` 已支持区分并管理：
   - `google-official`
   - `google-vertex-image`
4. `gemini-2.5-flash-image` 在 Vertex 渠道下已通过候选模型列表承接为 Imagen 3。
5. 当前图片积分、分辨率规则、失败不扣费策略保持不变。

## 主要残余风险

1. 部署环境需要安装 `google-genai`，否则 Vertex 渠道会返回依赖缺失错误。
2. 当前沙箱环境未进行真实 Vertex 联网联调，仍建议上线前用真实渠道做一次端到端验证。
3. Vertex SDK 对 `imageSize` 的支持存在版本差异，本次实现已做兼容降级，但建议在真实环境重点验证：
   - `1K`
   - `2K`
   - `4K`

## 建议的发布前检查

1. 执行 `backend/sql/upgrade_vertex_image_channel_20260421.sql`。
2. 在 `/admin/channels` 新建或启用 Vertex 渠道，并配置：
   - `protocol_type=google`
   - `provider_variant=google-vertex-image`
   - `auth_header_type=x-goog-api-key`
3. 为三款统一模型确认 Vertex 映射：
   - `gemini-2.5-flash-image` -> `imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002`
   - `gemini-3.1-flash-image-preview` -> `gemini-3.1-flash-image-preview`
   - `gemini-3-pro-image-preview` -> `gemini-3-pro-image-preview`
4. 用用户侧 QuickStart 生图示例分别验证 Google 官方渠道和 Vertex 渠道。
