# 119337 Grok 视频 API 调用流程

本文档记录 `api.119337.xyz` 渠道的 Grok 视频 API 调用方式，包括模型查询、文生视频、单参考图生视频、多参考图生视频、异步任务轮询、结果下载和错误处理。

> 来源：Google 文档《GROK 视频 API / Grok Video API 接入文档》，2026-07-14 整理。本文档是对上游接入说明的格式化记录，未在当前项目中实际发起生成请求。

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Base URL | `https://api.119337.xyz` |
| 鉴权方式 | `Authorization: Bearer <YOUR_API_KEY>` |
| 请求格式 | `Content-Type: application/json` |
| 响应格式 | JSON |
| 模型列表 | `GET /v1/models` |
| 创建视频任务 | `POST /v1/video/generations` |
| 查询视频任务 | `GET /v1/video/generations/{task_id}` |

视频生成是异步任务。创建接口首先返回 `task_id` 或 `id`，调用方需保存该 ID，然后持续调用查询接口，直到任务成功或失败。

## 2. 鉴权方式

请在用户控制台创建或复制 API Key，并在请求头中传入：

```http
Authorization: Bearer <YOUR_API_KEY>
```

JSON 请求追加：

```http
Content-Type: application/json
```

不要将 API Key 写入前端页面、移动端安装包或公开仓库，建议由服务端代为调用。

## 3. 查询可用模型

```bash
curl -X GET "https://api.119337.xyz/v1/models" \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

当前文档列出的视频模型：

| 模型 ID | 推荐用途 | 文生视频 | 单参考图 | 多参考图 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `grok-image-video` | 通用默认模型 | 支持，最长 15 秒 | 支持，最长 15 秒 | 支持，最多 7 张，最长 10 秒 | 多参考图请求超过 10 秒时会自动按 10 秒处理 |
| `grok-video-1.5` | 单图生视频预览模型 | 不支持 | 支持，最长 15 秒 | 不支持 | 必须提供且只能提供 1 张参考图 |

模型列表以 `GET /v1/models` 的实时返回为准。接入时不建议将可用模型列表完全写死。

## 4. 创建视频任务

### 4.1 接口地址

```text
POST https://api.119337.xyz/v1/video/generations
```

### 4.2 请求参数

| 参数 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `model` | 是 | string | 模型 ID，例如 `grok-image-video` |
| `prompt` | 是 | string | 视频生成提示词 |
| `seconds` | 否 | integer | 视频秒数，默认建议传 `4` |
| `aspect_ratio` | 否 | string | 画幅比例，默认建议传 `16:9` |
| `resolution` | 否 | string | 清晰度，建议 `720p` 或 `480p` |
| `image_urls` | 否 | array\<string> | 参考图 URL 或完整 base64 data URL 列表，推荐使用的统一字段 |
| `images` | 否 | array\<string> | `image_urls` 的兼容字段，二选一 |
| `input_reference` | 否 | object/string | 单参考图字段，可传 `{ "image_url": "..." }` |
| `reference_images` | 否 | array\<string> | 多参考图兼容字段 |

推荐优先使用 `image_urls`，由服务端根据模型和图片数量自动转换。

字段使用规则：

- `images` 与 `image_urls` 含义相同，不要同时传入。
- 优先只使用 `image_urls`，不要再同时传 `input_reference` 或 `reference_images`。
- `grok-video-1.5` 必须且只能传 1 张参考图。
- `grok-image-video` 最多传 7 张参考图。

## 5. 参数限制

### 5.1 视频时长

`grok-image-video` 文生视频、单图生视频，以及 `grok-video-1.5` 单图生视频的建议可选值：

```json
[4, 6, 8, 10, 12, 15]
```

`grok-image-video` 多参考图生视频的建议可选值：

```json
[4, 6, 8, 10]
```

时长规则：

- `grok-image-video` 文生视频和单图生视频最长 15 秒。
- `grok-image-video` 多参考图生视频最长 10 秒；请求超过 10 秒时，服务会自动按 10 秒处理。
- `grok-video-1.5` 只支持单图生视频，最长 15 秒。

### 5.2 画幅比例

`grok-image-video` 建议值：

```json
["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"]
```

`grok-video-1.5` 建议值：

```json
["16:9", "9:16"]
```

### 5.3 清晰度

```json
["720p", "480p"]
```

### 5.4 参考图要求

- 推荐使用公网可直接访问的 HTTPS 图片直链。
- 支持完整 base64 data URL，例如 `data:image/png;base64,...`。
- 不要传入裸 base64，例如 `iVBORw0KGgo...`。
- 图片 URL 不应依赖登录、Cookie、防盗链或临时跳转。
- 如果上游无法抓取图片，任务会失败并返回图片抓取错误。

## 6. 请求示例

### 6.1 文生视频

```bash
curl -X POST "https://api.119337.xyz/v1/video/generations" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-image-video",
    "prompt": "A cinematic shot of a red sports car driving through rainy neon streets at night",
    "seconds": 6,
    "aspect_ratio": "16:9",
    "resolution": "720p"
  }'
