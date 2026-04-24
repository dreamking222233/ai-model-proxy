# Vertex 图片生成接入指南

本文档用于指导本项目接入 Google Cloud Vertex AI 的图片生成能力，覆盖：

- Vertex 当前主流生图模型
- 当前账号实测可用模型
- API key 接入方式
- Gemini 图片模型与 Imagen 模型的调用差异
- 项目接入建议与排查方法

本文结论基于以下信息整理：

- Vertex 官方文档
- GoogleCloudPlatform 官方 notebook
- 当前账号在 `2026-04-21` 的真实 API 调用验证

---

## 1. 结论摘要

### 1.1 当前官方主线生图模型

按当前 Vertex 官方文档与官方 notebook，可归入当前主线图片生成能力的模型主要包括：

#### Gemini 图片模型

- `gemini-2.5-flash-image`
- `gemini-3-pro-image-preview`
- `gemini-3.1-flash-image-preview`

#### Imagen 图片模型

- `imagen-3.0-generate-001`
- `imagen-3.0-fast-generate-001`
- `imagen-3.0-generate-002`
- `imagen-4.0-fast-generate-001`
- `imagen-4.0-generate-001`
- `imagen-4.0-ultra-generate-001`

### 1.2 当前账号实测结果

以下结果基于当前 Vertex API key 的真实调用：

| 模型 | 类型 | 当前账号结果 | 说明 |
|------|------|-------------|------|
| `gemini-2.5-flash-image` | Gemini 图片 | 不可用 | 返回 `404 NOT_FOUND`，表现为当前账号 / 项目无访问权限或当前绑定区域下不可用 |
| `gemini-3-pro-image-preview` | Gemini 图片 | 可用 | 已成功返回 `TEXT + IMAGE` |
| `gemini-3.1-flash-image-preview` | Gemini 图片 | 可用 | 已成功返回 `TEXT + IMAGE` |
| `imagen-3.0-generate-001` | Imagen | 可用 | 已成功返回图片 |
| `imagen-3.0-fast-generate-001` | Imagen | 可用 | 已成功返回图片 |
| `imagen-3.0-generate-002` | Imagen | 可用 | 已成功返回图片 |
| `imagen-4.0-fast-generate-001` | Imagen | 可用 | 已成功返回图片 |
| `imagen-4.0-generate-001` | Imagen | 可用 | 已成功返回图片 |
| `imagen-4.0-ultra-generate-001` | Imagen | 可用 | 已成功返回图片 |

补充说明：

- `imagen-3.0-capability-001`
- `imagen-3.0-capability-002`

这两个 capability 版本在 `generate_images` 场景下返回 `400 INVALID_ARGUMENT`，不应作为本项目的直接文生图主模型使用。

### 1.3 当前项目推荐模型

建议按用途拆分：

| 场景 | 推荐模型 |
|------|---------|
| 默认稳定文生图 | `imagen-4.0-generate-001` |
| 更快、更便宜 | `imagen-4.0-fast-generate-001` |
| 更高质量 | `imagen-4.0-ultra-generate-001` |
| 带文本理解的 Gemini 图片生成 | `gemini-3.1-flash-image-preview` |
| 更强图片理解 / 生成能力 | `gemini-3-pro-image-preview` |

当前不建议在项目里默认使用 `gemini-2.5-flash-image`，因为当前账号实测不可用。

---

## 2. 认证方式选择

### 2.1 当前账号实际可用的方式

当前你提供的是 Vertex API key，而不是 OAuth access token。

在这种前提下，推荐使用：

- `google-genai` SDK
- `vertexai=True`
- `api_key=...`

这是当前实测可用的接入方式。

### 2.2 不建议当前项目使用的方式

以下方式更适合服务账号 / ADC / Bearer token 场景：

- `vertexai.preview.vision_models.ImageGenerationModel`
- 标准 Vertex REST `:predict`
- `Authorization: Bearer <access-token>`

我们在本次验证中已经确认：

- `vertexai.preview.vision_models.ImageGenerationModel` 这条链路在当前 API key 场景下不可直接作为主方案
- 它更偏向 ADC / quota project 场景

所以，如果你的项目当前就是使用 API key 接入 Vertex，优先走 `google-genai`。

---

