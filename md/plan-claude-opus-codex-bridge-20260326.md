# Claude Opus Codex Bridge Plan

## 用户原始需求

当前系统已有 `43.156.153.12-codex` 渠道，该渠道只支持通过 `/v1/responses` 调用 Codex / GPT-5 系列模型，主要用于 Codex CLI。

现在需要新增一个可通过 Anthropic `/v1/messages` 接口访问的模型别名：

- 对外模型名：`claude-opus-4-6`
- 实际上游渠道：`43.156.153.12-codex`
- 实际上游模型：`gpt-5.4`
- 固定推理强度：`reasoning.effort=high`
- 目标客户端：Claude Code

## 技术方案设计

### 1. 新增映射级别的上游 API 选择能力

当前 `model_channel_mapping.actual_model_name` 只表达“实际上游模型名”，无法表达“这条映射应走 `/chat/completions` 还是 `/responses`”。

本次采用轻量方案：

- 约定 `actual_model_name` 支持 `responses:` 前缀
- 例如：`responses:gpt-5.4`
- 代理层在读取映射后，拆出：
  - `upstream_api = responses`
  - `upstream_model_name = gpt-5.4`

优点：

- 不改数据库表结构
- 不影响现有普通 OpenAI / Anthropic 渠道
- API 选择粒度下沉到模型映射，而不是整个渠道

### 2. 补齐 Anthropic -> Responses 协议桥接

当前系统已支持：

- OpenAI `/v1/chat/completions` -> Anthropic `/messages`
- OpenAI `/v1/responses` -> OpenAI `/responses`

但尚未支持：

- Anthropic `/v1/messages` -> OpenAI `/responses`

本次新增一组桥接逻辑：

- Anthropic 请求转 Responses 请求
- Responses 非流式响应转 Anthropic message JSON
- Responses 流式事件转 Anthropic SSE 事件

### 3. `claude-opus-4-6` 别名模型策略

为避免影响现有 `claude-sonnet-*` 模型逻辑，本次直接新增独立统一模型：

- 统一模型名：`claude-opus-4-6`
- 显示名：`Claude Opus 4.6`
- 渠道映射：
  - channel: `43.156.153.12-codex`
  - actual_model_name: `responses:gpt-5.4`

在 Anthropic -> Responses 转换阶段，如果用户请求模型为 `claude-opus-4-6`，则固定附加：

- `reasoning: { "effort": "high", "summary": "auto" }`

这样可以：

- 让 Claude Code 继续按 Anthropic 协议调用
- 上游实际落到 GPT-5.4 Responses
- 尽量保留 reasoning 输出能力

### 4. 工具调用兼容策略

Claude Code 依赖工具调用，因此桥接必须覆盖：

- Anthropic `tools` -> Responses `tools`
- assistant `tool_use` -> `function_call`
- user `tool_result` -> `function_call_output`
- Responses `function_call` -> Anthropic `tool_use`

本次不新增额外业务语义，只做协议层等价映射。

### 5. 健康检查兼容

当前健康检查对 `protocol_type=openai` 渠道固定请求 `/chat/completions`。

本次需要让健康检查也识别 `responses:` 映射：

- 若映射声明为 `responses:gpt-5.4`
- 则健康检查走 `/responses`

避免新增映射后被误判为不健康。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `sql/init.sql`
- `sql/add_codex_channel.sql`
- `md/plan-claude-opus-codex-bridge-20260326.md`
- `md/impl-claude-opus-codex-bridge-20260326.md`

如需独立增量 SQL，再新增：

- `sql/add_claude_opus_codex_bridge_20260326.sql`

## 实施步骤概要

1. 在代理层增加模型映射目标解析能力，支持 `responses:` 前缀。
2. 在 `handle_openai_request` / `handle_anthropic_request` 中按映射目标决定实际调用 `/chat/completions`、`/messages` 或 `/responses`。
3. 新增 Anthropic -> Responses 的请求转换与响应回写逻辑。
4. 为 `claude-opus-4-6` 注入固定 `reasoning.effort=high`。
5. 更新健康检查逻辑，支持 `responses:` 映射。
6. 增加 SQL，写入 `claude-opus-4-6 -> responses:gpt-5.4 -> 43.156.153.12-codex` 映射。
7. 运行语法检查与最小回归验证。
