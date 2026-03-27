# Claude Opus Codex Bridge 实施记录

## 任务概述

本次实现新增了一个面向 Claude Code 的桥接模型：

- 对外模型名：`claude-opus-4-6`
- 客户端入口：Anthropic `POST /v1/messages`
- 实际上游渠道：`43.156.153.12-codex`
- 实际上游接口：`POST /v1/responses`
- 实际上游模型：`gpt-5.4`
- 固定推理参数：`reasoning.effort=high`

核心目标是让 Claude Code 可以继续使用 Anthropic 协议，而系统内部把请求转换为 OpenAI Responses 请求发往 Codex 渠道。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `sql/add_codex_channel.sql`
- `sql/add_claude_opus_codex_bridge_20260326.sql`
- `md/plan-claude-opus-codex-bridge-20260326.md`
- `md/impl-claude-opus-codex-bridge-20260326.md`
- `md/review-claude-opus-codex-bridge-20260326.md`

## 核心代码说明

### 1. 新增映射级别的上游 API 选择

在 `proxy_service.py` 中新增 `_resolve_mapped_upstream_target()`：

- 支持把 `actual_model_name` 写成 `responses:gpt-5.4`
- 代理层会拆成：
  - 实际模型名：`gpt-5.4`
  - 上游接口类型：`responses`

这样不需要修改数据库表结构，也避免把整个 `openai` 渠道都切到 `/responses`。

### 2. 补齐 Anthropic -> Responses 请求转换

新增：

- `_build_responses_message_content_parts()`
- `_build_responses_message_item()`
- `_convert_anthropic_tools_to_responses()`
- `_convert_anthropic_request_to_responses()`

实现内容：

- `system` 转成 Responses `developer` message
- `text` / `image` Anthropic block 转成 Responses `message` item
- assistant `tool_use` 转成 `function_call`
- user `tool_result` 转成 `function_call_output`
- Anthropic `tools` / `tool_choice` 转成 Responses `tools` / `tool_choice`
- 当请求模型为 `claude-opus-4-6` 时，固定注入：
  - `reasoning = {"effort": "high", "summary": "auto"}`

### 3. 补齐 Responses -> Anthropic 响应转换

新增：

- `_convert_responses_output_to_anthropic_content()`
- `_convert_responses_response_to_anthropic()`
- `_build_anthropic_sse_event()`
- `_stream_anthropic_via_responses_request()`
- `_non_stream_anthropic_via_responses_request()`

实现内容：

- Responses `message` 输出项转成 Anthropic `text` block
- Responses `function_call` 输出项转成 Anthropic `tool_use` block
- Responses `reasoning` 输出项转成 Anthropic `thinking` block
- 流式时把 `response.output_text.delta` 回放成 Anthropic `content_block_delta`
- 在 `response.completed` 阶段补齐 `message_delta` / `message_stop`

### 4. 更新 Anthropic 入口分流

`handle_anthropic_request()` 现在会根据模型映射目标决定：

- 走原来的 Anthropic `/messages`
- 或走新的 OpenAI `/responses` 桥接链路

这使得 `claude-opus-4-6 -> responses:gpt-5.4` 可以直接从 `POST /v1/messages` 生效。

### 5. 更新健康检查

`health_service.py` 中新增 `_resolve_health_target()`：

- 若映射为 `responses:gpt-5.4`
- 健康检查改走 `/responses`

避免 `43.156.153.12-codex` 这类 Responses-only 映射被误探测为 `/chat/completions`。

### 6. SQL 变更

#### `sql/add_codex_channel.sql`

- 新增 `claude-opus-4-6` 统一模型
- 把 codex 渠道已有映射改成 `responses:*`
- 新增 `claude-opus-4-6 -> responses:gpt-5.4` 映射

#### `sql/add_claude_opus_codex_bridge_20260326.sql`

用于已有数据库的增量升级：

- 新增 `claude-opus-4-6`
- 规范 `43.156.153.12-codex` 的现有映射为 `responses:*`
- 新增 `claude-opus-4-6 -> responses:gpt-5.4`

## 测试验证

已完成：

- `python -m py_compile backend/app/services/proxy_service.py`
- `python -m py_compile backend/app/services/health_service.py`
- 本地最小转换自检：
  - 验证 `responses:gpt-5.4` 可被正确解析
  - 验证 Anthropic request -> Responses request
  - 验证 Responses response -> Anthropic response

验证结果：

- 语法检查通过
- 本地转换断言通过

## 当前限制

- 未直接连接本机 MySQL 校验真实数据库状态；当前环境 `127.0.0.1:3306` 不可达
- 未直接联调真实上游 `http://43.156.153.12:8317/v1/responses`
- `claude-opus-4-6` 这类 `responses:` 映射当前主要面向 Anthropic `/v1/messages` 使用
- 若用户从 `/v1/chat/completions` 调这类映射，系统会返回明确错误，而不是错误地请求 `/chat/completions`

## 待优化项

- 如后续需要，也可以补 OpenAI `/v1/chat/completions` -> `/v1/responses` 的桥接能力
- 可增加后端自动化测试，覆盖：
  - Anthropic tool_use/tool_result -> Responses function_call/function_call_output
  - Responses reasoning item -> Anthropic thinking block
  - Anthropic 流式桥接事件序列
