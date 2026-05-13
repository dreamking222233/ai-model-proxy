# Grok Channel 实施记录

## 任务概述

为当前系统接入 Grok 文本渠道，支持以下统一模型：

- `grok-4.20-0309-non-reasoning`
- `grok-4.20-0309`
- `grok-4.20-0309-reasoning`
- `grok-4.20-fast`
- `grok-4.20-auto`
- `grok-4.20-expert`

并实现：

- `/v1/messages` 优先走 Anthropic Grok 渠道
- `/v1/chat/completions` 优先走 OpenAI Grok 渠道
- `/v1/responses` 优先走 OpenAI Grok 渠道
- 上游 `429 / 5xx / 连接失败 / 超时` 的同渠道非流式重试
- OpenAI Chat 空 `content` 时对 `reasoning_content` 的回填兼容

## 文件变更清单

- `md/plan-grok-channel-20260422.md`
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_proxy_model_alias_rewrite.py`
- `backend/sql/init.sql`
- `sql/init.sql`
- `backend/sql/upgrade_grok_channel_20260422.sql`
- `sql/upgrade_grok_channel_20260422.sql`

## 核心实现说明

### 1. 协议优先路由

在 `ProxyService` 中新增 `_prioritize_channels_for_request()`：

- OpenAI Chat 请求优先选择 `protocol_type=openai`
- Anthropic Messages 请求优先选择 `protocol_type=anthropic`
- Responses 请求优先选择 `responses:` 映射或 `protocol_type=openai`

这样在同一模型同时映射 OpenAI / Anthropic 双渠道时，当前请求会优先命中同协议上游，但仍保留跨协议回退能力。

### 2. Grok 非流式重试

新增 `_post_with_retries()`、`_should_retry_upstream_status()`、`_should_retry_upstream_exception()`：

- 默认 3 次尝试
- 对以下情况重试：
  - `408/409/425/429/500/502/503/504`
  - `httpx.TimeoutException`
  - `httpx.ConnectError`
  - `httpx.ReadError`
  - `httpx.RemoteProtocolError`
  - `httpx.NetworkError`
- 采用短退避：`0.6s * attempt`

已接入的非流式链路：

- OpenAI Chat
- Responses
- Anthropic
- Anthropic via Responses bridge

### 3. OpenAI Chat 空 content 兼容

新增 `_normalize_openai_chat_response_payload()` 与 `_extract_openai_text_content()`：

- 当 `choices[*].message.content` 为空时
- 若存在 `reasoning_content` / `reasoning` / `text`
- 自动回填到 `message.content`

同时增强 `_parse_sse_to_non_stream_openai()`：

- 非流式 SSE 还原时同时采集 `delta.content`
- 也采集 `delta.reasoning_content`
- 当正文为空时使用 `reasoning_content` 回填

### 4. 数据库与初始化脚本

新增 2 条 Grok 渠道：

- `Grok OpenAI`
- `Grok Anthropic`

共同特征：

- `base_url = http://167.88.186.145:8000/v1`
- `auth_header_type = authorization`
- `health_check_enabled = 0`

为 6 个 Grok 模型建立了双映射：

- 每个模型映射到 `Grok OpenAI`
- 每个模型映射到 `Grok Anthropic`

当前价格已更新为“官方价格 + 合理推断”：

- `grok-4.20-0309-non-reasoning`: `2.00 / 6.00`
- `grok-4.20-0309`: `2.00 / 6.00`
- `grok-4.20-0309-reasoning`: `2.00 / 6.00`
- `grok-4.20-fast`: `0.20 / 0.50`
- `grok-4.20-auto`: `2.00 / 6.00`
- `grok-4.20-expert`: `2.00 / 6.00`

说明：

- `0309 reasoning/non-reasoning` 使用用户提供的 xAI 官方价格片段。
- `fast` 参考 xAI 官方 `grok-4-1-fast-*` 快速档做近似定价。
- `auto/expert` 暂按 4.20 主档处理，属于推断价格，后续如拿到官方逐项价格应再修正。

## 本地数据库更新结果

已写入本地 `modelinvoke`：

- 渠道：
  - `id=15` `Grok OpenAI`
  - `id=16` `Grok Anthropic`
- 模型：
  - `id=33..38` 共 6 个 `grok-*` 模型
- 映射：
  - `Grok OpenAI` 6 条
  - `Grok Anthropic` 6 条

## 测试验证

已完成：

- `python -m py_compile backend/app/services/proxy_service.py backend/app/test/test_proxy_model_alias_rewrite.py`
- `PYTHONPATH=backend python -m unittest backend.app.test.test_proxy_model_alias_rewrite`
- 本地 MySQL 查询确认 Grok 渠道、模型、映射已落库

测试结果：

- 单测 `7` 项通过
- Redis 在测试环境不可连，但本次单测不依赖 Redis，未影响结果

## 待优化项

- 当前“同渠道重试”只覆盖非流式请求，流式请求仍主要依赖多渠道 failover。
- Grok 上游当前存在端口不稳定现象，建议后续增加按渠道可配置的重试次数与退避策略。
- `auto/expert/fast` 仍属于推断定价，后续如拿到 xAI 官方逐项价格，应覆盖更新。
