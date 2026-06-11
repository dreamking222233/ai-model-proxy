# 首尔Claude缓存路由优化 Impl

## 任务概述

优化 Anthropic 协议渠道的模型映射解析。当代理模型映射到 `gpt-*` / `o*` / `codex*` 等 OpenAI Responses 类上游模型时，即使后台没有显式添加 `responses:` 前缀，也自动通过 Responses 桥接请求上游，避免误走 Anthropic messages 透传导致缓存命中异常。

## 文件变更清单

- `backend/app/services/proxy_service.py`
  - 新增 `_looks_like_responses_upstream_model`。
  - `_resolve_mapped_upstream_target` 增加 Anthropic 渠道下 GPT/Codex 类模型自动走 `responses` 的逻辑。
  - 映射值解析增加首尾空格清理和 `responses:` 前缀大小写兼容。
  - OpenAI chat 入口通过 `auto_responses_for_anthropic=False` 保持旧行为，避免 `/v1/chat/completions` 被自动切到 Responses。
  - `_is_responses_reasoning_model` 复用 `_looks_like_responses_upstream_model`，避免 reasoning 与路由识别规则不一致。
- `backend/test_proxy_retry_error_sanitization.py`
  - 增加 Anthropic 渠道 GPT 映射自动走 Responses 的测试。
  - 增加 Codex / O 系列 / 命名空间 GPT 映射自动走 Responses 的测试。
  - 增加显式 `responses:` 兼容测试。
  - 增加 Claude 模型继续走 Anthropic messages 的测试。
  - 增加 OpenAI 渠道默认行为不变的测试。
  - 增加 OpenAI chat 入口关闭 Anthropic 自动 Responses 映射的测试。

## 核心代码说明

本次优化只改变 `_resolve_mapped_upstream_target` 的协议选择结果：

- `protocol_type=anthropic` 且 `actual_model_name=gpt-5.5`：返回 `("gpt-5.5", "responses")`。
- `protocol_type=anthropic` 且 `actual_model_name=responses:gpt-5.5`：返回 `("gpt-5.5", "responses")`。
- `protocol_type=anthropic` 且 `actual_model_name=claude-opus-4-8`：仍返回 `("claude-opus-4-8", "anthropic_messages")`。
- `protocol_type=openai` 且 `actual_model_name=gpt-5.5`：仍使用调用方默认 API，不改变 OpenAI 聊天入口行为。
- OpenAI chat 入口调用解析时显式关闭 Anthropic 自动 Responses 映射，防止旧的 chat-completions 转 Anthropic messages 路径被误切换。

## 测试验证

已执行：

```bash
env PYTHONPATH=backend python -m py_compile backend/app/services/proxy_service.py backend/test_proxy_retry_error_sanitization.py
env PYTHONPATH=backend python -m unittest backend/test_proxy_retry_error_sanitization.py
```

结果：33 个测试通过。

## 自审迭代

自审提出两点建议：

1. Responses 路由识别规则与 reasoning 判断不一致。
2. 测试未覆盖 Codex / O 系列映射。

已处理：

- `_is_responses_reasoning_model` 改为复用 `_looks_like_responses_upstream_model`。
- 补充 Codex / O 系列 / 命名空间 GPT 的测试。
- 增加 `auto_responses_for_anthropic` 开关，确保 OpenAI chat 入口不受自动桥接影响。

## 待观察项

上线后重点观察 `claude-opus-4-8 -> gpt-5.5` 这类映射的请求日志，确认 `upstream_api=responses`，并对比首尔/zz1 渠道的 `cache_read_input_tokens` 和 `cache_creation_input_tokens` 是否改善。
