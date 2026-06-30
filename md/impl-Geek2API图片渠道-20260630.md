# Geek2API图片渠道 Impl

## 任务概述

以最小改动接入 Geek2API `gpt-image-2` 图片渠道，使媒体工作台继续使用现有 `image_size + aspect_ratio + n + quality` 参数即可生成符合 Geek2API 实测尺寸的图片。

## 文件变更清单

- `backend/app/services/channel_service.py`
  - 新增 `geek2api-image` provider_variant。
  - 声明支持 `1K/2K/4K` 和图片编辑。
  - 默认关闭健康检查，避免普通文本健康检查误打图片渠道。
- `backend/app/services/proxy_service.py`
  - 新增 Geek2API 专用尺寸映射表。
  - `geek2api-image` 复用 OpenAI 图片链路，但在 `image_size + aspect_ratio` 转像素尺寸时使用 Geek2API 实测尺寸。
  - 显式 `size=2048x1152` 等 Geek2API 支持的像素尺寸优先；不支持的显式尺寸返回 400，避免误转成 OpenAI 原生尺寸。
- `backend/app/services/health_service.py`
  - 将 `geek2api-image` 识别为 OpenAI 图片生成健康检查类型。
- `frontend/src/views/admin/ChannelManage.vue`
  - 管理端渠道类型下拉新增 `Geek2API Image`。
  - 标签、颜色、白名单和健康检查默认值支持新类型。
- `frontend/src/views/admin/ModelManage.vue`
  - 模型映射渠道标签和提示支持 `geek2api-image`。
- `frontend/src/views/user/MediaWorkbench.vue`
  - 图片生成新增数量 `1/2/4` 和质量 `low/medium/high` 控件。
  - 比例选项补齐 `3:2`、`2:3`、`5:4`、`4:5`、`21:9`，与 Geek2API 尺寸表保持一致。
- `backend/sql/init.sql`、`backend/sql/initData.sql`、`sql/initData.sql`
  - 更新 `provider_variant` 注释。
- `backend/sql/upgrade_geek2api_image_channel_20260630.sql`
  - 新增可选升级脚本，默认不写入真实 API Key。
  - 已有 `gpt-image-2` 模型时不覆盖运营侧自定义模型配置，只补缺失的分辨率规则。

## 核心代码说明

渠道配置：

```text
provider_variant = geek2api-image
protocol_type = openai
auth_header_type = authorization
base_url = https://www.geek2api.com
actual_model_name = gpt-image-2
```

媒体工作台请求：

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "response_format": "b64_json",
  "image_size": "2K",
  "aspect_ratio": "16:9",
  "quality": "high",
  "n": 1
}
```

后端命中 `geek2api-image` 后会转为：

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "response_format": "b64_json",
  "size": "2048x1152",
  "quality": "high",
  "n": 1
}
```

## 测试验证

已执行：

```bash
python -m py_compile backend/app/services/channel_service.py backend/app/services/proxy_service.py backend/app/services/health_service.py
npm run build
```

尺寸映射断言：

```text
1K 1:1 -> 1024x1024
2K 16:9 -> 2048x1152
4K 16:9 -> 3840x2160
1K 9:16 -> 720x1280
2K 9:16 -> 1152x2048
4K 9:16 -> 2160x3840
2K 5:4 -> 2080x1664
4K 21:9 -> 3808x1632
explicit size -> 2048x1152
unsupported explicit size -> INVALID_IMAGE_SIZE
```