```

### 6.2 单参考图生视频

```bash
curl -X POST "https://api.119337.xyz/v1/video/generations" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-image-video",
    "prompt": "Animate the product with a slow rotating camera, soft studio light, premium commercial style",
    "seconds": 6,
    "aspect_ratio": "9:16",
    "resolution": "720p",
    "image_urls": [
      "https://example.com/product.png"
    ]
  }'
```

单图也可以使用 `input_reference`：

```json
{
  "model": "grok-image-video",
  "prompt": "Animate the product with a slow rotating camera",
  "seconds": 6,
  "aspect_ratio": "9:16",
  "resolution": "720p",
  "input_reference": {
    "image_url": "https://example.com/product.png"
  }
}
```

### 6.3 多参考图生视频

```bash
curl -X POST "https://api.119337.xyz/v1/video/generations" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-image-video",
    "prompt": "Create a smooth product showcase video using these references, luxury lighting, clean background",
    "seconds": 10,
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "image_urls": [
      "https://example.com/ref-1.png",
      "https://example.com/ref-2.png"
    ]
  }'
```

多参考图规则：

- `grok-image-video` 最多支持 7 张参考图。
- 多参考图最长支持 10 秒；传入的 `seconds` 大于 10 时，服务会自动按 10 秒处理。
- 不要在同一个请求中混用 `input_reference`、`reference_images`、`image_urls` 或 `images`。

### 6.4 `grok-video-1.5` 单图生视频

```bash
curl -X POST "https://api.119337.xyz/v1/video/generations" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-video-1.5",
    "prompt": "Use the reference image as the main subject and create a smooth cinematic motion",
    "seconds": 4,
    "aspect_ratio": "16:9",
    "resolution": "480p",
    "image_urls": [
      "https://example.com/reference.png"
    ]
  }'
```

该模型必须传入且只能传入 1 张参考图，最长支持 15 秒。不要用它提交纯文生视频或多参考图请求。

## 7. 创建任务响应

创建成功后会返回任务对象，关键字段是 `task_id` 或 `id`：

```json
{
  "id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "object": "video",
  "model": "grok-image-video",
  "status": "queued",
  "progress": 0,
  "created_at": 1780000000
}
```

客户端应兼容两种 ID 字段：

```javascript
const taskId = response.task_id || response.id
```

## 8. 查询任务状态

```bash
curl -X GET "https://api.119337.xyz/v1/video/generations/task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

### 8.1 处理中响应

```json
{
  "code": "success",
  "message": "",
  "data": {
    "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "IN_PROGRESS",
    "progress": "30%",
    "result_url": "",
    "fail_reason": ""
  }
}
```

### 8.2 成功响应

```json
{
  "code": "success",
  "message": "",
  "data": {
    "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "SUCCESS",
    "progress": "100%",
    "result_url": "https://example.com/generated-video.mp4",
    "fail_reason": ""
  }
}
```

### 8.3 失败响应

```json
{
  "code": "success",
  "message": "",
  "data": {
    "task_id": "task_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "FAILURE",
    "progress": "100%",
    "result_url": "",
    "fail_reason": "Image URL could not be fetched: Fetching image failed with HTTP status 400 Bad Request."
  }
}
```

### 8.4 状态判断规则

| 条件 | 含义 | 处理方式 |
| --- | --- | --- |
| `data.status == "SUCCESS"` 且 `data.result_url` 非空 | 生成成功 | 立即保存或下载 `data.result_url` |
| `data.status == "FAILURE"` | 生成失败 | 读取并展示 `data.fail_reason` |
| `SUBMITTED` / `QUEUED` / `IN_PROGRESS` / `NOT_START` | 任务仍在处理 | 继续轮询 |

`progress: "100%"` 只表示任务流程已结束，不代表生成成功。必须以 `data.status` 判断成功或失败。

### 8.5 建议轮询策略

| 配置 | 建议值 |
| --- | --- |
| 轮询间隔 | 5 秒 |
| 最大轮询时长 | 5 分钟 |
| 最大轮询次数 | 60 次 |
| 成功结果 | `data.result_url` |

任务轮询超时时应保留 `task_id`，便于稍后继续查询，不要因为客户端超时就重复创建视频任务。

