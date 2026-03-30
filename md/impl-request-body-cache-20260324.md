# 请求体缓存方案 Impl

## 1. 任务概述

本次实现不是恢复旧的“响应缓存”或“改写上游请求参数”的缓存，而是实现一套**请求体分段缓存分析**能力：

1. 对每次请求体进行分段拆解。
2. 使用 Redis 按用户维度缓存请求片段。
3. 统计本次请求的缓存创建、读取、跳过。
4. 在不改变上游请求体的前提下，将缓存摘要写入 `request_log` 和 `request_cache_summary`。
5. 在 `admin/logs` 和 `user/balance` 页面显示缓存创建/读取。
6. 将缓存控制统一收敛到 `admin/config`。
7. 删除 `admin/users` 中按用户设置缓存的入口。

## 2. 文件变更清单

### 后端

1. [backend/app/models/log.py](/Volumes/project/modelInvocationSystem/backend/app/models/log.py)
2. [backend/app/models/__init__.py](/Volumes/project/modelInvocationSystem/backend/app/models/__init__.py)
3. [backend/app/services/request_body_cache_analyzer.py](/Volumes/project/modelInvocationSystem/backend/app/services/request_body_cache_analyzer.py)
4. [backend/app/services/request_body_cache_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/request_body_cache_service.py)
5. [backend/app/services/request_cache_summary_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/request_cache_summary_service.py)
6. [backend/app/middleware/cache_middleware.py](/Volumes/project/modelInvocationSystem/backend/app/middleware/cache_middleware.py)
7. [backend/app/middleware/stream_cache_middleware.py](/Volumes/project/modelInvocationSystem/backend/app/middleware/stream_cache_middleware.py)
8. [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py)
9. [backend/app/services/log_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py)
10. [backend/app/api/user/profile.py](/Volumes/project/modelInvocationSystem/backend/app/api/user/profile.py)
11. [sql/upgrade_request_body_cache_20260324.sql](/Volumes/project/modelInvocationSystem/sql/upgrade_request_body_cache_20260324.sql)
12. [sql/init.sql](/Volumes/project/modelInvocationSystem/sql/init.sql)
13. [backend/sql/init.sql](/Volumes/project/modelInvocationSystem/backend/sql/init.sql)

### 前端

1. [frontend/src/views/admin/RequestLog.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/RequestLog.vue)
2. [frontend/src/views/user/BalanceLog.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/BalanceLog.vue)
3. [frontend/src/views/admin/SystemConfig.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/SystemConfig.vue)
4. [frontend/src/views/admin/UserManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/UserManage.vue)
5. [frontend/src/router/index.js](/Volumes/project/modelInvocationSystem/frontend/src/router/index.js)

## 3. 核心实现说明

### 3.1 请求体分段算法

新增 [request_body_cache_analyzer.py](/Volumes/project/modelInvocationSystem/backend/app/services/request_body_cache_analyzer.py)：

1. `anthropic_messages`
   - 拆分 `system_block`
   - 拆分 `tool_definition`
   - 拆分 `message_content_block`
2. `openai_chat`
   - 拆分 `system_message`
   - 拆分 `tool_definition`
   - 拆分 `message`
   - 拆分 `tool_call`
3. `responses`
   - 拆分 `instructions`
   - 拆分 `tool_definition`
   - 拆分 `input_item`

每个片段都会计算：

1. 稳定序列化
2. `sha256`
3. `size_chars`
4. `estimated_tokens`
5. `preview`

### 3.2 Redis 请求体缓存

新增 [request_body_cache_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/request_body_cache_service.py)：

1. Redis key 维度为：
   - `user_id + request_format + segment_type + sha256`
2. 读取命中记为 `HIT`
3. 未命中则写入 Redis 并记为 `MISS`
4. 小于 `request_body_cache_min_chars` 的片段记为 `BYPASS`
5. Redis 不可用、功能关闭、格式未启用时统一 `BYPASS`

注意：

1. 不修改任何上游请求体内容
2. 不返回旧响应
3. 不减少真实上游 token
4. 只做系统内部分析和缓存片段读写

### 3.3 中间件接入

重构：

1. [cache_middleware.py](/Volumes/project/modelInvocationSystem/backend/app/middleware/cache_middleware.py)
2. [stream_cache_middleware.py](/Volumes/project/modelInvocationSystem/backend/app/middleware/stream_cache_middleware.py)

当前语义：

1. 请求进入时先做请求体缓存分析
2. 生成 `cache_info`
3. 原样执行上游调用
4. 真实计费仍按上游返回 token

### 3.4 日志与持久化

新增：

1. `request_log` 扩展字段：
   - `cache_status`
   - `cache_hit_segments`
   - `cache_miss_segments`
   - `cache_bypass_segments`
   - `cache_reused_tokens`
   - `cache_new_tokens`
   - `cache_reused_chars`
   - `cache_new_chars`
