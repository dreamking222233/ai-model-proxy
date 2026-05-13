## 用户原始需求

> 当前版本：v2

在当前 Google 官方生图渠道之外，新增一个 Google Vertex 图片渠道，并满足以下要求：

- 用户侧仍然通过现有两个接口调用：
  - `/v1/images/generations`
  - `/v1/image/created`
- 用户请求参数与返回协议保持不变，继续兼容 `image_size / imageSize / size / aspect_ratio`
- 管理端可在 `/admin/channels` 管理 Google 官方渠道和 Vertex 渠道，并通过启用/禁用控制实际可用渠道
- 对外统一模型名继续保持：
  - `gemini-2.5-flash-image`
  - `gemini-3.1-flash-image-preview`
  - `gemini-3-pro-image-preview`
- Vertex 渠道内部按既定映射关系转成实际可用的 Vertex 模型
- 继续支持 `1K / 2K / 4K` 等当前系统定义的分辨率参数与计费规则

## 当前项目现状

### 1. 当前图片主链路仅支持 Google 官方 generateContent

当前图片请求统一进入：

- `backend/app/api/proxy/image_proxy.py`
- `backend/app/services/proxy_service.py`

现有实现默认将 Google 图片请求发往：

- `{base_url}/v1beta/models/{model}:generateContent`

并按 Google 官方 Gemini 图片响应结构解析。

这意味着当前同一个 `google` 协议下，只支持：

- Google 官方 Gemini 图片模型
- `generateContent` 风格响应

尚未支持：

- Vertex 渠道
- Imagen 的 `generate_images` 风格调用
- 同一协议内根据渠道类型切换不同上游调用器

### 2. 现有模型和渠道映射能力基本够用，但缺少“Google 子类型”

当前系统已有：

- `unified_model`
- `model_channel_mapping`
- `channel`

并支持：

- 一个统一模型映射多个渠道
- 同一统一模型在不同渠道使用不同 `actual_model_name`
- 渠道按 `priority + health` 排序与故障切换

但当前 `channel` 只有：

- `protocol_type`
- `auth_header_type`

没有进一步区分：

- Google 官方 Generative Language
- Google Vertex AI Image

所以如果直接把 Vertex 渠道也塞成 `protocol_type=google`，后端仍然会错误地走 Google 官方 `generateContent` 逻辑。

### 3. Vertex 渠道有两条调用链

根据现有文档：

- `docs/vertex-image-integration.md`
- `md/impl-vertex-image-integration-20260421.md`

Vertex 图片模型需要分为：

1. Gemini 图片模型
   - 使用 `generate_content`
   - 可返回 `TEXT + IMAGE`
2. Imagen 模型
   - 使用 `generate_images`
   - 返回图片数组

因此 Vertex 渠道内不能再假设“所有图片模型都走同一 HTTP endpoint”。

### 4. 当前系统的三个统一模型与 Vertex 实际可用模型不完全一致

按当前文档结论，Vertex 渠道建议映射如下：

- `gemini-3.1-flash-image-preview` -> `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview` -> `gemini-3-pro-image-preview`
- `gemini-2.5-flash-image` -> `imagen-3.0-fast-generate-001`
- `gemini-2.5-flash-image` -> `imagen-3.0-generate-001`
- `gemini-2.5-flash-image` -> `imagen-3.0-generate-002`

所以 Vertex 渠道接入的核心不是新增统一模型，而是：

- 保持统一模型名不变
- 仅在渠道映射层改变实际调用模型

## 技术方案设计

### 方案总览

本次改造拆成 5 个层面：

1. 渠道抽象层
   - 为 `channel` 增加 Google 子类型，区分“google-official”和“google-vertex-image”
2. 图片请求分发层
   - 在统一图片入口下，根据渠道类型分发到：
     - Google 官方图片调用器
     - Vertex Gemini 图片调用器
     - Vertex Imagen 图片调用器
3. 渠道映射层
   - 继续使用 `model_channel_mapping.actual_model_name`
   - 对 Vertex 渠道承载系统已有 3 个统一模型
4. 管理端
   - `/admin/channels` 增加渠道子类型配置与展示
   - 让管理员可以分别启用 / 禁用 Google 官方与 Vertex 渠道
5. 数据与文档
   - 增加 SQL 升级脚本
   - 初始化 Vertex 渠道与推荐映射
   - 增加测试与实现记录

### 方案 1：为 channel 增加 `provider_variant` 字段（推荐）

建议在 `channel` 表新增：

