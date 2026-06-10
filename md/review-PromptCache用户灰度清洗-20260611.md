# PromptCache用户灰度清洗 Review

## Findings

1. 高风险：`normalize` 灰度只覆盖首个 prompt-cache 变体，最终 `fallback_no_cache` 仍可能带回用户原始 `cache_control`。  
   已修复：命中 `normalize` 时，`fallback_no_cache` 使用已清洗请求，并记录 `user_cache_control_removed=true`。

2. 中风险：初始化 SQL 默认空列表，升级脚本默认 `244`，如果配置已存在但为空，升级不会生效。  
   已修复：升级脚本在配置存在但为空时也会设置 `anthropic_prompt_cache_normalize_user_ids=244`。

## 补充建议

- 增加 user/agent 同时命中时的优先级测试。  
  已补充：`test_user_scope_has_priority_over_agent_scope`。

## 结论

修复后实现符合需求：全局仍保持 `augment`，生产可先对 `user_id=244` 灰度启用 `normalize`，并通过日志中的 `control_policy_source=normalize_user` 观察效果。
