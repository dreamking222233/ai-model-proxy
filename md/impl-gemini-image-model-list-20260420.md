## 任务概述

调整 Gemini 生图模型列表与积分倍率，新增 `gemini-2.5-flash-image`，并将图片模型统一为以下三项：

- `gemini-2.5-flash-image`：1 积分/次
- `gemini-3.1-flash-image-preview`：2 积分/次
- `gemini-3-pro-image-preview`：3 积分/次

## 文件变更清单

- `backend/sql/init.sql`
- `backend/sql/update-20260406-gemini-image.sql`
- `frontend/src/views/user/QuickStart.vue`
- `md/plan-gemini-image-model-list-20260420.md`

## 核心代码说明

- 在初始化 SQL 中补充 `gemini-2.5-flash-image` 的模型定义与 Google 渠道映射。
- 在升级 SQL 中补充 `gemini-2.5-flash-image` 的幂等插入逻辑，并修正：
  - `gemini-3.1-flash-image-preview` 为 2 积分/次
  - `gemini-3-pro-image-preview` 为 3 积分/次
- 在快速开始页面更新了生图接口支持模型与计费文案，避免文档仍停留在旧的双模型配置。

## 测试验证

- 查询本地数据库 `unified_model` 与 `model_channel_mapping`，确认三条图片模型配置如下：
  - `gemini-2.5-flash-image` -> `Google Gemini Official` -> `1 积分/次`
  - `gemini-3.1-flash-image-preview` -> `Google Gemini Official` -> `2 积分/次`
  - `gemini-3-pro-image-preview` -> `Google Gemini Official` -> `3 积分/次`
- 检查前端快速开始文案，确认图片模型示例与支持列表已经同步更新。