- `provider_variant`

候选值：

- `default`
- `google-official`
- `google-vertex-image`

推荐理由：

- 不需要把 `protocol_type` 拆碎成过多枚举
- 可以保留当前 `protocol_type=google` 的高层语义
- 能在 Google 协议内部继续扩展多个子实现
- 前后端都容易理解，也适合后续健康检查和 UI 展示

### 方案 2：仅通过 `base_url` 或 `description` 猜测渠道类型（不推荐）

例如：

- `generativelanguage.googleapis.com` 视为官方
- `aiplatform.googleapis.com` 视为 Vertex

问题：

- 规则隐式，维护成本高
- 管理端无法明确表达渠道用途
- 后续若 base URL 变化会导致逻辑脆弱

结论：

- 不采用隐式识别
- 明确增加渠道子类型字段

### Vertex 接入方式

按照现有文档，当前 API key 场景推荐使用：

- `google-genai`
- `vertexai=True`

因此后端建议新增基于 SDK 的 Vertex 图片调用器，而不是用当前 Google 官方的纯 HTTP 拼接方式硬套 Vertex。

原因：

- 文档已明确当前 API key 场景下 `google-genai` 是主方案
- Gemini 图片与 Imagen 图片调用入口不同
- SDK 能统一处理 Vertex 的两条调用链
- 当前主链路为异步 FastAPI，而 `google-genai` 使用上以同步 SDK 为主，因此 Vertex 调用器需要通过 `asyncio.to_thread(...)` 接入

### 图片请求分发策略

建议将当前 `_non_stream_image_request` 拆成明确分支：

1. `google-official`
   - 保持当前 HTTP `generateContent` 逻辑
2. `google-vertex-image` + Gemini 图片模型
   - 使用 Vertex SDK `generate_content`
3. `google-vertex-image` + Imagen 模型
   - 使用 Vertex SDK `generate_images`

图片响应最终统一回写成当前 OpenAI 兼容格式：

```json
{
  "created": 1710000000,
  "model": "gemini-2.5-flash-image",
  "request_id": "uuid",
  "data": [
    {
      "b64_json": "...",
      "mime_type": "image/png"
    }
  ],
  "usage": {
    "billing_type": "image_credit",
    "image_credits_charged": 1,
    "model_multiplier": 1,
    "image_size": "1K"
  }
}
```

### Vertex 实际模型识别策略

在 Vertex 渠道中，以 `actual_model_name` 判断调用器：

- `actual_model_name` 以 `imagen-` 开头：
  - 走 Imagen 调用器
- 其他图片模型：
  - 走 Gemini 图片调用器

这是当前最小改造、最稳定的实现方式。

### Vertex 渠道内的候选模型回退策略

评审后确认，现有 `model_channel_mapping` 结构不适合让同一统一模型在同一渠道下保存多条 `actual_model_name`。

因此 `gemini-2.5-flash-image` 在 Vertex 渠道中的承接方案调整为：

- 仍然只有一条 mapping
- `actual_model_name` 支持保存一个有序候选列表

编码规则建议为：

```text
imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002
```

运行时策略：

1. 先按 `|` 解析候选模型列表
2. 逐个尝试调用
3. 某个候选模型成功即返回
4. 若全部失败，则将最后一次有效请求错误返回给上层

这样可以满足：

- 用户侧统一模型名不变
- 管理端仍只管理一个 Vertex 渠道
- 不需要重做 `model_channel_mapping` 结构

### 分辨率参数兼容策略

用户协议保持不变：

- `image_size`
- `imageSize`
- `size`
- `aspect_ratio`

内部处理保持现有规则：

- `size=1K/2K/4K` 时视为图片分辨率
- `size=1024x1024` 等旧值时映射为 `aspect_ratio`

然后按渠道类型分别透传：

- Google 官方：
  - `generationConfig.imageConfig.imageSize`
  - `generationConfig.imageConfig.aspectRatio`
- Vertex Gemini：
  - 优先透传 `response_modalities=["TEXT","IMAGE"]`
  - 若 SDK 支持尺寸 / 比例配置则附带配置
  - 若模型不支持某尺寸，则继续复用当前模型能力白名单 + 本地计费规则提前拦截
- Vertex Imagen：
  - `GenerateImagesConfig.aspectRatio`
  - 若 SDK 支持图片尺寸参数则透传；若当前 SDK / API key 模式下以 `aspectRatio` 为主，则保持本地计费生效并尽可能传递尺寸意图

说明：