## 3. Gemini 与 Imagen 的调用差异

### 3.1 Gemini 图片模型

Gemini 图片模型走 `generate_content`：

- 输入是 `contents`
- 输出通常同时包含 `TEXT` 和 `IMAGE`
- 适合“理解 + 生成”一体化场景

典型模型：

- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`

### 3.2 Imagen 图片模型

Imagen 图片模型走 `generate_images`：

- 输入是 `prompt`
- 输出直接是图片数组
- 更适合稳定、标准化的图片生成服务

典型模型：

- `imagen-4.0-fast-generate-001`
- `imagen-4.0-generate-001`
- `imagen-4.0-ultra-generate-001`

### 3.3 项目侧的选择建议

如果你要做“用户上传提示词，直接出图”的标准接口：

- 首选 `Imagen`

如果你要做“多模态对话里同时产出文本与图片”：

- 使用 `Gemini 图片模型`

---

## 4. 推荐 SDK 与依赖

### 4.1 安装

推荐安装：

```bash
pip install google-genai
```

当前本地验证环境中也安装了：

```bash
pip install google-cloud-aiplatform
```

但对 API key 文生图主流程而言，核心是 `google-genai`。

### 4.2 Python 版本建议

当前验证环境使用的是 Python `3.9`，可以运行，但 Google SDK 已发出即将停止支持的 warning。

项目正式接入建议至少升级到：

- Python `3.10`

---

## 5. Imagen 模型调用示例

以下是当前项目已验证成功的调用方式。

```python
from google import genai
from google.genai import types

client = genai.Client(
    vertexai=True,
    api_key="YOUR_VERTEX_API_KEY",
)

response = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="生成一张未来感十足的城市夜景海报，霓虹灯、雨夜街道、电影感构图",
    config=types.GenerateImagesConfig(
        numberOfImages=1,
        aspectRatio="1:1",
        negativePrompt="",
        personGeneration=types.PersonGeneration.ALLOW_ALL,
        safetyFilterLevel=types.SafetyFilterLevel.BLOCK_MEDIUM_AND_ABOVE,
        addWatermark=True,
        outputMimeType="image/png",
    ),
)

generated_images = response.generated_images or []
image_bytes = generated_images[0].image.image_bytes

with open("output.png", "wb") as f:
    f.write(image_bytes)
```

适用模型：

- `imagen-3.0-generate-001`
- `imagen-3.0-fast-generate-001`
- `imagen-3.0-generate-002`
- `imagen-4.0-fast-generate-001`
- `imagen-4.0-generate-001`
- `imagen-4.0-ultra-generate-001`

---

## 6. Gemini 图片模型调用示例

Gemini 图片模型需要使用 `generate_content`，并显式声明返回模态：

```python
from google import genai
from google.genai import types

client = genai.Client(
    vertexai=True,
    api_key="YOUR_VERTEX_API_KEY",
)

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents="Generate a simple red apple image.",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"]
    ),
)

for candidate in response.candidates or []:
    content = candidate.content
    for part in content.parts or []:
        if part.text:
            print(part.text)
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            with open("gemini_image.png", "wb") as f:
                f.write(image_bytes)
```

适用模型：

- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`

当前不建议默认接入：

- `gemini-2.5-flash-image`

因为当前账号实测不可用。

---

## 7. 本项目接入建议

### 7.1 推荐的抽象方式

项目里建议把 Vertex 生图分成两条链路：

#### A. Imagen 链路

特点：

- 稳定
- 返回结构简单
- 适合做标准 `/images/generations` 风格接口

建议模型优先级：

1. `imagen-4.0-generate-001`
2. `imagen-4.0-fast-generate-001`
3. `imagen-4.0-ultra-generate-001`

#### B. Gemini 图片链路

特点：

- 可同时产出文本与图片
- 更适合聊天 / 多模态生成

建议模型优先级：

1. `gemini-3.1-flash-image-preview`
2. `gemini-3-pro-image-preview`

### 7.2 配置建议

建议在项目配置层至少保留以下字段：

```yaml
vertex:
  enabled: true
  auth_mode: api_key
  api_key: YOUR_VERTEX_API_KEY
  default_imagen_model: imagen-4.0-generate-001
  fast_imagen_model: imagen-4.0-fast-generate-001
  ultra_imagen_model: imagen-4.0-ultra-generate-001
  default_gemini_image_model: gemini-3.1-flash-image-preview
```

