# 首尔Claude缓存路由优化 Review

## Findings

- 中：`_looks_like_responses_upstream_model` 的启发式比方案/实施说明更窄。实施记录写的是支持 `gpt-* / o* / codex*`，但代码只识别 `gpt-`、`gpt_`、`o1`、`o3`、`o4`、`codex`、`openai/`。这会让未来扩展的 `o*` 模型或带命名空间的 GPT/Codex 映射继续落到 `anthropic_messages`。同文件里的 `_is_responses_reasoning_model` 使用了更宽的 GPT/Codex 识别规则，两者存在内部不一致。
- 低：新增测试覆盖了 `gpt-*`、显式 `responses:` 和 Claude 透传，但没有覆盖 `o*` / `codex*` 映射，也没有覆盖实际 Anthropic 分发桥接路径。

## Notes

针对 `claude-opus-4-8 -> gpt-5.5` 的目标没有发现阻塞性问题；语法检查和 `backend/test_proxy_retry_error_sanitization.py` 通过。

## 建议

1. 将 Responses 路由识别规则统一成单一来源，至少与 `_is_responses_reasoning_model` 保持一致。
2. 补充 `o*` / `codex*` 映射测试。
3. 如时间允许，增加 Anthropic 请求分发到 Responses bridge 的端到端单测。

## 处理状态

- 已处理建议 1：`_is_responses_reasoning_model` 复用 `_looks_like_responses_upstream_model`。
- 已处理建议 2：补充 `codex-max`、`openai/codex-mini`、`o4-mini`、`openai/o5-high` 的映射测试。
- 已补充额外保护：OpenAI chat 入口显式关闭 Anthropic 自动 Responses 映射，避免影响 `/v1/chat/completions` 旧路径。
- 建议 3 暂未新增完整端到端分发测试，本次先用解析层测试覆盖核心风险。
