# PromptCache用户灰度清洗 Plan

## 用户原始需求

代理下级用户缓存命中率不稳定，希望针对 DDD 等用户进行优化，更新服务器后监控效果。

## 技术方案设计

- 保持全局 `anthropic_prompt_cache_control_policy=augment` 不变，避免影响命中正常的用户。
- 新增灰度配置：
  - `anthropic_prompt_cache_normalize_user_ids`：命中用户 ID 后强制使用 `normalize`。
  - `anthropic_prompt_cache_normalize_agent_ids`：命中代理 ID 后强制使用 `normalize`。
- `normalize` 行为复用现有实现：移除用户自带 `cache_control`，只注入系统选择的稳定断点。
- 增加元数据字段，方便日志观察策略来源。

## 涉及文件

- `backend/app/services/anthropic_prompt_cache_service.py`
- `backend/app/services/proxy_service.py`
- `backend/sql/init.sql`
- `backend/sql/initData.sql`
- `backend/sql/upgrade_prompt_cache_normalize_scope_20260611.sql`
- `backend/test_anthropic_prompt_cache_policy.py`
- `frontend/src/views/admin/SystemConfig.vue`

## 实施步骤概要

1. 为 Anthropic prompt cache variant 构建方法增加 user/agent 上下文参数。
2. 增加配置解析和策略覆盖逻辑。
3. 调用处传入当前 `user_id`、`agent_id`。
4. 管理端系统配置页增加灰度配置输入项。
5. 补充 SQL 和单元测试。
6. 本地验证、提交、推送并部署服务器。
