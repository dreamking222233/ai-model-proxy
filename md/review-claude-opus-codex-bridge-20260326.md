存在 2 个高风险问题，路由分流方向本身是对的，但这版还不能算“Claude Code 工具调用兼容已完成”。

**Findings**
- High: Anthropic `tools` 被转成了 Chat Completions 风格，不是 Responses 原生风格。当前 `_convert_anthropic_tools_to_responses()` 输出的是 `{"type":"function","function":{...}}`，强制工具选择也用了同样的嵌套结构；而 Responses 官方示例是顶层 `name` / `description` / `parameters`。严格一点的 `/v1/responses` 上游会直接拒绝工具声明或 `tool_choice=tool`。见 [proxy_service.py#L946](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L946) [proxy_service.py#L972](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L972)。
- High: `function_call -> tool_use` 的流式回写不符合 Anthropic streaming 协议。当前桥接只在 `response.output_item.done` / `response.completed` 时一次性吐出 `tool_use` block，而且没有 `input_json_delta`，也完全没处理 upstream 的 `response.function_call_arguments.delta`。Anthropic 的 tool streaming 预期是 `content_block_start -> input_json_delta -> content_block_stop`。这对 Claude Code 是实打实的兼容风险。见 [proxy_service.py#L4006](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L4006) [proxy_service.py#L4041](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L4041) [proxy_service.py#L4052](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L4052) [proxy_service.py#L4113](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L4113)。
- Medium: `reasoning/thinking` 转换对真实 Responses 负载不稳，而且会直接影响 `claude-opus-4-6`，因为这个别名固定开启高推理。当前代码把 `reasoning.summary` 数组直接 `str(...)`，我本地复现出来的是 `"[{'type': 'summary_text', ...}]"` 这种 Python 列表字符串；流式 `thinking` 也没有 Anthropic 的 `signature_delta`。请求侧还会把返回的 thinking 重新编码成自造的 `{"type":"reasoning","content":"..."}` item。见 [proxy_service.py#L1063](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L1063) [proxy_service.py#L1577](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L1577) [proxy_service.py#L3924](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L3924)。
- Medium: `claude-opus-4-6` 的新路由没问题，但 SQL 风险范围比“新增一个 alias”更大。增量 SQL 会把整个 `43.156.153.12-codex` 渠道的既有映射都改成 `responses:*`，而 `/v1/chat/completions` 对这类映射现在会直接报错。如果现网还有人拿这批 `gpt-5*` 模型走 chat/completions，会被一起打断。见 [add_claude_opus_codex_bridge_20260326.sql#L42](/Volumes/project/modelInvocationSystem/sql/add_claude_opus_codex_bridge_20260326.sql#L42) [add_codex_channel.sql#L31](/Volumes/project/modelInvocationSystem/sql/add_codex_channel.sql#L31) [proxy_service.py#L2778](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L2778)。

**Assessment**
路由主干基本符合方案：`responses:` 映射解析、Anthropic 入口分流、`claude-opus-4-6 -> gpt-5.4`、以及健康检查切到 `/responses` 都已经落地。见 [proxy_service.py#L844](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L844) [proxy_service.py#L2933](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L2933) [proxy_service.py#L2966](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L2966) [health_service.py#L38](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py#L38)。

`tool_result -> function_call_output` 的请求侧映射本身是对的，主要问题出在：
1. `tools/tool_choice` 进入 Responses 的 schema 不对。
2. `function_call` 从 Responses 回 Anthropic 的流式协议不完整。
3. reasoning/thinking 现在是“能跑样例”，不是“协议等价”。

**建议**
- 先修 `_convert_anthropic_tools_to_responses()`，改成 Responses 原生 tool schema，再补 `tool_choice=auto/any/tool` 的回归用例。
- 流式桥接里接住 `response.function_call_arguments.delta`，按 Anthropic `input_json_delta` 回放；不要等到 `output_item.done` 才一次性拼整块。
- `claude-opus-4-6` 上线前，确认 `43.156.153.12-codex` 是否还承接任何 `/v1/chat/completions` 流量；如果有，建议只给新 alias 用 `responses:`，不要顺手改全量映射。

官方协议参考：
- OpenAI Responses function calling: https://platform.openai.com/docs/guides/function-calling?api-mode=responses
- Anthropic streaming: https://docs.anthropic.com/en/docs/build-with-claude/streaming
