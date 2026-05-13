## 用户原始需求

修改 Gemini 生图系列的模型列表：

- `gemini-2.5-flash-image`
- `gemini-3.1-flash-image-preview`
- `gemini-3-pro-image-preview`

积分规则：

- `gemini-2.5-flash-image`：1 积分/次
- `gemini-3.1-flash-image-preview`：2 积分/次
- `gemini-3-pro-image-preview`：3 积分/次

## 技术方案设计

- 更新 `backend/sql/init.sql` 中图片模型初始化数据与 Google 渠道映射，补充 `gemini-2.5-flash-image`。
- 更新 `backend/sql/update-20260406-gemini-image.sql`，保证增量执行时也会补齐新模型并修正 3.1 / 3 pro 的积分倍率。
- 更新本地数据库 `unified_model` 与 `model_channel_mapping`，使当前运行环境立即生效。
- 更新前端快速开始文档示例，避免仍展示旧的双模型列表与旧积分认知。

## 涉及文件清单

- `backend/sql/init.sql`
- `backend/sql/update-20260406-gemini-image.sql`
- `frontend/src/views/user/QuickStart.vue`
- `md/impl-gemini-image-model-list-20260420.md`

## 实施步骤概要

1. 调整初始化 SQL 中的 Gemini 图片模型定义与映射。
2. 调整升级 SQL，兼容已有数据库的补数与倍率修正。
3. 更新本地数据库中的图片模型与映射数据。
4. 更新前端快速开始中的图片模型示例。
5. 验证本地数据库结果与关键前端文案。
