# Kiro AmazonQ Compatibility Impl

## 任务概述

基于线上环境 `线上环境.txt` 的排障结论，同步本地 `backend/app/services/proxy_service.py`，修复 Claude Code 通过本系统调用 Kiro/AmazonQ 渠道时出现的两类问题：

- 请求参数不兼容导致的 `Improperly formed request`
- 长对话上下文过大时被上游拒绝，但本地误包装为 503

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `md/plan-kiro-amazonq-compatibility-20260321.md`
- `md/impl-kiro-amazonq-compatibility-20260321.md`

## 核心代码说明

### 1. Anthropic/Kiro 请求预处理

新增 Kiro/AmazonQ Anthropic 预处理逻辑：

- 过滤顶层不兼容字段：
  - `thinking`
  - `context_management`
  - `output_config`
  - `metadata`
  - `betas`
- 移除 `anthropic-beta` 请求头，避免触发 `invalid beta flag`
- 清洗历史消息中的 `thinking` / `redacted_thinking` block 和 `signature`

### 2. 大上下文错误处理

最终实现不对请求做本地裁剪。

- 如果请求能通过本地基础长度校验，就按原始上下文转发给上游
- 若上游因上下文过大返回 400/413 或类似错误，直接映射为本地 400 并把上游错误信息返回给用户
- 避免通过静默裁剪降低回答质量

### 3. 错误归类修正

新增上游请求错误映射逻辑：

- 对 `Improperly formed request`
- `invalid beta flag`
- `invalid signature in thinking block`
- 上游 400 / 413 / 422

统一映射为本地 400 错误，尽量保留上游原始错误信息，不再错误包装为 503，也不再计入渠道熔断失败。

### 4. 流式错误处理修正

在 OpenAI / Anthropic / Responses 的流式分支中：

- 对请求类错误返回更可读的错误消息
- 不再把此类错误计为 channel failure
- 保留真实渠道故障的失败统计逻辑

## 测试验证

已完成：

- `python -m py_compile backend/app/services/proxy_service.py`

未完成：

- 未启动完整后端进行端到端验证
- 未连接真实 Kiro/AmazonQ 上游复测长对话与异常参数场景

## 待优化项

- 若后续仍需控制长对话质量，更合适的方向是显式报错或引导客户端做 compact，而不是服务端静默裁剪
