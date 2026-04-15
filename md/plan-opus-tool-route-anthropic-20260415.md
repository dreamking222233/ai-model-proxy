# Opus Tool Route To Anthropic Plan

日期：2026-04-15

## 用户原始需求

希望对 `claude-opus-4-6` 的工具调用类请求，不再优先桥接到 `gpt-5.4 / responses`，而是优先转发给真实 Anthropic 协议的模型，例如 `claude-sonnet-4-5`，以降低 bridge 场景下的工具/子代理不稳定问题。

## 技术方案设计

### 现状

- `claude-opus-4-6` 当前只映射到 `responses:gpt-5.4`
- Claude Code 走的是 `POST /v1/messages`
- 该路径会进入 `handle_anthropic_request(...)`
- 请求中如带大量工具定义，则 bridge 容易产生多 `Agent/Task*` 工具，进而放大客户端 worktree 风险

### 修复策略

在 Anthropic 请求入口增加“工具请求优先改路由”：

1. 若用户请求模型为 `claude-opus-4-6`
2. 且请求体中存在工具定义 `tools`
3. 则优先尝试将渠道集合切换到 `claude-sonnet-4-5`
4. 并且仅选取真实 Anthropic passthrough 渠道
5. 若未找到可用 Anthropic 渠道，再回退到原来的 `gpt-5.4 / responses` bridge

### 保留策略

- 保留之前已做的 `parallel_tool_calls=false` 缓解逻辑
- 该逻辑继续作为 fallback bridge 的防护层

### 风险与权衡

- 用户请求的名义模型仍是 `claude-opus-4-6`
- 实际工具请求会转发到 `claude-sonnet-4-5`
- 这属于“语义兼容优先、稳定性优先”的策略，不是严格等价模型执行

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `md/plan-opus-tool-route-anthropic-20260415.md`
- `md/impl-opus-tool-route-anthropic-20260415.md`

## 实施步骤概要

1. 在 `ProxyService` 中增加工具请求路由映射与 Anthropic passthrough 渠道筛选逻辑。
2. 在 `handle_anthropic_request(...)` 中，对 `claude-opus-4-6` 的工具请求优先切换到 `claude-sonnet-4-5` 的真实 Anthropic 渠道。
3. 添加清晰日志，记录是否命中该路由策略。
4. 保持原有 bridge 作为 fallback。
5. 执行静态校验并记录实施结果。
