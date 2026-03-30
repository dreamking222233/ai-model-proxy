# Anthropic Prompt Cache 实施记录

## 1. 任务概述

基于 `Plan v2`，本次完成了 Anthropic Prompt Cache 的代码接入、双口径 usage 落库、admin/user 展示改造，以及对当前上游 `43.156.153.12:8080/v1/messages` 的真实 capability probe。

最终验证结论：

1. 系统侧已能安全注入 Anthropic 官方 `cache_control`，且不会改写业务文本、工具、顺序。
2. 本地链路已能记录真实 upstream prompt cache usage 字段。
3. 当前上游网关接受带 `cache_control` 的请求，但不返回任何 `cache_read_input_tokens` / `cache_creation_input_tokens`。
4. 对超过 `1024` token 的重复长前缀请求，`input_tokens` 仍完全不下降。
5. 因此当前 `43.156.153.12:8080` 网关不支持真实 Anthropic Prompt Caching，已将本地 `anthropic_prompt_cache_enabled` 重新关闭，避免无效元数据持续发送。

## 2. 文件变更清单

### 后端

1. `backend/app/services/anthropic_prompt_cache_service.py`
2. `backend/app/services/proxy_service.py`
3. `backend/app/services/request_cache_summary_service.py`
4. `backend/app/services/log_service.py`
5. `backend/app/services/balance_service.py`
6. `backend/app/services/subscription_service.py`
7. `backend/app/api/user/profile.py`
8. `backend/app/api/user/balance.py`
9. `backend/app/models/log.py`

### 前端

1. `frontend/src/views/admin/SystemConfig.vue`
2. `frontend/src/views/admin/RequestLog.vue`
3. `frontend/src/views/user/BalanceLog.vue`

### SQL

1. `sql/upgrade_anthropic_prompt_cache_20260325.sql`
2. `sql/init.sql`
3. `backend/sql/init.sql`

## 3. 核心实现说明

### 3.1 Anthropic Prompt Cache 注入器

新增 `AnthropicPromptCacheService`，实现：

1. 读取系统配置：
   - `anthropic_prompt_cache_enabled`
   - `anthropic_prompt_cache_history_enabled`
   - `anthropic_prompt_cache_static_ttl`
   - `anthropic_prompt_cache_history_ttl`
   - `anthropic_prompt_cache_beta_header`
   - `anthropic_prompt_cache_user_visible`
   - `anthropic_prompt_cache_billing_mode`
2. 仅在安全块上注入官方 `cache_control`
   - 优先最后一个 `tool`
   - 其次最近一轮 `user.content` 的最后一个 block
3. 不改写文本内容，不合并消息，不删工具，不重排顺序
4. 支持 1h -> 5m -> no-cache 的回退变体

### 3.2 Anthropic 主链路接入

在 `proxy_service.py` 中接入：

1. `_stream_anthropic_request`
2. `_non_stream_anthropic_request`

实现方式：

1. 内部请求体缓存分析仍基于原始请求体执行
2. 上游实际请求使用 prompt-cache 变体
3. 若上游返回疑似 cache 元数据兼容错误，则自动回退到更保守变体
4. 最终把 Anthropic prompt cache request/usage 信息合并回统一 `cache_info`

### 3.3 双口径 usage / billing

新增并落库：

1. `logical_input_tokens`
2. `upstream_input_tokens`
3. `upstream_cache_read_input_tokens`
4. `upstream_cache_creation_input_tokens`
5. `upstream_cache_creation_5m_input_tokens`
6. `upstream_cache_creation_1h_input_tokens`
7. `upstream_prompt_cache_status`

当前默认：

1. 继续按 `logical` 口径计费
2. admin/user 页面可展示真实 upstream cache usage

### 3.4 管理端 / 用户端展示

已改造：

1. `admin/system`
   - 新增 Anthropic Prompt Cache 开关/可见性/TTL/计费口径配置
2. `admin/logs`
   - Token 区域优先展示真实 upstream `读/建/实入`
   - 内部分段缓存退为次级明细
3. `user/balance`
   - 在配置允许时展示真实 upstream `读/建/实入`

## 4. 测试验证

### 4.1 本地静态验证

1. `python -m py_compile ...` 通过
2. `npm run build` 通过

### 4.2 本地后端联调

1. 已重启本地后端 `http://0.0.0.0:8085`
2. 本地 `/health` 正常

### 4.3 真实 capability probe

#### Probe A. 低 token 请求

对本地中转和上游直连分别发送两次相同请求：

1. 请求内已注入 `cache_control`
2. 上游返回正常
3. 但 usage 始终只有：
   - `input_tokens`
   - `output_tokens`
4. `request_log` 记录为：
   - `upstream_prompt_cache_status = NONE`
   - `upstream_cache_read_input_tokens = 0`
   - `upstream_cache_creation_input_tokens = 0`

#### Probe B. 超过最小缓存阈值的长前缀请求

使用长工具描述构造约 `12841` 输入 token 的请求，直连上游连续发送两次：

1. 第一次返回：
   - `usage.input_tokens = 12841`
2. 第二次返回：
   - `usage.input_tokens = 12841`
3. 两次都没有：
   - `cache_read_input_tokens`
   - `cache_creation_input_tokens`
4. 说明该网关并未暴露真实 Anthropic Prompt Caching 能力

## 5. 当前结论

代码层面，Anthropic Prompt Cache 主方案已完成接入。

但业务目标“真正减少当前上游 token”在现有网关 `43.156.153.12:8080` 上无法达成，原因不是本系统不注入，而是该网关本身不支持或不透传 Anthropic Prompt Caching。

因此当前正确结论是：

1. 本系统实现已到位
2. 当前网关 capability 不满足
3. 若要真正减少上游 token，必须更换为支持 Anthropic Prompt Caching 的上游或确认该网关升级支持相关能力

## 6. 后续建议

1. 保持当前 `anthropic_prompt_cache_enabled=false`
2. 若更换上游，再重新打开该配置做联调
3. 下一步可以补充：
   - channel 级 capability 缓存
   - admin 手动 capability probe 按钮
   - unsupported 状态展示