### 7.3 模型白名单建议

当前账号建议白名单：

```text
gemini-3.1-flash-image-preview
gemini-3-pro-image-preview
imagen-3.0-generate-001
imagen-3.0-fast-generate-001
imagen-3.0-generate-002
imagen-4.0-fast-generate-001
imagen-4.0-generate-001
imagen-4.0-ultra-generate-001
```

当前应排除：

```text
gemini-2.5-flash-image
imagen-3.0-capability-001
imagen-3.0-capability-002
```

### 7.4 当前系统三款模型的 Vertex 渠道映射方案

当前系统对外已经存在 3 个统一模型名：

- `gemini-2.5-flash-image`
- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`

如果要接入 Vertex 渠道，建议保留这 3 个统一模型名不变，不修改前端和用户侧可见的模型名，只在渠道映射层调整实际调用的 Vertex 模型。

推荐映射关系如下：

| 系统统一模型名 | 当前积分 | Vertex 渠道实际模型 | 推荐优先级 | 说明 |
|------|------:|------|------:|------|
| `gemini-3.1-flash-image-preview` | 2 | `gemini-3.1-flash-image-preview` | 1 | 可直接一对一映射，当前账号已实测可用 |
| `gemini-3-pro-image-preview` | 3 | `gemini-3-pro-image-preview` | 1 | 可直接一对一映射，当前账号已实测可用 |
| `gemini-2.5-flash-image` | 1 | `imagen-3.0-fast-generate-001` | 1 | 当前账号下 `gemini-2.5-flash-image` 不可用，可用同积分 Imagen 3 模型代替 |
| `gemini-2.5-flash-image` | 1 | `imagen-3.0-generate-001` | 2 | 作为第二候选 |
| `gemini-2.5-flash-image` | 1 | `imagen-3.0-generate-002` | 3 | 作为第三候选 |

这套方案的核心原则是：

- 对外模型名保持不变
- 对内按 Vertex 渠道实际可用模型做映射
- 保持原有积分规则不变
- 用当前账号实测可用的 Imagen 3 模型承接 `gemini-2.5-flash-image`

### 7.5 为什么 `gemini-2.5-flash-image` 要映射到 Imagen 3

当前账号在 Vertex 渠道下调用 `gemini-2.5-flash-image` 返回：

- `404 NOT_FOUND`

说明当前这把 API key 对该模型不可用。

但当前系统里：

- `gemini-2.5-flash-image` 计费是 `1 积分/次`

而以下三个 Imagen 模型同样适合按 `1 积分/次` 处理：

- `imagen-3.0-fast-generate-001`
- `imagen-3.0-generate-001`
- `imagen-3.0-generate-002`

因此最稳妥的兼容方案是：

- 系统保留 `gemini-2.5-flash-image` 这个统一模型名
- Vertex 渠道内把它映射到上述 3 个 Imagen 3 模型之一

这样可以达到：

- 不改用户侧现有模型选择
- 不改现有积分规则
- 避免因为 Vertex 渠道无法直接使用 `gemini-2.5-flash-image` 而导致该模型不可用

### 7.6 推荐的数据库映射落地方式

如果项目仍沿用当前的：

- `unified_model`
- `model_channel_mapping`

则建议这样落地。

#### 统一模型层

保留以下 3 条统一模型：

```text
gemini-2.5-flash-image
gemini-3.1-flash-image-preview
gemini-3-pro-image-preview
```

并继续保留原有积分：

```text
gemini-2.5-flash-image              1 积分/次
gemini-3.1-flash-image-preview      2 积分/次
gemini-3-pro-image-preview          3 积分/次
```

#### Vertex 渠道映射层

新增一个 Vertex 图片渠道后，建议映射成：

```text
unified_model: gemini-3.1-flash-image-preview
channel: Vertex AI Image
actual_model_name: gemini-3.1-flash-image-preview
priority: 1
```

```text
unified_model: gemini-3-pro-image-preview
channel: Vertex AI Image
actual_model_name: gemini-3-pro-image-preview
priority: 1
```

```text
unified_model: gemini-2.5-flash-image
channel: Vertex AI Image
actual_model_name: imagen-3.0-fast-generate-001
priority: 1
```

```text
unified_model: gemini-2.5-flash-image
channel: Vertex AI Image
actual_model_name: imagen-3.0-generate-001
priority: 2
```

```text
unified_model: gemini-2.5-flash-image
channel: Vertex AI Image
actual_model_name: imagen-3.0-generate-002
priority: 3
```

如果当前平台支持按渠道优先级或健康度做 failover，那么：

- 先尝试 `imagen-3.0-fast-generate-001`
- 再尝试 `imagen-3.0-generate-001`
- 再尝试 `imagen-3.0-generate-002`

### 7.7 对产品侧的影响

采用这套映射后，产品层面可以保持：

- 模型展示名不变
- 用户计费规则不变
- 老接口参数不变

唯一变化是：

- `gemini-2.5-flash-image` 在 Vertex 渠道下，实际已不再直连 Google 的 `gemini-2.5-flash-image`
- 而是由 3 个 `Imagen 3` 模型承接

因此建议在内部文档中明确标注：

- `gemini-2.5-flash-image` 是“兼容模型名”
- Vertex 渠道内的真实承载模型是 `Imagen 3`

---

## 8. 验证脚本

当前仓库中已经有一个可运行的 Vertex 图片验证脚本：

- `backend/app/test/test_vertex_api.py`

该脚本当前使用：

- `google-genai`
- `vertexai=True`
- `api_key=...`
- `imagen-4.0-generate-001`

运行方式：

```bash
/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python backend/app/test/test_vertex_api.py
```

最近一次验证结果：

- 成功生成图片
- 输出文件位于 `backend/app/test/output/`

---

## 9. 常见问题

### 9.1 为什么 `vertexai.preview.vision_models.ImageGenerationModel` 不适合当前项目

因为当前项目拿到的是 API key，而不是 Bearer token。

在实测中：

- `vertexai.preview.vision_models.ImageGenerationModel` 更偏向 ADC / quota project 体系
- 当前环境直接使用它会触发 quota project / ADC 相关限制

所以不要把它当成当前项目的主实现方案。

### 9.2 为什么 `gemini-2.5-flash-image` 文档有，但当前账号不能用

这类情况通常意味着：

- 当前 API key 绑定的账号 / 项目没有访问权限
- 或当前请求落到的区域 / 发布模型映射不可用

本次实测返回的是 `404 NOT_FOUND`，不是代码拼错。

### 9.3 为什么 capability 模型不能直接用

因为在 `generate_images` 场景下它们返回的是：

- `400 INVALID_ARGUMENT`
- 提示 `invalid endpoint`

因此不应把 capability 型号当成标准文生图 endpoint 使用。

---

## 10. 接入落地建议

如果你的目标是尽快把 Vertex 接到本项目，建议顺序如下：

1. 先用 `Imagen 4` 完成标准图片生成接口接入
2. 再补 `Gemini 3.1 Flash Image` 作为多模态图片生成能力
3. 在配置层为模型做白名单控制
4. 在调用层区分 `generate_images` 与 `generate_content`
5. 对 `404 / 429 / 400 invalid endpoint` 做明确错误分类

最稳妥的第一版推荐：

- 默认模型：`imagen-4.0-generate-001`
- 快速模型：`imagen-4.0-fast-generate-001`
- Gemini 图片模型：`gemini-3.1-flash-image-preview`

---

## 11. 参考资料

### Vertex 官方文档

- Vertex 图片总览  
  `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/overview?hl=zh-cn`
- Gemini 图片生成  
  `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/image-generation?hl=zh-cn`
- Gemini 2.5 Flash Image  
  `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-image`
- Gemini 3 Pro Image  
  `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-pro-image`
- Gemini 3.1 Flash Image  
  `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-flash-image`
- Imagen 3 模型页  
  `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/3-0-generate`

### GoogleCloudPlatform 官方 notebook

- Gemini 2.5 Image  
  `https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_2_5_image_gen.ipynb`
- Gemini 3 Image  
  `https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_3_image_gen.ipynb`
- Gemini 3.1 Flash Image  
  `https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_3_1_flash_image_gen.ipynb`
