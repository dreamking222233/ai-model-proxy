# Kiro AmazonQ Compatibility Plan

## 用户原始需求

- 阅读线上环境的 Claude Code 对话记录，参考线上修复更新本地代码
- 解决通过 Claude Code 调用本系统 API 时，因上下文过大或参数不兼容导致的错误：
  - `API Error: 503 All channels failed: Upstream returned HTTP 500: {"error":{"message":"HTTP 400 from AmazonQ: {\"message\":\"Improperly formed request.\",\"reason\":null}","type":"api_error"},"type":"error"}`
  - `Upstream returned HTTP 500: {"error":{"message":"HTTP 400 from AmazonQ: {\"message\":\"Improperly formed request.\",\"reason\":null}","type":"api_error"},"type":"error"}`

## 技术方案设计

### 1. 同步线上已确认有效的兼容修复

- 在 Anthropic `/v1/messages` 转发链路中，针对 Kiro/AmazonQ 渠道过滤不支持的顶层字段：
  - `thinking`
  - `context_management`
  - `output_config`
  - `metadata`
  - `betas`
- 对 `anthropic-beta` 透传请求头做渠道级拦截，避免 Kiro/AmazonQ 返回 `invalid beta flag`

### 2. 增强 Anthropic 请求体兼容性

- 清洗消息内容中的 `thinking` / `redacted_thinking` block
- 对嵌套 `tool_result` 内容递归清洗，避免带入签名或思维块
- 不对超大历史消息做服务端静默裁剪；若上游因上下文过大拒绝请求，直接将上游错误返回给用户

### 3. 修正错误归类

- 当前实现会把上游 400 类请求错误计入渠道失败，并最终包装成 503
- 调整为：
  - 请求参数问题 / 上下文过大：返回 400
  - 不计入渠道熔断失败
  - 所有渠道都因请求格式不兼容失败时，优先返回可读的 400 错误

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `md/plan-kiro-amazonq-compatibility-20260321.md`
- `md/impl-kiro-amazonq-compatibility-20260321.md`

## 实施步骤概要

1. 读取线上对话，提取线上已确认的问题根因和修复点
2. 在 `proxy_service.py` 中抽出 Anthropic/Kiro 请求预处理逻辑
3. 实现顶层字段过滤、thinking block 清洗、上下文裁剪
4. 实现上游 4xx 请求错误识别与 400 映射，避免误报 503
5. 进行语法检查和定向代码检查
6. 编写 `impl` 文档并执行一次 Codex CLI review
