# Conversation State Compaction 实施记录

## 1. 任务概述

本轮按 `Plan v2` 实施了 `Phase 1 + Phase 2` 的最小可用闭环，目标是：

1. 不改真实上游请求
2. 先做会话识别
3. 先做 shadow 模式的理论压缩估算
4. 请求成功后再提交会话状态

当前已完成：

1. 会话状态表与检查点表
2. `request_log` 会话压缩影子字段
3. Anthropic `/v1/messages` 主链路 shadow 接入
4. 请求成功后会话状态与检查点提交
5. admin/user 页面基础展示
6. `non_stream_active` 真实历史压缩接入
7. 压缩失败自动 full request fallback 代码路径
8. `stream_active` 真实历史压缩接入

## 2. 文件变更清单

### 后端

1. `backend/app/models/log.py`
2. `backend/app/models/__init__.py`
3. `backend/app/services/proxy_service.py`
4. `backend/app/services/request_cache_summary_service.py`
5. `backend/app/services/log_service.py`
6. `backend/app/services/conversation_match_service.py`
7. `backend/app/services/conversation_session_service.py`
8. `backend/app/services/history_compaction_service.py`
9. `backend/app/services/conversation_shadow_service.py`

### 前端

1. `frontend/src/views/admin/RequestLog.vue`
2. `frontend/src/views/user/BalanceLog.vue`

### SQL

1. `sql/init.sql`
2. `backend/sql/init.sql`
3. `sql/upgrade_conversation_state_compaction_20260325.sql`

## 3. 核心实现说明

### 3.1 会话匹配

新增 `ConversationMatchService`：

1. 对 Anthropic 请求构建：
   - `system_hash`
   - `tools_hash`
   - `message_hashes`
2. 自动匹配同一 `user + model + protocol + system_hash + tools_hash`
3. 通过消息 hash 前缀判断：
   - `NEW`
   - `EXACT`
   - `APPEND`
   - `RESET`

### 3.2 Shadow 压缩估算

新增 `HistoryCompactionService` 与 `ConversationShadowService`：

1. 只按“已完成 turn 组”切历史
2. 不切断 `tool_use -> tool_result`
3. 默认不压缩 `system / tools`
4. 将老历史重建为一个会话检查点块，仅用于估算，不发送上游

### 3.3 主链路接入

在 `ProxyService.handle_anthropic_request` 中：

1. 先计算 `conversation_shadow_info`
2. 实际请求仍保持完整原始请求
3. 请求成功后：
   - 写入 `request_log`
   - 提交 `conversation_session`
   - 提交 `conversation_checkpoint`

### 3.4 日志与展示

新增 `request_log` 字段：

1. `conversation_session_id`
2. `conversation_match_status`
3. `compression_mode`
4. `compression_status`
5. `original_estimated_input_tokens`
6. `compressed_estimated_input_tokens`
7. `compression_saved_estimated_tokens`
8. `compression_ratio`
9. `compression_fallback_reason`
10. `upstream_session_mode`
11. `upstream_session_id`

admin/user 页面已可展示：

1. `会话压缩`
2. `NEW / APPEND`
3. `SHADOW_READY / SHADOW_BYPASS_NEW_SESSION`
4. 理论节省 token

## 4. 本地验证

### 4.1 编译验证

1. `python -m py_compile ...` 通过
2. `npm run build` 通过

### 4.2 MySQL 升级

已执行：

1. `sql/upgrade_conversation_state_compaction_20260325.sql`
2. 修正了 `request_log.compression_status` 字段长度到 `VARCHAR(64)`

### 4.3 Anthropic Shadow 联调

本地构造了两次同会话 Anthropic 请求：

1. 第一次请求：
   - `conversation_match_status = NEW`
   - `compression_status = SHADOW_BYPASS_NEW_SESSION`
2. 第二次 append 请求：
   - `conversation_match_status = APPEND`
   - `compression_status = SHADOW_READY`
   - `original_estimated_input_tokens = 49323`
   - `compressed_estimated_input_tokens = 49029`
   - `compression_saved_estimated_tokens = 294`
   - `compression_ratio = 0.0060`

并成功落库：

1. `conversation_session`
2. `conversation_checkpoint`

### 4.4 Anthropic `non_stream_active` 联调

已将：

1. `conversation_state_compaction_enabled = true`
2. `conversation_state_compaction_stage = non_stream_active`

后对同一长会话再次发起非流式请求，最新 `request_log` 结果为：

1. `conversation_match_status = EXACT`
2. `compression_mode = non_stream_active`
3. `compression_status = ACTIVE_APPLIED`
4. `original_estimated_input_tokens = 49323`
5. `compressed_estimated_input_tokens = 49029`
6. `compression_saved_estimated_tokens = 294`
7. 实际上游 `input_tokens` 从前一轮 `31235` 降到 `31066`

说明：

1. 非流式真实历史压缩链路已实际生效
2. 当前案例下已看到真实上游输入 token 下降
3. 压缩后的请求仍能正常返回

### 4.5 Anthropic `stream_active` 联调

进一步将：

1. `conversation_state_compaction_stage = stream_active`

后，对同一长会话发送流式请求，SSE 正常返回，最新 `request_log` 记录为：

1. `is_stream = 1`
2. `conversation_match_status = EXACT`
3. `compression_mode = stream_active`
4. `compression_status = ACTIVE_APPLIED`
5. `original_estimated_input_tokens = 49323`
6. `compressed_estimated_input_tokens = 49029`
7. `compression_saved_estimated_tokens = 294`
8. 实际上游 `input_tokens = 31066`

说明：

1. 流式真实历史压缩链路已可用
2. 当前案例下流式请求也出现了真实上游输入 token 下降
3. 当前实现只支持“首字节前 fallback”，属于保守实现

## 5. 当前结论

当前系统已经具备：

1. 会话识别
2. shadow 模式估算
3. 成功后提交会话状态
4. 页面展示 shadow 结果
5. 非流式真实历史压缩
6. 压缩失败回退完整原始请求的实现路径
7. 流式真实历史压缩
8. stateful upstream 抽象占位

当前仍未进入默认真实压缩的只有：

1. 真实 stateful upstream 增量发送
2. 实验性 tools/system 压缩

## 6. 下一步建议

下一轮实施应进入：

1. `Phase 4`
   - 流式 shadow / 灰度
2. `Phase 5`
   - 状态会话上游抽象的进一步接线
