**Findings**
1. High: OpenAI 非流式请求命中 Anthropic 渠道时，如果上游在 `stream=false` 下仍返回 SSE，当前回拼会丢掉 `thinking` 和 `tool_use`，只保留文本；工具调用场景下最终可能出现 `finish_reason="tool_calls"` 但 `message.tool_calls` 为空，客户端无法继续执行。问题点在 [_non_stream_openai_via_anthropic_request](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L2740)、[_parse_sse_to_non_stream_anthropic](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L3228)、[_convert_anthropic_response_to_openai](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L715)。我本地用最小 SSE 样例复现后，`tool_use` 被回拼成空 `content`。
2. Medium: OpenAI -> Anthropic 转换静默丢弃了 `response_format`，所以之前依赖 `json_schema/json mode` 的 OpenAI 客户端，请求落到 `protocol_type="anthropic"` 渠道后会失去输出格式约束，而且代码没有显式报错。问题点在 [_convert_openai_request_to_anthropic](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L576)。这和方案里“不影响现有客户端调用我方 OpenAI 接口的兼容性”不一致。方案文档是 [plan-claude-upstream-api-20260324.md](/Volumes/project/modelInvocationSystem/md/plan-claude-upstream-api-20260324.md)，实施文档是 [impl-claude-upstream-api-20260324.md](/Volumes/project/modelInvocationSystem/md/impl-claude-upstream-api-20260324.md)。

**优化建议**
- 先补齐 Anthropic SSE -> 非流式响应的完整回拼，至少覆盖 `thinking`、`tool_use`、`partial_json/input_json_delta`。
- 对暂不支持的 OpenAI 字段不要静默忽略，优先显式返回 `400 UPSTREAM_INVALID_REQUEST`，避免客户端拿到“成功但格式不对”的结果。
- 给这条新链路补最小自动化测试：`OpenAI non-stream + Anthropic SSE fallback + tool_use/thinking`。

**验证**
- 本地执行了 `PYTHONPATH=backend python -m py_compile backend/app/services/proxy_service.py`，通过。
- 做了两组最小复现脚本，确认了上面两个问题。

审查结论已写入 [review-claude-upstream-api-20260324.md](/Volumes/project/modelInvocationSystem/md/review-claude-upstream-api-20260324.md)。
