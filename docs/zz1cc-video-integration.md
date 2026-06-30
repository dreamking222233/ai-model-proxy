# zz1cc 视频接入说明

## 渠道配置

- 协议类型：`OpenAI`
- OpenAI 渠道类型：`zz1cc 视频`
- `provider_variant`：`zz1cc-video`
- `base_url`：`https://zz1cc.cc.cd` 或 `https://zz1cc.cc.cd/v1`
- 认证：`Authorization: Bearer <API_KEY>`
- 健康监控：默认关闭

## 模型

系统预置两个统一视频模型：

- `video-ds-2.0`
- `video-ds-2.0-fast`

管理员创建 zz1cc 渠道后，在模型映射中将两个模型分别映射到同名 `actual_model_name`。

## 对外接口

用户侧接口保持现有视频生成返回值，不需要改客户端解析逻辑：

- `POST /v1/videos`
- `POST /v1/created/video`
- `GET /v1/videos/{video_id}`
- `GET /v1/videos/{video_id}/content`

`/v1/chat/completions` 视频兼容入口首版不支持 `zz1cc-video` 渠道，会返回 `VIDEO_MODEL_NOT_SUPPORTED`。

## 参数映射

| 系统字段 | zz1cc 字段 | 说明 |
| --- | --- | --- |
| `model` | `model` | 使用模型映射后的 `actual_model_name` |
| `prompt` | `prompt` | 必填 |
| `seconds` | `seconds` | 缺省默认 15，仅允许 15 |
| `size` | `aspect_ratio` | `720x1280/1024x1792 -> 9:16`，`1280x720/1792x1024/848x480/1696x960/1920x1080 -> 16:9`，`1024x1024 -> 1:1` |
| `input_reference[]` | `images[]` | 只允许 `image/*`，转成 data URL 后 JSON 传递 |

`resolution_name`、`preset` 当前 zz1cc 文档未声明支持，系统不会透传。

## 返回值

创建响应会归一任务 ID：

```text
id = body.id || body.task_id || body.request_id
```

系统对外仍返回标准视频任务对象，并附带：

- `id`
- `status`
- `content_url`
- `retrieve_url`
- `usage`

`/content` 直接代理 zz1cc `/v1/videos/{id}/content`。

## 计费

- 创建任务时不扣费。
- 任务完成后先校验 content 可获取且不是 JSON/text 错误内容，再扣媒体积分。
- 默认倍率为 `0.500` 积分/秒，可在模型管理中调整。

## 联调待确认

- `video-ds-2.0` 是否与 `video-ds-2.0-fast` 完全同参数。
- 上游真实状态枚举和失败 body 形态。
- 参考图数量、单图大小、总 JSON body 限制。
- `/content` 是否稳定返回视频二进制、302 或签名 URL。
