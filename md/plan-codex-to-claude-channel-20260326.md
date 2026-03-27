# Codex To Claude Channel Plan

## 用户原始需求

当前系统已经有：

- `43.156.153.12-Claude`：`Anthropic` 协议渠道，直接走上游 `/v1/messages`
- `43.156.153.12-codex`：`OpenAI` 协议渠道，主要走上游 `/v1/responses`

现在需要新增一个独立渠道：

- 渠道名：`43.156.153.12-codex转claude`
- 对外协议：`Anthropic`
- 目标客户端：Claude Code
- 对外模型名：`claude-opus-4-6`
- 实际上游模型：`gpt-5.4`
- 实际上游地址：`43.156.153.12-codex`

同时要求：

- `claude-opus-4-6` 不再直接挂在 `43.156.153.12-codex`
- 从 Claude Code 角度要表现为可正常使用的 Anthropic 模型
- 实际上游仍然命中 `gpt-5.4`

## 技术方案设计

### 1. 当前 `43.156.153.12-Claude` 的工作方式

当前系统对渠道协议的判断核心在 `channel.protocol_type`：

- `protocol_type = anthropic`
  - Anthropic 入口默认走 `/messages`
  - OpenAI 入口会先转成 Anthropic 请求，再走 `/messages`
- `protocol_type = openai`
  - OpenAI 入口默认走 `/chat/completions`
  - Responses 映射会显式走 `/responses`

因此 `43.156.153.12-Claude` 的本质是：

- 渠道元数据声明为 Anthropic
- 代理层据此构造 Anthropic header 和 `/messages` 请求

### 2. 新渠道设计

本次不改数据库表结构，继续复用已有的映射指令能力：

- `actual_model_name = responses:gpt-5.4`

这样可以表达：

- 对外：该模型从 Anthropic `/v1/messages` 进入
- 对内：该映射实际走 OpenAI `/v1/responses`

新渠道的配置设计为：

- `name = 43.156.153.12-codex转claude`
- `base_url = http://43.156.153.12:8317/v1`
- `protocol_type = anthropic`

路由决策依旧由：

- `channel.protocol_type = anthropic`
- `actual_model_name = responses:gpt-5.4`

共同决定：

- 入口保留 Anthropic 语义
- 实际上游改走 Responses

### 3. `claude-opus-4-6` 的映射调整

将 `claude-opus-4-6` 改为：

- 统一模型协议：`anthropic`
- 唯一主映射渠道：`43.156.153.12-codex转claude`
- 实际模型：`responses:gpt-5.4`

旧的：

- `claude-opus-4-6 -> 43.156.153.12-codex`

需要关闭，避免同一模型同时落到两个不同语义渠道。

### 4. Claude Code 兼容性补强

仅新增渠道还不够。Claude Code 对 Anthropic tools streaming 比较严格，当前桥接仍有兼容风险：

- `function_call` 需要按 Anthropic `tool_use` block 流式回放
- `response.function_call_arguments.delta` 需要转换为 `input_json_delta`

本次补齐：

- `Responses function_call` 的流式 block 生命周期
- `function_call_arguments.delta/done` 到 `input_json_delta`
- 对最终补齐分支做去重，避免重复发 tool block

### 5. 健康检查兼容

新渠道是：

- 渠道协议：Anthropic
- 实际上游 API：Responses

因此健康检查不能只按 `channel.protocol_type` 选 header 语义，需要按实际目标 API 决定。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `sql/init.sql`
- `sql/add_codex_channel.sql`
- `sql/add_codex_to_claude_channel_20260326.sql`
- `md/plan-codex-to-claude-channel-20260326.md`
- `md/impl-codex-to-claude-channel-20260326.md`
- `md/review-codex-to-claude-channel-20260326.md`

## 实施步骤概要

1. 梳理当前 `43.156.153.12-Claude` 与 `43.156.153.12-codex` 的协议分流逻辑。
2. 为 Claude Code 补齐 Anthropic tools streaming -> Responses 桥接缺口。
3. 调整健康检查逻辑，兼容 Anthropic-facing / Responses-backed 渠道。
4. 在 `sql/init.sql` 中新增 `43.156.153.12-codex转claude` 渠道并重挂 `claude-opus-4-6`。
5. 新增增量 SQL，把已有数据库中的 `claude-opus-4-6` 从旧渠道迁移到新渠道。
6. 运行语法检查与最小协议级验证。
