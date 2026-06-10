# PromptCache优化 Impl 20260611

## 任务概述

针对用户自带 `cache_control` 时系统完全跳过自动 prompt cache 优化的问题，增加可配置策略，让系统可以在不做响应缓存的前提下，帮助用户更稳定地使用上游 prompt cache。

## 文件变更清单

- `backend/app/services/anthropic_prompt_cache_service.py`
  - 新增 `anthropic_prompt_cache_control_policy` 配置读取。
  - 支持 `preserve`、`augment`、`normalize` 三种策略。
  - `augment` 保留用户断点并在安全位置补充系统断点。
  - `normalize` 移除用户断点后由系统重新注入稳定断点。
  - 记录策略、用户断点数量、是否移除用户断点、是否添加系统断点到 `request_cache_summary.details_json`。
  - 保持现有 prompt cache fallback：上游不接受增强请求时继续尝试后续变体，最终回到原始请求。
- `frontend/src/views/admin/SystemConfig.vue`
  - 在缓存配置区域增加“用户断点策略”下拉项。
  - 保存/读取 `anthropic_prompt_cache_control_policy`。
- `backend/sql/upgrade_prompt_cache_control_policy_20260611.sql`
  - 增加线上增量配置，新环境默认设置为 `augment`。
  - 重复执行时只更新类型和描述，不覆盖已手动回退的配置值。
- `backend/sql/init.sql`
  - 新初始化环境增加配置项。
- `backend/sql/initData.sql`
  - 新初始化数据增加配置项。
- `backend/test_anthropic_prompt_cache_policy.py`
  - 增加 preserve/augment/normalize 单元测试。

## 核心代码说明

- `preserve`
  - 用户请求中已有 `cache_control` 时直接保留原始请求，行为等同旧版本。
- `augment`
  - 用户请求中已有 `cache_control` 时不删除原有断点。
  - 若总断点数未达到 Anthropic 限制，则尝试在 tools/system/latest user content 的安全位置补充系统断点。
  - 若无法补充，则退回原始请求并记录 `user_cache_control_present_no_room` 或 `no_safe_breakpoint`。
- `normalize`
  - 删除请求体中受支持位置的用户 `cache_control`。
  - 再按系统稳定规则重新注入 tools/system 稳定前缀断点。
  - 已有用户断点场景下不再重新给最新 user block 注入 history 断点，避免删除后又加回低价值位置。
- fallback
  - 现有 `should_retry_with_fallback` 已覆盖 400/403/422 且错误内容包含 prompt cache/cache_control 相关提示的情况。
  - 本次新增的增强/纠偏变体会自然进入该 fallback 链路，最后一个变体保留原始请求。

## 测试验证

- `/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest test_anthropic_prompt_cache_policy.py`
  - 3 tests OK
- `/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest test_proxy_retry_error_sanitization.py`
  - 19 tests OK
- `/Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m py_compile app/services/anthropic_prompt_cache_service.py test_anthropic_prompt_cache_policy.py`
  - 通过
- 自动 Review 后按建议修复：
  - `normalize` 不再把断点重新加到最新用户消息。
  - 增量 SQL 重跑不覆盖线上手动回退值。

## 回退方式

无需发版即可在 `/admin/config` 将 `anthropic_prompt_cache_control_policy` 改为 `preserve`，即可回到旧行为。