## 9. 下载视频

`result_url` 是有效期约 1 小时的临时直链。生成成功后应立即下载，并在业务代码中加入自动下载或转存逻辑。

```bash
curl -L -o "grok_video_$(date +%s).mp4" "$result_url"
```

## 10. JavaScript 完整调用示例

```javascript
const BASE_URL = 'https://api.119337.xyz'
const API_KEY = process.env.NEWAPI_API_KEY

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function validateVideoRequest({ model, imageUrls }) {
  if (model === 'grok-video-1.5' && imageUrls.length !== 1) {
    throw new Error('grok-video-1.5 only supports exactly one reference image.')
  }

  if (model === 'grok-image-video' && imageUrls.length > 7) {
    throw new Error('grok-image-video supports at most 7 reference images.')
  }
}

async function createVideo({
  model = 'grok-image-video',
  prompt,
  seconds = 4,
  aspectRatio = '16:9',
  resolution = '720p',
  imageUrls = [],
}) {
  validateVideoRequest({ model, imageUrls })

  const body = {
    model,
    prompt,
    seconds,
    aspect_ratio: aspectRatio,
    resolution,
  }

  if (imageUrls.length > 0) {
    body.image_urls = imageUrls

    if (imageUrls.length >= 2 && Number(body.seconds) > 10) {
      // Multi-reference video is capped at 10 seconds.
      body.seconds = 10
    }
  }

  const createResponse = await fetch(`${BASE_URL}/v1/video/generations`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  const created = await createResponse.json()
  if (!createResponse.ok) {
    throw new Error(`Video request failed: ${JSON.stringify(created)}`)
  }

  const taskId = created.task_id || created.id
  if (!taskId) {
    throw new Error(`No task_id returned: ${JSON.stringify(created)}`)
  }

  for (let i = 0; i < 60; i += 1) {
    await sleep(5000)

    const pollResponse = await fetch(
      `${BASE_URL}/v1/video/generations/${taskId}`,
      {
        headers: {
          Authorization: `Bearer ${API_KEY}`,
        },
      },
    )

    const result = await pollResponse.json()
    if (!pollResponse.ok) {
      throw new Error(`Video poll failed: ${JSON.stringify(result)}`)
    }

    const task = result.data
    if (task?.status === 'SUCCESS' && task.result_url) {
      return {
        task_id: task.task_id,
        video_url: task.result_url,
        raw_response: result,
      }
    }

    if (task?.status === 'FAILURE') {
      throw new Error(
        `Video generation failed: ${task.fail_reason || JSON.stringify(result)}`,
      )
    }
  }

  throw new Error(`Video generation timeout: ${taskId}`)
}
```

## 11. 常见错误

| 错误 | 原因 | 处理方式 |
| --- | --- | --- |
| `401` | API Key 缺失或错误 | 检查 `Authorization: Bearer <YOUR_API_KEY>` |
| `403` | 权限、余额、分组或模型限制 | 检查账号余额、令牌权限和可用模型 |
| `400 prompt is required` | `prompt` 为空 | 提交前校验提示词 |
| `400 model field is required` | `model` 为空 | 使用模型列表接口返回的模型 ID |
| `400 only supports exactly one reference image` | `grok-video-1.5` 未传图或传入多张图 | 该模型只传 1 张参考图 |
| 图片抓取失败 | 服务端无法访问图片 URL | 改用可直接访问的真实直链或完整 base64 data URL |
| 任务状态为 `FAILURE` | 上游生成失败、图片不可访问或参数不支持 | 读取 `data.fail_reason` 并展示给调用方 |
| 轮询超时 | 任务耗时较长或暂时没有结果 | 保留 `task_id`，稍后继续查询 |

## 12. 接入注意事项

- 接入中转站时，不要只依赖 New API/Sub2API 后台的通用“测试”按钮判断视频模型是否可用，应使用实际视频接口路径和映射后的模型名发起真实请求。
- 建议通过 `/v1/models` 动态读取模型列表，不要将模型 ID 写死为单一值。
- 默认推荐使用 `grok-image-video`。
- `grok-video-1.5` 当前仅用于单参考图生视频。
- `grok-image-video` 文生视频、单图生视频最长 15 秒，多参考图最长 10 秒。
- `grok-image-video` 多参考图最多 7 张，请求超过 10 秒时会自动按 10 秒处理。
- `grok-video-1.5` 只支持 1 张参考图，最长 15 秒。
- 最终视频 URL 位于查询响应的 `data.result_url`，有效期约 1 小时，建议生成成功后立即下载。
- 任务失败时 `progress` 也可能是 `"100%"`，必须以 `data.status` 为准。
