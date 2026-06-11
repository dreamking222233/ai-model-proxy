# 首尔Claude缓存路由优化 Plan

## 用户原始需求

用户反馈 `首尔-claude` / `zz1-claude` 等 Claude 渠道在部分代理用户请求中缓存命中率很差，要求先进行优化。

## 技术方案设计

当前 Anthropic 协议入口在解析模型映射时，仅当映射值显式写成 `responses:gpt-5.5` 才会走 Responses 桥接；如果映射为 `gpt-5.5`，会默认走 `anthropic_messages` 透传。实际日志显示 `claude-opus-4-8 -> gpt-5.5` 时，上游 API 被解析为 `anthropic_messages`，导致缓存读取几乎为 0。

优化方案：

1. 保留显式 `responses:` 前缀优先级。
2. 对 Anthropic 协议渠道，如果实际映射模型明显是 GPT / Codex / OpenAI Responses 类模型，则自动选择 `responses` 桥接。
3. 对真实 Claude / Anthropic 模型继续走 `anthropic_messages`。
4. 不修改 OpenAI 协议入口现有行为，避免影响 `/v1/chat/completions`。
5. 增加单元测试覆盖自动路由、显式路由和 Claude 透传。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/test_proxy_retry_error_sanitization.py`
- `md/plan-首尔Claude缓存路由优化-20260611.md`
- `md/impl-首尔Claude缓存路由优化-20260611.md`
- `md/review-首尔Claude缓存路由优化-20260611.md`

## 实施步骤概要

1. 增加 Responses 类上游模型的启发式判断方法。
2. 修改 `_resolve_mapped_upstream_target` 的 Anthropic 渠道分支。
3. 增加单元测试。
4. 运行语法检查和相关测试。
5. 记录实施结果并进行自审。
