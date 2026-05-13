# 图片编辑渠道接入 Review（2026-04-23）

## 审查结论
- 当前实现已满足本次需求：
  - 新增图片编辑代理接口 `POST /v1/image/edit`
  - 兼容 OpenAI 风格 `POST /v1/images/edits`
  - `gpt-image-2` 支持图片编辑
  - `n` 固定为 `1`
  - 图片编辑按 `0.5` 图片积分计费
  - `user/chat` / `admin/chat` 支持上传图片后编辑
  - `user/quickstart` 已补充编辑图片调用示例

## 本轮修正项
1. 修正图片编辑入口兼容参数透传
- 编辑接口已同时保留 `image_size`、`imageSize`、`size`、`aspect_ratio`，避免旧客户端参数被误判。

2. 修正 `n` 非法值边界
- 为图片生成与图片编辑统一补充 `n` 参数校验。
- 当客户端传入非法字符串时，现会稳定返回业务 4xx，而不是抛出 Python 转换异常。

3. 前端交互与展示链路补齐
- 聊天页已区分“生成 / 编辑”模式。
- 编辑结果可展示原图预览、结果图和积分消耗。
- 调用方式面板会根据当前模式切换为 JSON 或 multipart 示例。

## 残余风险
1. 原图与结果图预览均为前端运行时缓存
- 刷新页面后，历史消息中的本地图片预览不会恢复，只保留文本消息与结果元数据。

2. 管理端聊天页的渠道选择仍沿用现有行为
- 前端会继续传 `X-Channel-Id`，但后端是否强制命中指定渠道不在本次改动范围内。

3. 上游内容安全策略仍可能拒绝请求
- 当前新增的是接口能力与页面入口，若提示词或上传图片命中上游风控，仍会返回上游错误。

## 验证记录
- 后端：
  - `/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest app.test.test_openai_image_channel app.test.test_image_billing`
  - 14 个测试通过
- 前端：
  - `npm run build`
  - 构建通过，仅有仓库原有 warning

## 备注
- 按规范尝试执行 `codex exec` 自动审查命令时，当前环境因 `/Users/dream/.codex/sessions` 无权限而失败，因此本文件为本轮人工 review 结果。
