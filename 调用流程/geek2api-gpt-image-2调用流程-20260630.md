# Geek2API gpt-image-2 调用流程

## 基本信息

- Base URL：`https://www.geek2api.com`
- Endpoint：`POST /v1/images/generations`
- 模型：`gpt-image-2`
- 鉴权：`Authorization: Bearer <GEEK2API_API_KEY>`
- 返回格式：建议 `response_format=b64_json`

## 请求示例

```bash
curl --http1.1 -X POST "https://www.geek2api.com/v1/images/generations" \
  -H "Authorization: Bearer $GEEK2API_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "A clean product photo of a futuristic camera",
    "size": "2048x1152",
    "quality": "low",
    "n": 1,
    "response_format": "b64_json"
  }'
```

## 支持参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `model` | string | 固定使用 `gpt-image-2` |
| `prompt` | string | 图片提示词 |
| `size` | string | 像素尺寸，如 `2048x1152` |
| `quality` | string | `low`、`medium`、`high` |
| `n` | integer | `1`、`2`、`4` |
| `response_format` | string | `b64_json` |

## 系统接入方式

系统内不让用户端直连 Geek2API，而是通过当前 `/v1/images/generations` 统一入口转发。

渠道配置：

```text
protocol_type = openai
provider_variant = geek2api-image
auth_header_type = authorization
base_url = https://www.geek2api.com
actual_model_name = gpt-image-2
```

媒体工作台传入：

```json
{
  "image_size": "2K",
  "aspect_ratio": "16:9",
  "quality": "high",
  "n": 1
}
```

后端转发给 Geek2API：

```json
{
  "size": "2048x1152",
  "quality": "high",
  "n": 1
}
```

## 尺寸映射

| 档位 | 1:1 | 16:9 | 9:16 | 3:2 | 2:3 | 4:3 | 3:4 | 5:4 | 4:5 | 21:9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1K | 1024x1024 | 1280x720 | 720x1280 | 1008x672 | 672x1008 | 1024x768 | 768x1024 | 1040x832 | 832x1040 | 1344x576 |
| 2K | 2048x2048 | 2048x1152 | 1152x2048 | 2064x1376 | 1376x2064 | 2048x1536 | 1536x2048 | 2080x1664 | 1664x2080 | 2016x864 |
| 4K | 2880x2880 | 3840x2160 | 2160x3840 | 3504x2336 | 2336x3504 | 3264x2448 | 2448x3264 | 3200x2560 | 2560x3200 | 3808x1632 |

## 返回内容

OpenAI 图片兼容格式：

```json
{
  "created": 1782820700,
  "data": [
    {
      "b64_json": "..."
    }
  ]
}
```

系统会继续转换为当前平台统一响应，并按图片积分计费。
