**Findings**
1. Medium: 工具历史转换对并行工具调用不是无损的。`assistant.tool_calls` 会被拆成多个连续的 `assistant.function_call`，而 `tool` 消息只按 `tool_call_id -> function.name` 回填名称，随后就丢失了调用 ID 语义；这对“同一轮多个调用”、“同名函数重复调用”或“结果顺序和调用顺序不一致”的 transcript 会变得含糊，存在继续把 Kiro/AmazonQ 历史喂错的风险。[proxy_service.py#L139](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L139) [proxy_service.py#L157](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L157) [proxy_service.py#L175](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L175)

2. Medium: 渠道识别对关键词分支仍有误伤空间。`_is_kiro_amazonq_channel()` 只在 `43.156.153.12` 分支上加了 `model.startswith("claude")` 限制，但只要 `name/base_url/description` 含 `kiro` 或 `amazonq`，就会无条件触发改写；这和实施文档里“避免误伤同机上的 GPT/Codex 渠道”的表述并不完全一致。当前库里的已知 Codex 渠道配置是安全的，但实现本身没有把这个约束固化下来。[proxy_service.py#L79](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L79) [proxy_service.py#L83](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L83) [impl-kiro-amazonq-compat-20260321.md#L35](/Volumes/project/modelInvocationSystem/md/impl-kiro-amazonq-compat-20260321.md#L35) [add_codex_channel.sql#L7](/Volumes/project/modelInvocationSystem/sql/add_codex_channel.sql#L7)

**Assessment**
- 对焦点 1：当前 `43.156.153.12-Claude` 的 OpenAI `chat/completions` 路径，兼容改写已经挂在实际转发前，且流式/非流式共用同一入口，所以“单次 `assistant.tool_calls + tool` 导致 AmazonQ improperly formed request” 这个当前问题，代码上看大概率已经覆盖到了。[proxy_service.py#L1054](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L1054) [init.sql#L373](/Volumes/project/modelInvocationSystem/sql/init.sql#L373) [impl-kiro-amazonq-compat-20260321.md#L85](/Volumes/project/modelInvocationSystem/md/impl-kiro-amazonq-compat-20260321.md#L85)
- 对焦点 2：对“当前已知同机 Codex/GPT 渠道”风险不高，因为现有配置没有命中关键词分支，且 host 分支做了 Claude 限制；但对未来带 `kiro/amazonq` 标识的非 Claude 渠道，仍有误伤风险。
- 对焦点 3：当前确实补了 `assistant.tool_calls`、`tool`、`function` 内容字符串化这几块，但并行/重复工具调用、孤儿 `tool` 消息这些边界还没被完整覆盖。

**建议**
- 把 Kiro/AmazonQ 识别改成显式渠道能力配置，或者至少让关键词分支也加上 Claude-family 限制。
- 对多工具调用历史，要么按 `tool_call_id` 做更严格的重排/配对，要么在 Kiro/AmazonQ 渠道上显式禁用并行工具调用，避免生成含糊的 legacy transcript。
- 补最少量回归测试：单工具、并行双工具、同名函数双调用、缺失前序 `assistant.tool_calls` 的 `tool` 消息、非 Kiro 渠道透传不改写。

如果只问“这版能不能先解决当前 43.156 Claude 的 Improperly formed request”，我的判断是“基本可以”；如果问“是否已经把 Kiro/AmazonQ 工具历史兼容做完整了”，结论是“还没有完全收口”。
