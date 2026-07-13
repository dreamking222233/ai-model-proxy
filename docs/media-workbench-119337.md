# 媒体工作台 119337 Grok 视频

## 页面入口

- 用户端菜单：媒体工作台
- 路由：`/user/media-workbench`

页面通过 `/api/user/chat/models` 读取启用模型和 `video_workbench_capabilities`，根据实际启用渠道映射动态展示视频模式、参考图数量、时长、画面比例、清晰度和预设。

## 119337 模型能力

### Grok 视频

- 用户模型：`grok-video`
- 119337 实际模型：`grok-image-video`
- 支持文生视频和参考图生视频。
- 无参考图：支持 `4/6/8/10/12/15` 秒。
- 上传参考图：按当前产品规则支持 `4/6/8/10` 秒，最多 7 张。
- 比例：`1:1/16:9/9:16/4:3/3:4/3:2/2:3`。
- 清晰度：`720p/480p`。

### Grok 视频 1.5 预览

- 用户模型：`grok-imagine-video-1.5-preview`
- 119337 实际模型：`grok-video-1.5`
- 只支持参考图生视频。
- 必须且只能上传 1 张参考图。
- 支持 `4/6/8/10/12/15` 秒。
- 比例：`16:9/9:16`。
- 清晰度：`720p/480p`。

## 调用链

1. 页面以 multipart 请求 `POST /v1/videos`，提交 `model/prompt/seconds/aspect_ratio/size/resolution_name/input_reference[]`。
2. 后端按统一模型映射选择渠道；119337 渠道使用 `provider_variant=grok-video-119337`。
3. 后端在计费预检前根据实际模型与参考图数量规范化最终秒数、比例和清晰度。
4. 参考图片转换为完整 data URL，并以 JSON `image_urls` 调用上游 `POST /v1/video/generations`。
5. 页面轮询本系统 `GET /v1/videos/{task_id}`；本系统代理查询上游任务。
6. 任务完成后页面请求 `/v1/videos/{task_id}/content`，后端校验 `data.result_url` 视频内容后再扣媒体积分并代理下载。

## 计费

- 创建任务阶段不扣费。
- 只有任务完成且视频内容校验成功后扣费。
- 通用模型上传参考图并把 12/15 秒规范化为 10 秒时，按最终 10 秒计费。
- 上游失败、轮询失败、结果 URL 为空或视频内容无效时不扣费。

## 参考视频边界

当前 119337 文档只定义参考图片字段 `image_urls`，没有参考视频或视频转视频参数。因此页面只开放图片文件上传，不会把视频文件错误地作为图片 data URL 提交。

如果上游后续提供参考视频字段，还需要明确字段名、文件/URL 格式、大小、编码、时长和模型约束后再扩展。

## 渠道配置

- `protocol_type`: `openai`
- `provider_variant`: `grok-video-119337`
- `auth_header_type`: `authorization`
- `base_url`: 119337 服务地址，可填根地址或 `/v1`
- `health_check_enabled`: `0`
- `actual_model_name`:
  - `grok-video` -> `grok-image-video`
  - `grok-imagine-video-1.5-preview` -> `grok-video-1.5`

生产配置不要把 API Key 写入仓库或 SQL 文件。
