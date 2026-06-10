# PromptCache用户灰度清洗 Impl

## 任务概述

为 Anthropic Prompt Cache 增加按用户/代理灰度的 `normalize` 策略，用于观察 DDD 等用户在移除客户端自带 `cache_control` 后的缓存表现。

## 文件变更清单

- `backend/app/services/anthropic_prompt_cache_service.py`
  - 新增用户/代理 ID 列表配置解析。
  - 新增策略来源 `control_policy_source`。
  - 命中用户/代理灰度配置时覆盖为 `normalize`。
- `backend/app/services/proxy_service.py`
  - Anthropic 流式/非流式请求构建缓存 variant 时传入 `user_id`、`agent_id`。
- `frontend/src/views/admin/SystemConfig.vue`
  - 管理端缓存配置增加清洗用户ID、清洗代理ID输入项。
- `backend/sql/upgrade_prompt_cache_normalize_scope_20260611.sql`
  - 新增灰度配置，生产默认对 `user_id=244` 生效。
- `backend/sql/init.sql`、`backend/sql/initData.sql`
  - 新增初始化配置项，默认空列表。
- `backend/test_anthropic_prompt_cache_policy.py`
  - 补充 user/agent 灰度覆盖测试。

## 核心说明

- 全局默认仍为 `augment`，不影响现有命中正常用户。
- `anthropic_prompt_cache_normalize_user_ids` 命中优先级高于 `anthropic_prompt_cache_normalize_agent_ids`。
- 命中后复用现有 `normalize` 行为：移除客户端自带 `cache_control`，仅保留系统稳定断点。
- 日志详情中新增 `control_policy_source`，便于上线后按 `normalize_user` / `normalize_agent` 观察。

## 测试验证

- `/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest test_anthropic_prompt_cache_policy.py`
- `/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m py_compile app/services/anthropic_prompt_cache_service.py app/services/proxy_service.py`
- `frontend/npm run build`

以上均通过，前端仅存在既有 bundle size warning。
