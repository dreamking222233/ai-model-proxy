# PromptCache优化 Plan 20260611

## 用户原始需求

当前系统是 AI 请求中转平台，本身不做响应缓存。不同上游渠道会影响用户请求的 prompt cache 表现。先根据以下策略优化一版并部署观察：

- 默认保守模式：用户自带 `cache_control` 时不破坏原始请求。
- 增强模式：用户自带 `cache_control` 但断点不稳定时，系统额外给稳定内容补缓存断点。
- 纠偏模式：用户把 `cache_control` 放到低价值位置时，系统可移除或忽略，并改放到稳定前缀。
- 失败回退：增强后如果上游返回格式错误，自动用原始请求重试。

暂不处理渠道粘性和渠道选择。

## 技术方案设计

- 在 `AnthropicPromptCacheService` 增加 `anthropic_prompt_cache_control_policy` 配置：
  - `preserve`：完全保留用户自带 `cache_control`，等同当前行为。
  - `augment`：保留用户自带断点，并在安全稳定位置补充系统断点。
  - `normalize`：移除用户断点，按系统稳定规则重新注入。
- 保持现有 prompt cache variant/fallback 机制：
  - 第一轮走增强/纠偏请求。
  - 如果上游返回 `cache_control`、`prompt cache`、`invalid_request_error` 等相关 400/403/422，继续走后续 fallback。
  - 最后 fallback 到原始请求，避免影响用户调用。
- 在 admin/config 缓存配置区域增加策略选择，方便线上切换。
- 增加 SQL 升级脚本，线上默认设置为 `augment` 便于观察；可随时改回 `preserve` 回退。

## 涉及文件清单

- `backend/app/services/anthropic_prompt_cache_service.py`
- `frontend/src/views/admin/SystemConfig.vue`
- `backend/sql/upgrade_prompt_cache_control_policy_20260611.sql`
- `backend/sql/init.sql`
- `backend/sql/initData.sql`
- `backend/test_anthropic_prompt_cache_policy.py`

## 实施步骤概要

1. 增加 prompt cache 策略读取和规范化。
2. 改造已有 `cache_control` 请求的处理逻辑，支持 preserve/augment/normalize。
3. 记录策略、是否移除用户断点、是否增强到日志详情。
4. 补充 admin/config 策略显示和保存。
5. 增加升级 SQL 和初始化 SQL。
6. 增加后端单元测试。
7. 本地验证后提交并推送 GitHub。
8. 服务器拉取、更新数据库、重启后端。
9. 部署后观察线上缓存聚合数据。
