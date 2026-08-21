# 媒体工作台

媒体工作台是用户端独立页面，入口位于：

- `用户端 -> 媒体工作台`
- 路由：`/user/media-workbench`

## 支持能力

- 图片生成：调用 `/v1/images/generations`
- 参考图生图/图片编辑：调用 `/v1/image/edit`，最多携带 7 张参考图，按重复 `image` 字段提交
- 文生视频：调用 `/v1/videos` 创建任务，前端轮询 `/v1/videos/{video_id}`，完成后拉取 `/v1/videos/{video_id}/content`
- 图生视频：调用 `/v1/videos` 创建任务，最多携带 7 张参考图，按重复 `input_reference[]` 字段提交
- 结果预览、打开、下载
- 最近 24 小时媒体调用成功率展示

## 图片渠道路由

图片请求继续走统一模型与渠道映射。

- 用户选择 `1K`：后端优先使用 `OpenAI Image Compatible` 类型渠道。
- 用户选择 `2K` 或 `4K`：后端只保留支持对应尺寸的渠道，通常命中 `OpenAI Image Native Size` 类型渠道。
- 用户选择参考图生图：页面调用现有图片编辑代理 `/v1/image/edit`，模型必须支持 `supports_image_edit`，多张参考图会作为多个 `image` 文件字段进入后端。

排序逻辑只影响图片请求候选，不改变管理端其他渠道配置语义。

## 视频生成

视频模型默认使用 `grok-imagine-video`。

支持参数：

- `seconds`
- `size`
- `resolution_name`
- `preset`
- `input_reference[]`，仅图生视频需要，支持最多 7 张参考图

页面使用异步任务接口 `/v1/videos` 创建视频，随后每 3 秒轮询一次 `/v1/videos/{video_id}`，最长等待 300 秒。任务完成后通过 `/v1/videos/{video_id}/content` 拉取视频 blob，用于页面预览和下载。

## 最近调用成功率

页面调用：

```text
GET /api/user/media-workbench/health?window_hours=24
```

返回固定两个摘要：

- `image_gpt_image_2`
- `video_grok`

健康等级：

- `unknown`：无样本
- `good`：成功率 >= 95%
- `warning`：成功率 >= 80% 且 < 95%
- `bad`：成功率 < 80%

该指标是「最近调用成功率」，不是严格渠道探活结果。

同步视频生成的等待失败、等待超时和完成后内容校验失败，会按 `video_generation` 失败样本记录，且扣费字段为 `0`，用于反映工作台中用户实际遇到的视频生成失败。

## 计费规则

媒体工作台不新增绕过计费的专用生成接口：

- 图片生成继续调用 `/v1/images/generations`，由图片代理完成渠道路由、结果校验、日志和媒体积分扣费。
- 参考图生图继续调用 `/v1/image/edit`，由图片编辑代理完成渠道路由、结果校验、日志和媒体积分扣费。
- 视频生成调用 `/v1/videos` 创建任务，页面轮询完成后拉取 `/v1/videos/{video_id}/content`，由视频内容接口完成内容校验与扣费。

失败请求只记录失败日志，`image_credits_charged` 为 `0`。图片生成和参考图生图必须解析到有效图片后才进入 `_deduct_image_credits_and_log()`；视频创建阶段不扣费，必须完成并能通过 `/content` 校验后才进入 `_bill_video_route_if_needed()` / `_log_video_success()`，因此生成失败、超时、渠道异常或内容为空不会扣费。