- 本次以“兼容当前系统 1K/2K/4K 调用参数”为目标
- 若某个 Vertex 实际模型对 `imageSize` 的支持与 Google 官方不完全一致，以“系统统一协议不变 + 本地规则稳定 + 可生成图片”为优先

### 渠道健康检查策略

当前健康检查会对 `protocol_type=google` 默认发：

- `/v1beta/models/{model}:generateContent`

接入 Vertex 后需要区分：

- `google-official`
  - 保持现状
- `google-vertex-image`
  - 使用轻量 Gemini 文本模型作为健康检查模型
  - 通过 Vertex SDK 的 `generate_content` 做最小健康探测

不建议用 Imagen 模型做周期性健康检查，因为：

- 成本更高
- 延迟更高
- 与当前“图片专用渠道低频检查”的思路不一致

### 管理端改造

`/admin/channels` 需要新增：

- 渠道子类型字段
- 对 Google 渠道的推荐组合提示

推荐展示：

- 协议：`Google`
- 渠道类型：`Google Official Image` / `Google Vertex Image`

管理员创建 Vertex 渠道时仍配置：

- `name`
- `api_key`
- `protocol_type=google`
- `provider_variant=google-vertex-image`
- `health_check_model`
- `enabled`
- `priority`

补充说明：

- `base_url` 对 Vertex 渠道主要用于管理端展示与渠道识别，不再作为 Vertex SDK 的核心调用依据
- 实际调用以 `provider_variant + api_key + actual_model_name` 为主

### SQL 与初始化策略

新增升级脚本，完成：

1. `channel` 表新增 `provider_variant`
2. 为历史 Google 渠道回填：
   - 默认 `google-official`
3. 可选插入 Vertex 渠道模板
4. 为 3 个统一模型追加 Vertex 推荐映射

注意：

- 不强制覆盖用户现有渠道
- Vertex 模板渠道以“提供可选 bootstrap”为主
- 模型映射应具备幂等性
- `gemini-2.5-flash-image` 的 Vertex 映射使用单条候选列表格式，不新增多条同渠道映射

## 影响范围分析

### 后端

- `backend/app/models/channel.py`
- `backend/app/schemas/channel.py`
- `backend/app/services/channel_service.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `backend/app/api/admin/channel.py`
- `backend/app/test/*`
- `backend/requirements.txt`

### SQL

- `backend/sql/init.sql`
- 新增 `backend/sql/upgrade_vertex_image_channel_20260421.sql`

### 前端

- `frontend/src/views/admin/ChannelManage.vue`

### 文档

- `md/plan-vertex-image-channel-20260421.md`
- `md/impl-vertex-image-channel-20260421.md`

## 风险点

1. `google-genai` 依赖引入后，部署环境需要安装新依赖
2. Vertex Gemini 与 Imagen 响应结构不同，需要统一解析
3. 若 SDK 对某些 `image_size` 档位的参数支持弱于当前 Google 官方接口，需要做好本地兼容与错误提示
4. `gemini-2.5-flash-image` 在 Vertex 下是兼容模型名，不是真实模型名，内部日志与排障需要明确区分 `requested_model` 和 `actual_model`
5. 健康检查不能继续把所有 Google 渠道都当作 Google 官方 HTTP API
6. `actual_model_name` 候选列表格式需要与现有单模型字符串保持兼容

## To-Do 拆解

1. 为 `channel` 增加 `provider_variant` 字段并打通 ORM / schema / service / admin UI。
2. 为 Channel 管理页增加 Google 渠道子类型展示与编辑能力。
3. 在 `ProxyService` 中增加 Google 图片渠道子类型分发入口。
4. 保留现有 Google 官方 HTTP 图片调用器不变。
5. 新增 Vertex SDK 客户端构建逻辑，并通过 `asyncio.to_thread(...)` 接入异步主链路。
6. 新增 `actual_model_name` 候选模型列表解析逻辑。
7. 新增 Vertex Gemini 图片调用器与响应解析。
8. 新增 Vertex Imagen 图片调用器与响应解析。
9. 在 Vertex 渠道内对候选模型执行逐个回退。
10. 复用现有统一模型、分辨率与图片积分逻辑，不改用户协议。
11. 改造健康检查逻辑以支持 Vertex 渠道。
12. 为 init / upgrade SQL 增加 Vertex 渠道与推荐映射模板。
13. 增加后端单测，覆盖渠道分发、候选模型解析、响应解析等关键路径。
14. 编写实现文档并进行验证。
