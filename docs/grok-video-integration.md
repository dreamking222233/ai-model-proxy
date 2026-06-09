# Grok 视频生成接入说明

当前系统通过 OpenAI 兼容渠道接入 grok2api 视频接口，支持：

- `POST /v1/videos`
- `POST /v1/created/video`
- `POST /v1/chat/completions`
- `GET /v1/videos/{video_id}`
- `GET /v1/videos/{video_id}/content`

## 管理端配置

1. 执行升级脚本：

```sql
source backend/sql/upgrade_grok_video_model_20260528.sql;
```

2. 新增或确认渠道：

- `protocol_type`: `openai`
- `base_url`: grok2api 服务地址，例如 `http://127.0.0.1:8000`
- `auth_header_type`: `authorization`
- `api_key`: grok2api 的 API Key

3. 为统一模型 `grok-imagine-video` 添加渠道映射：

- `actual_model_name`: `grok-imagine-video`

## 创建视频

### 文生视频：Chat Completions

`POST /v1/chat/completions` 适合文生视频，可使用 `stream=true` 流式返回上游生成的视频 URL。

```bash
curl -N -X POST "https://你的域名/v1/chat/completions" \
  -H "Authorization: Bearer sk-你的密钥" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-imagine-video",
    "stream": true,
    "messages": [
      {"role": "user", "content": "霓虹雨夜街头，电影感慢镜头追拍"}
    ],
    "video_config": {
      "seconds": 10,
      "size": "1792x1024",
      "resolution_name": "720p",
      "preset": "normal"
    }
  }'
```

### 图生视频：任务接口

`POST /v1/created/video` 是同步等待接口：系统会先向上游创建视频任务，再自动轮询任务状态，直到生成完成后返回任务信息和本地下载地址。

```bash
curl -X POST "https://你的域名/v1/created/video" \
  -H "Authorization: Bearer sk-你的密钥" \
  -F "model=grok-imagine-video" \
  -F "prompt=霓虹雨夜街头，电影感慢镜头追拍" \
  -F "seconds=10" \
  -F "size=1792x1024" \
  -F "resolution_name=720p" \
  -F "preset=normal" \
  -F "input_reference[]=@reference.png"
```

返回中的 `id` 即视频任务 ID；`content_url` 为当前系统代理的视频下载地址，例如 `/v1/videos/video_xxx/content`。

`POST /v1/videos` 保持异步创建语义：创建成功即返回任务 ID，调用方可自行查询状态。

支持参数：

- `seconds`: `6`、`10`、`12`、`16`、`20`
- `size`: `720x1280`、`1280x720`、`1024x1024`、`1024x1792`、`1792x1024`
- `resolution_name`: `480p`、`720p`
- `preset`: `fun`、`normal`、`spicy`、`custom`
- `input_reference[]`: 图生视频参考图，最多 7 张

## 查询与下载

```bash
curl "https://你的域名/v1/videos/video_xxx" \
  -H "Authorization: Bearer sk-你的密钥"

curl -L "https://你的域名/v1/videos/video_xxx/content" \
  -H "Authorization: Bearer sk-你的密钥" \
  -o result.mp4
```

## 计费规则

视频生成复用现有图片积分账户作为媒体积分账户：

- `unified_model.billing_type=image_credit` 时，任务创建阶段不扣减积分；必须在完成状态且视频内容校验成功后才扣减积分。
- 视频模型的 `unified_model.image_credit_multiplier` 表示每秒媒体积分单价。
- 扣减数量为 `image_credit_multiplier * seconds`。
- 请求日志使用 `request_type=video_generation` 区分视频请求。
- 上游返回失败、未返回视频 URL、视频 URL 内容为空或返回 JSON/text 错误内容时，记录失败日志且不扣减积分。

默认升级脚本将 `grok-imagine-video` 设置为 `0.500` 积分/秒，可在管理端按实际成本调整。
