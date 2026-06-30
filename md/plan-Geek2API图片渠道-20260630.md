# Geek2API图片渠道 Plan

## 用户原始需求

接入 Geek2API `gpt-image-2` 图片渠道，尽量使用最小改动，使媒体工作台等页面能使用 1K/2K/4K、16:9/9:16 等横竖屏尺寸，并支持 `n` 生成多张图和 `quality=low/medium/high`。

## 技术方案设计

- 新增 OpenAI 渠道子类型 `geek2api-image`，不复用/修改现有 `openai-image-native-size`，避免影响已接入渠道。
- `geek2api-image` 仍走现有 OpenAI 图片接口链路：
  - 生成：`/v1/images/generations`
  - 编辑：`/v1/images/edits`
  - 鉴权：`Authorization: Bearer <api_key>`
  - 返回：`response_format=b64_json`
- 在后端仅针对 `geek2api-image` 使用 Geek2API 实测尺寸表，将媒体工作台的 `image_size + aspect_ratio` 映射到 Geek2API 支持的像素尺寸。
- 媒体工作台补充图片数量和质量控件，继续调用当前系统 `/v1/images/generations`，不直连 Geek2API。

## 涉及文件清单

- `backend/app/services/channel_service.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `frontend/src/views/admin/ChannelManage.vue`
- `frontend/src/views/admin/ModelManage.vue`
- `frontend/src/views/user/MediaWorkbench.vue`
- `backend/sql/upgrade_geek2api_image_channel_20260630.sql`
- `backend/sql/init.sql`
- `backend/sql/initData.sql`
- `sql/initData.sql`

## 实施步骤概要

1. 后端新增 `geek2api-image` provider_variant 常量、归一化、能力和默认健康检查策略。
2. 图片转发逻辑中将 `geek2api-image` 视为原生尺寸渠道，并使用 Geek2API 尺寸映射表。
3. 管理端渠道和模型映射页面支持选择与展示 `Geek2API Image`。
4. 媒体工作台图片生成补充 `n`、`quality` 和扩展比例选项。
5. 增加可选 SQL 升级脚本，补齐模型、分辨率规则和渠道类型注释。
6. 运行后端编译、尺寸映射断言和前端构建。