2. `request_cache_summary` 新表：
   - 保存按请求聚合的缓存摘要
   - 保存 `details_json`

新增 [request_cache_summary_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/request_cache_summary_service.py)：

1. 将 `cache_info` 映射到 `request_log`
2. 将完整缓存摘要落到 `request_cache_summary`

### 3.5 页面展示

管理端：

1. [RequestLog.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/RequestLog.vue)
   - 在 Token 用量区显示：
     - `读 x`
     - `建 x`
     - `复用 ~x tok`
   - 在详情弹窗显示缓存摘要

用户端：

1. [BalanceLog.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/BalanceLog.vue)
   - 只有在 `request_body_cache_enabled=true` 且 `request_body_cache_user_visible=true` 时才显示缓存信息

系统配置：

1. [SystemConfig.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/SystemConfig.vue)
   - 新增请求体缓存配置卡片
   - 可控制：
     - 缓存总开关
     - 用户端可见
     - TTL
     - 最小片段长度

旧入口清理：

1. [UserManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/UserManage.vue)
   - 删除用户级缓存开关/缓存计费 UI
2. [router/index.js](/Volumes/project/modelInvocationSystem/frontend/src/router/index.js)
   - 移除 `/admin/cache`
   - 移除 `/user/cache`

## 4. 数据库与本地环境处理

已执行本地升级：

1. [upgrade_request_body_cache_20260324.sql](/Volumes/project/modelInvocationSystem/sql/upgrade_request_body_cache_20260324.sql)
2. 本地 `modelinvoke` 库新增：
   - `request_log` 缓存摘要字段
   - `request_cache_summary` 表
   - `system_config` 缓存配置项

已在本地测试环境打开：

1. `request_body_cache_enabled=true`
2. `request_body_cache_user_visible=true`

## 5. 测试与验证

### 5.1 后端语法校验

已执行：

```bash
python -m py_compile backend/app/models/log.py backend/app/models/__init__.py backend/app/services/request_body_cache_analyzer.py backend/app/services/request_body_cache_service.py backend/app/services/request_cache_summary_service.py backend/app/middleware/cache_middleware.py backend/app/middleware/stream_cache_middleware.py backend/app/services/log_service.py backend/app/api/user/profile.py backend/app/services/proxy_service.py
```

### 5.2 前端构建校验

已执行：

```bash
cd frontend && npm run build
```

结果：

1. 构建成功
2. 仅存在原有体积 warning 和无关 lint warning

### 5.3 真实请求验证

使用本地有效 API key 对 `http://127.0.0.1:8085/v1/messages` 做真实 Anthropic 请求验证。

#### 验证 1：短文本

结果：

1. 两个片段都未达到 `256 chars`
2. 正确记录为 `BYPASS`

数据库验证：

1. `request_log.id=467`
2. `request_log.id=468`
3. `request_cache_summary.id=1`
4. `request_cache_summary.id=2`

#### 验证 2：长文本重复请求

结果：

1. 请求片段为 2 段：
   - 1 个 `system_block`
   - 1 个 `message_content_block`
2. 已成功出现真实的 `MISS` / `HIT`

数据库验证结果：

1. `request_log.id=470`
   - `cache_status=MISS`
   - `cache_miss_segments=2`
   - `cache_new_tokens=231`
2. `request_log.id=469`
   - `cache_status=HIT`
   - `cache_hit_segments=2`
   - `cache_reused_tokens=231`
3. `request_cache_summary.id=4`
   - `request_format=anthropic_messages`
   - `cache_status=MISS`
4. `request_cache_summary.id=3`
   - `request_format=anthropic_messages`
   - `cache_status=HIT`

说明：

1. 系统已能对相同长请求体片段执行创建与读取
2. 且不会影响真实上游调用

## 6. 当前状态

已完成：

1. 请求体分段识别
2. Redis 缓存创建/读取
3. 请求日志与摘要表持久化
4. admin/logs 展示
5. user/balance 展示
6. admin/config 统一控制
7. admin/users 用户级缓存入口删除
8. 本地数据库升级
9. 本地真实请求命中验证

未做：

1. 不做响应短路缓存
2. 不做上游请求体裁剪
3. 不做流式回放缓存
4. 不做缓存计费减免

## 7. 结论

本次实现满足了当前阶段的安全目标：

1. 能识别真实请求体中的重复片段
2. 能执行 Redis 创建/读取
3. 能在管理端和用户端展示缓存创建/读取
4. 不修改上游请求体
5. 不影响系统正常调用

当前这套实现解决的是“重复内容识别、缓存留痕、统计与展示”，不是“真实减少上游 token 成本”。如果后续允许接入上游原生 Prompt Caching，再可在此基础上扩展为真正的上游 token 降本方案。
