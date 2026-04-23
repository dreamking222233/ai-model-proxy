# 图片编辑原生透传修复实施记录（2026-04-23）

## 任务概述
- 修复当前系统图片编辑请求与上游原生调用不一致的问题。
- 保持多图 `image` 重复字段透传不变。
- 调整 OpenAI 兼容图片编辑场景下的 prompt 处理逻辑，使其更接近上游原生行为。

## 文件变更清单
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_openai_image_channel.py`
- `md/plan-image-edit-native-forward-20260423.md`

## 核心变更

### 1. 图片编辑 prompt 改为原始透传
- 修改 `ProxyService._build_openai_image_edit_prompt()`。
- 变更前：
  - 会基于 `image_size` / `aspect_ratio` 自动拼接额外提示
  - 会自动附加“尽量保留原图主体、构图关系和关键视觉元素”之类的文本
- 变更后：
  - 直接返回调用方原始 `prompt`
  - 不再为图片编辑场景追加尺寸、比例或保留主体类提示

### 2. 多图上传透传保持不变
- 当前系统仍会将所有上传的 `image` 字段继续作为重复 multipart 字段转发给上游 `/v1/images/edits`。
- 本次修复不影响：
  - 多图上传能力
  - `n=1`
  - `response_format=b64_json`
  - 5 分钟超时
  - 计费与日志

## 测试验证
- 命令：
  - `PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m pytest backend/app/test/test_openai_image_channel.py`
- 结果：
  - `12 passed`

## 结果说明
- 当前系统与上游原生图片编辑调用的主要差异点已消除。
- 对于多图编辑场景，请求将继续上传全部参考图，但编辑 prompt 不再被系统二次增强，更接近直接调用上游接口的行为。
