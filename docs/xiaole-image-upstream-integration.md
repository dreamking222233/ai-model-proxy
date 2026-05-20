# XiaoLe 类型图片上游接入说明

本文档说明如何在当前系统中接入一个“也是由当前源码搭建”的上游渠道，用来承接图片生成与图片编辑请求。

适用场景：

- 上游平台本身也是这套系统
- 上游图片接口走当前系统自带的别名路径
- 文生图使用 `/v1/image/created`
- 编辑图使用 `/v1/image/edit`

不适用场景：

- 上游直接提供标准 OpenAI 图片接口 `/v1/images/generations`、`/v1/images/edits`
- 上游支持原生 `size/quality` 且希望透传 2K/4K

这两类场景分别应该使用：

- `OpenAI Image Compatible`
- `OpenAI Image Native Size`

## 1. 前置条件

开始前请确认：

- 目标上游已经部署完成，能正常访问
- 目标上游已创建可用 API Key
- 目标上游中，目标图片模型已经有可用渠道
- 当前系统版本已经包含 `XiaoLe 类型图片上游`

说明：

- 本次接入不需要新增数据库字段
- 复用的仍然是 `channel.provider_variant`
- 新增的只是一个渠道类型取值：`openai-image-modelinvoke`

## 2. 在后台新增渠道

进入：

- `管理后台 -> 渠道管理 -> 新增渠道`

推荐配置如下：

| 字段 | 推荐值 |
|------|--------|
| 协议 | `OpenAI` |
| OpenAI 渠道类型 | `XiaoLe 类型图片上游` |
| 基础 URL | `https://你的上游域名` 或 `https://你的上游域名/v1` |
| API Key | 上游系统中的用户 API Key |
| 上游认证 Header 类型 | `Authorization: Bearer` |
| 优先级 | 按你的路由策略设置，数字越小优先级越高 |
| 启用 | 开启 |
| 参与健康监控 | 默认关闭即可 |

建议：

- `base_url` 推荐直接填域名根路径，例如 `https://relay.example.com`
- 即使填成 `https://relay.example.com/v1` 也可以，系统会自动兼容

该类型的实际转发规则是：

- 图片生成转发到上游 `/v1/image/created`
- 图片编辑转发到上游 `/v1/image/edit`

## 3. 配置模型映射

进入：

- `管理后台 -> 模型管理`

选择要承接的图片模型后，新增映射：

### 3.1 `gpt-image-2` 文生图/编辑图

推荐映射：

| 当前系统统一模型 | 渠道 | actual_model_name |
|------------------|------|-------------------|
| `gpt-image-2` | XiaoLe 类型图片上游 | `gpt-image-2` |

说明：

- `gpt-image-2` 当前支持文生图，也支持编辑图
- 编辑图是否可用，取决于上游系统里 `gpt-image-2` 是否已有可用图片渠道

### 3.2 Gemini 图片模型

如果只是文生图，可继续映射：

| 当前系统统一模型 | 渠道 | actual_model_name |
|------------------|------|-------------------|
| `gemini-2.5-flash-image` | XiaoLe 类型图片上游 | `gemini-2.5-flash-image` |
| `gemini-3.1-flash-image-preview` | XiaoLe 类型图片上游 | `gemini-3.1-flash-image-preview` |
| `gemini-3-pro-image-preview` | XiaoLe 类型图片上游 | `gemini-3-pro-image-preview` |

说明：

- 这些模型只承接文生图
- 图片编辑链路仍然只适用于支持编辑图的模型

## 4. 渠道类型选择建议

### 4.1 什么时候选 `XiaoLe 类型图片上游`

当上游满足以下条件时使用：

- 上游是当前系统
- 希望转发到上游的 `/v1/image/created`
- 希望转发到上游的 `/v1/image/edit`

### 4.2 什么时候选 `OpenAI Image Compatible`

当上游满足以下条件时使用：

- 上游是标准 OpenAI 兼容图片网关
- 使用 `/v1/images/generations`
- 使用 `/v1/images/edits`
- 主要承接默认 1K 图片请求

### 4.3 什么时候选 `OpenAI Image Native Size`

当上游满足以下条件时使用：

- 上游支持标准 OpenAI 图片接口
- 需要透传 `size`
- 需要透传 `quality`
- 需要承接 `1K/2K/4K`

## 5. 当前行为限制

`XiaoLe 类型图片上游` 当前默认行为：

- 支持图片生成
- 支持图片编辑
- 默认声明的分辨率能力为 `1K`

这意味着：

- 1K 请求可以正常命中
- 如果当前模型发起的是 2K/4K 请求，系统不会把它路由到这个 1K 渠道

如果后续要让这类上游承接更高分辨率，需要继续扩展渠道能力模型。

## 6. 最小验证步骤

完成渠道与模型映射后，建议做两次验证。

### 6.1 验证文生图

请求当前系统：

```bash
curl -X POST "https://你的当前系统域名/v1/images/generations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-当前系统-key" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "一只戴宇航头盔的橘猫站在月球上",
    "response_format": "b64_json"
  }'
```

预期：

- 当前系统命中 `XiaoLe 类型图片上游`
- 再由该渠道转发到上游 `/v1/image/created`
- 返回图片 `b64_json`

### 6.2 验证编辑图

请求当前系统：

```bash
curl -X POST "https://你的当前系统域名/v1/image/edit" \
  -H "Authorization: Bearer sk-当前系统-key" \
  -F "model=gpt-image-2" \
  -F "prompt=把图片中的天空改成黄昏晚霞" \
  -F "image=@./input.png"
```

预期：

- 当前系统命中 `XiaoLe 类型图片上游`
- 再由该渠道转发到上游 `/v1/image/edit`
- 返回编辑后的图片结果

## 7. 常见问题

### 7.1 为什么已经是 OpenAI 协议，还要单独加 XiaoLe 类型

因为图片接口路径不同。

标准 OpenAI 图片接口使用：

- `/v1/images/generations`
- `/v1/images/edits`

当前系统图片别名接口使用：

- `/v1/image/created`
- `/v1/image/edit`

如果直接按标准 OpenAI 图片渠道处理，会打错上游路径。

### 7.2 为什么没有要求改数据库结构

因为现有 `channel.provider_variant` 已经足够承载这个能力。

本次只是在业务逻辑中新增了一个渠道类型值：

- `openai-image-modelinvoke`

### 7.3 为什么后台里这个类型默认不参与健康监控

与现有图片专用渠道保持一致：

- 图片健康检查通常成本更高
- 很多图片上游不适合高频探活

如果你确实需要，也可以手动开启健康监控。

## 8. 推荐配置总结

如果你接入的是另一套“小乐 AI / 当前系统”实例，图片渠道推荐这样配：

| 项 | 推荐值 |
|----|--------|
| 协议 | `OpenAI` |
| 渠道类型 | `XiaoLe 类型图片上游` |
| 认证头 | `Authorization: Bearer` |
| base_url | `https://上游域名` |
| `gpt-image-2` 映射 | `actual_model_name = gpt-image-2` |

这样配置后：

- 当前系统对外仍可保持原有 4 个图片接口
- 转发到上游时，会自动走当前系统自己的图片别名接口
