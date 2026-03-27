# Codex To Claude Channel Review

## Findings

- High: `sql/add_codex_channel.sql` 现在会新增 `43.156.153.12-codex转claude -> claude-opus-4-6` 映射，但不会关闭旧的 `claude-opus-4-6 -> 43.156.153.12-codex` 映射。如果有人在已有旧映射的库上执行这份脚本，`claude-opus-4-6` 会同时挂在旧 codex 渠道和新 bridge 渠道上，和方案里“旧映射必须关闭”的要求不一致，而且两个渠道优先级同为 `1`，最终命中顺序会退化成数据库返回顺序。见 [plan-codex-to-claude-channel-20260326.md](/Volumes/project/modelInvocationSystem/md/plan-codex-to-claude-channel-20260326.md#L78) [add_codex_channel.sql](/Volumes/project/modelInvocationSystem/sql/add_codex_channel.sql#L97) [model_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/model_service.py#L462) [model_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/model_service.py#L499)。

- Medium: 实施记录写的是“增量 SQL 自动复制旧 codex 渠道的 `api_key` 和 `base_url`”，但这和实际执行的 `sql/add_codex_to_claude_channel_20260326.sql` 不一致。当前脚本只从旧渠道复制了 `api_key`，`base_url` 仍然被硬编码成 `http://43.156.153.12:8317/v1`。如果现网 `43.156.153.12-codex` 的真实 `base_url` 不是这个固定值，bridge 渠道就不会真正复用旧渠道路由。见 [impl-codex-to-claude-channel-20260326.md](/Volumes/project/modelInvocationSystem/md/impl-codex-to-claude-channel-20260326.md#L45) [impl-codex-to-claude-channel-20260326.md](/Volumes/project/modelInvocationSystem/md/impl-codex-to-claude-channel-20260326.md#L83) [add_codex_to_claude_channel_20260326.sql](/Volumes/project/modelInvocationSystem/sql/add_codex_to_claude_channel_20260326.sql#L20) [add_codex_to_claude_channel_20260326.sql](/Volumes/project/modelInvocationSystem/sql/add_codex_to_claude_channel_20260326.sql#L42)。

- Medium: Claude Code 需要的 `tool_use` / `input_json_delta` 主干已经补上了，但 Anthropic `thinking` 协议仍然不是完整等价实现。当前流式桥接只会发 `thinking_delta`，不会发 `signature_delta`；非流式响应里也只返回 `{"type":"thinking","thinking":"..."}`，没有 signature 字段。若后续客户端或 SDK 开始严格依赖 Anthropic thinking signature，这里仍有兼容风险。见 [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L3975) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L1604) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L1619)。

## Assessment

主链路基本符合方案：

- 新渠道 `43.156.153.12-codex转claude` 在代码层确实按 `Anthropic entry + responses:gpt-5.4 upstream` 分流。
- `claude-opus-4-6` 在 `init.sql` 和专用迁移脚本里都被切成 `protocol_type = anthropic`，并指向 `responses:gpt-5.4`。
- `Responses -> Anthropic` 的工具流式桥接已经补到了 `response.output_item.added`、`response.function_call_arguments.delta/done`、`input_json_delta` 和去重收口，健康检查也会按实际上游 API 选 `/responses` 和 OpenAI 风格 header。

对应代码见 [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L844) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L2963) [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py#L3850) [health_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py#L38) [health_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py#L202)。

所以结论是：

- 如果按实施记录那样只执行 `sql/add_codex_to_claude_channel_20260326.sql`，当前“新渠道 43.156.153.12-codex转claude + claude-opus-4-6 切换 + Claude Code tools streaming 主链路”基本成立。
- 但 SQL 资产整体还不够收敛，`sql/add_codex_channel.sql` 和实施记录之间仍有偏差；此外 Anthropic thinking signature 还没补齐，所以不能算 100% Anthropic 协议等价。

## 建议

- 收敛增量 SQL，只保留一份最终脚本作为唯一入口；至少让 `sql/add_codex_channel.sql` 也显式禁用旧的 `claude-opus-4-6 -> 43.156.153.12-codex` 映射，避免双挂。
- 把 `sql/add_codex_to_claude_channel_20260326.sql` 里的 `base_url` 改成真正从旧 codex 渠道复制，或者直接在文档里说明这是固定值，不再宣称“自动复制 base_url”。
- 给 bridge 链路补一组自动化回归：单 tool、多 tool、tool_result 续轮、reasoning/thinking 混合输出；其中至少断言 `content_block_start -> input_json_delta -> content_block_stop -> message_delta(tool_use)` 的事件序列。
- 如果后续要追求 Claude Code / Anthropic SDK 的更强兼容性，再补 `thinking` 的 `signature_delta` / signature 字段；如果短期不做，建议在文档中明确标注这是已知兼容边界。
