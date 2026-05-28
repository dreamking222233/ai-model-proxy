# Grok 视频生成接入说明

当前系统通过 OpenAI 兼容渠道接入 grok2api 视频接口，支持：

- `POST /v1/videos`
- `POST /v1/created/video`
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

返回中的 `id` 即视频任务 ID。

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

- `unified_model.billing_type=image_credit` 时，创建任务成功后扣减积分。
- 扣减数量来自 `unified_model.image_credit_multiplier`。
- 请求日志使用 `request_type=video_generation` 区分视频请求。

默认升级脚本将 `grok-imagine-video` 的单次积分设置为 `5.000`，可在管理端按实际成本调整。
