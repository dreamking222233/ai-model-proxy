# AI 请求缓存系统 - 文件修改记录

**日期**: 2026-03-21
**功能**: AI 请求缓存系统（流式/非流式，支持 OpenAI/Anthropic/Responses API）
**状态**: ✅ 已完成并测试通过

---

## 一、新增文件清单

### 1.1 后端核心文件

| 文件路径 | 说明 | 行数 |
|---------|------|------|
| `backend/app/core/redis_client.py` | Redis 客户端封装 | ~50 |
| `backend/app/models/cache_log.py` | 缓存日志 ORM 模型 | ~30 |
| `backend/app/services/cache_service.py` | 核心缓存服务（Redis 操作） | ~255 |
| `backend/app/services/cache_stats_service.py` | 缓存统计服务（数据库操作） | ~319 |
| `backend/app/services/cache_key_generator.py` | 缓存键生成器 | ~150 |
| `backend/app/middleware/cache_middleware.py` | 非流式请求缓存中间件 | ~200 |
| `backend/app/middleware/stream_cache_middleware.py` | 流式请求缓存中间件 | ~454 |
| `backend/app/api/admin/cache.py` | 管理员缓存管理 API | ~150 |
| `backend/app/api/user/cache.py` | 用户缓存统计 API | ~100 |

### 1.2 前端文件

| 文件路径 | 说明 |
|---------|------|
| `frontend/src/views/admin/CacheManage.vue` | 缓存管理页面 |
| `frontend/src/views/user/CacheStats.vue` | 用户缓存统计页面 |

### 1.3 SQL 文件

| 文件路径 | 说明 |
|---------|------|
| `sql/add_cache_system_20260321.sql` | 缓存系统数据库迁移脚本 |

### 1.4 文档文件

| 文件路径 | 说明 |
|---------|------|
| `md/plan-ai-request-cache-20260321.md` | 初始计划文档 |
| `md/plan-ai-request-cache-20260321-v2.md` | 修订后的计划文档 |
| `md/impl-ai-request-cache-20260321.md` | 实现文档 |
| `md/impl-cache-integration-20260321.md` | 集成文档 |
| `md/codex-review-plan-v1-20260321.md` | Codex Review 第1轮 |
| `md/codex-review-plan-v2-20260321.md` | Codex Review 第2轮 |
| `md/codex-review-stream-cache-final-20260321.md` | Codex Review 第3轮（流式缓存） |
| `md/codex-review-responses-cache-20260321.md` | Codex Review 第4轮（Responses API） |
| `md/cache-implementation-status-20260321.md` | 实现状态报告 |
| `md/cache-test-report-20260321.md` | 测试报告 |
| `md/stream-cache-test-guide-20260321.md` | 测试指南 |
| `md/final-summary-cache-system-20260321.md` | 最终总结 |
| `md/cache-system-changes-20260321.md` | 本文档 |

### 1.5 测试文件

| 文件路径 | 说明 |
|---------|------|
| `backend/test_stream_cache.py` | 流式缓存测试脚本 |

---

## 二、修改文件清单

### 2.1 后端核心文件

| 文件路径 | 修改内容 | 关键变更 |
|---------|---------|---------|
| `backend/app/models/user.py` | 添加缓存相关字段 | `cache_enabled`, `cache_hit_count`, `cache_saved_tokens`, `cache_billing_enabled` |
| `backend/app/services/proxy_service.py` | 集成缓存中间件 | 在 OpenAI/Anthropic/Responses API 的流式和非流式方法中调用缓存中间件 |
| `backend/app/main.py` | 注册缓存路由 | 添加 `admin_cache_router` 和 `user_cache_router` |
| `backend/app/services/auth_service.py` | 添加缓存字段支持 | 用户注册时初始化缓存字段 |

### 2.2 前端文件

| 文件路径 | 修改内容 |
|---------|---------|
| `frontend/src/views/admin/UserManage.vue` | 添加缓存统计列显示 |
| `frontend/src/router/index.ts` | 添加缓存管理路由 |
| `frontend/src/api/cache.ts` | 添加缓存 API 接口 |

### 2.3 SQL 文件

| 文件路径 | 修改内容 |
|---------|---------|
| `sql/init.sql` | 添加缓存相关字段和表 |

---

## 三、数据库变更详情

### 3.1 新增表

#### cache_log - 缓存日志表

```sql
CREATE TABLE `cache_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `cache_key` VARCHAR(64) NOT NULL COMMENT 'Cache Key (SHA256)',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `model` VARCHAR(100) NOT NULL COMMENT '模型名称',
    `prompt_tokens` INT NOT NULL COMMENT 'Prompt Tokens',
    `completion_tokens` INT NOT NULL COMMENT 'Completion Tokens',
    `cache_status` ENUM('HIT', 'MISS', 'BYPASS') NOT NULL COMMENT '缓存状态',
    `saved_tokens` INT DEFAULT 0 COMMENT '节省的 Tokens',
    `saved_cost` DECIMAL(10, 6) DEFAULT 0.00 COMMENT '节省的费用',
    `ttl` INT NOT NULL COMMENT '缓存时长（秒）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_cache_key` (`cache_key`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_cache_status` (`cache_status`),
    KEY `idx_user_created` (`user_id`, `created_at`),
    KEY `idx_user_status_created` (`user_id`, `cache_status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='缓存日志表';
```

### 3.2 修改表

#### sys_user - 系统用户表

**新增字段**:
- `cache_enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用缓存（1=启用，0=禁用）'
- `cache_hit_count` BIGINT NOT NULL DEFAULT 0 COMMENT '缓存命中次数'
- `cache_saved_tokens` BIGINT NOT NULL DEFAULT 0 COMMENT '累计节省 Tokens'
- `cache_billing_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '缓存计费开关（1=按缓存后计费，0=按原始计费）'
- `subscription_type` VARCHAR(10) NOT NULL DEFAULT 'balance' COMMENT 'balance=按量计费, unlimited=时间套餐'
- `subscription_expires_at` DATETIME DEFAULT NULL COMMENT '套餐过期时间'

#### channel - 渠道表

**新增字段**:
- `auth_header_type` VARCHAR(32) NOT NULL DEFAULT 'x-api-key' COMMENT 'Auth header type: x-api-key, anthropic-api-key, authorization'

---

## 四、核心功能实现

### 4.1 缓存中间件

#### 非流式缓存 (CacheMiddleware)

**文件**: `backend/app/middleware/cache_middleware.py`

**功能**:
- 缓存查询（Redis: `cache:content:{cache_key}`）
- 缓存保存（TTL 默认 3600 秒）
- 缓存命中时根据用户配置减免计费
- 统计记录（数据库 + Redis）

**支持协议**:
- ✅ OpenAI
- ✅ Anthropic
- ✅ Responses API

#### 流式缓存 (StreamCacheMiddleware)

**文件**: `backend/app/middleware/stream_cache_middleware.py`

**功能**:
- 缓存查询（Redis: `cache:stream:{cache_key}`）
- 缓存保存（包含 chunks、延迟、usage）
- 缓存重放（模拟流式输出，包含延迟）
- 事件序列生成（根据协议生成正确的 SSE 事件）
- 计费回调集成
- 统计记录

**支持协议**:
- ✅ OpenAI（完整的 delta chunks + `[DONE]`）
- ✅ Anthropic（完整的 6 个事件序列）
- ✅ Responses API（完整的前置事件 + delta + 结束事件）

### 4.2 缓存键生成

**文件**: `backend/app/services/cache_key_generator.py`

**算法**: SHA256(标准化请求体)

**标准化规则**:
- 移除 `stream` 字段
- 移除 `user` 字段
- 排序 messages
- 排序字典键
- 确保一致性

### 4.3 缓存绕过条件

1. **全局开关**: `CACHE_ENABLED=false`
2. **用户级别**: `user.cache_enabled=0`
3. **请求级别**: `X-No-Cache: true`
4. **特殊情况**:
   - 包含 `tools` 或 `tool_choice`
   - 包含 `response_format`
   - 包含 `seed`
   - 包含 `logprobs`

### 4.4 计费逻辑

**缓存命中时**:
- 如果 `user.cache_billing_enabled=1`: 按实际 tokens 计费
- 如果 `user.cache_billing_enabled=0`: 免费（tokens=0）

**缓存未命中时**:
- 正常计费

---

## 五、API 接口

### 5.1 管理员接口

**路由前缀**: `/api/admin/cache`

| 接口 | 方法 | 说明 |
|------|------|------|
| `/stats` | GET | 全局缓存统计 |
| `/logs` | GET | 缓存日志列表 |
| `/clear` | POST | 清空所有缓存 |
| `/clear/user/{user_id}` | POST | 清空指定用户缓存 |

### 5.2 用户接口

**路由前缀**: `/api/user/cache`

| 接口 | 方法 | 说明 |
|------|------|------|
| `/stats` | GET | 用户缓存统计 |
| `/clear` | POST | 清空自己的缓存 |

---

## 六、配置说明

### 6.1 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `CACHE_ENABLED` | `true` | 全局缓存开关 |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_DB` | `0` | Redis 数据库 |
| `REDIS_PASSWORD` | `None` | Redis 密码 |

### 6.2 请求头

| 请求头 | 说明 | 示例 |
|--------|------|------|
| `X-No-Cache` | 跳过缓存 | `true` |
| `X-Cache-TTL` | 自定义 TTL（秒） | `7200` |

### 6.3 响应头

| 响应头 | 说明 | 可能值 |
|--------|------|--------|
| `X-Cache-Status` | 缓存状态 | `HIT` / `MISS` / `BYPASS` / `STREAM` |
| `X-Request-ID` | 请求 ID | UUID |

---

## 七、测试验证

### 7.1 测试脚本

**文件**: `backend/test_stream_cache.py`

**测试场景**:
1. 第一次请求 - 预期 MISS
2. 第二次相同请求 - 预期 HIT
3. 第三次不同请求 - 预期 MISS
4. 第四次请求（同测试1） - 预期 HIT

### 7.2 测试结果

**状态**: ✅ 通过

**测试输出**:
```
测试1（第一次）: 2.94s - ✅ 成功
测试2（相同请求）: 2.83s - ✅ 内容一致
测试3（不同请求）: 3.18s - ✅ 不同内容
测试4（同测试1）: 3.47s - ✅ 内容一致
```

### 7.3 Codex Review

**轮次**: 4 轮

| 轮次 | 文件 | 结果 |
|------|------|------|
| 第1轮 | `codex-review-plan-v1-20260321.md` | 🔶 需修改 |
| 第2轮 | `codex-review-plan-v2-20260321.md` | ✅ 通过 |
| 第3轮 | `codex-review-stream-cache-final-20260321.md` | 🔶 需修改 |
| 第4轮 | `codex-review-responses-cache-20260321.md` | ✅ 通过 |

---

## 八、已知问题与限制

### 8.1 流式请求响应头限制

**问题**: `X-Cache-Status` 响应头固定为 `"STREAM"`，无法反映实际的 HIT/MISS 状态。

**原因**: FastAPI/Starlette 的 `StreamingResponse` 在构造时就固定了 headers，此时 generator 尚未执行，无法获取实际的缓存状态。

**解决方案**: 实际的缓存状态通过后端日志记录：
- `Stream cache HIT for user xxx, key=xxxxxxxx...`
- `Stream cache MISS for user xxx, key=xxxxxxxx...`

### 8.2 缓存 TTL

**默认 TTL**: 3600 秒（1 小时）

**自定义 TTL**: 通过请求头 `X-Cache-TTL` 设置（单位：秒）

---

## 九、部署清单

### 9.1 数据库迁移

```bash
# 执行缓存系统迁移脚本
mysql -u root -p modelinvoke < sql/add_cache_system_20260321.sql

# 或者使用完整的 init.sql 重新初始化（会清空所有数据）
mysql -u root -p modelinvoke < sql/init.sql
```

### 9.2 Redis 启动

```bash
# 启动 Redis
redis-server --daemonize yes

# 验证 Redis
redis-cli ping  # 应返回 PONG
```

### 9.3 后端服务

```bash
# 安装依赖
pip install redis

# 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8085
```

### 9.4 环境变量

```bash
# .env 文件
CACHE_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

---

## 十、Git 提交建议

### 10.1 提交信息

```
feat: AI 请求缓存系统（流式/非流式，支持 OpenAI/Anthropic/Responses API）

- 新增缓存中间件（流式/非流式）
- 新增缓存服务和统计服务
- 新增缓存管理 API（管理员/用户）
- 新增缓存日志表和用户缓存字段
- 支持 OpenAI/Anthropic/Responses API 三种协议
- 支持缓存命中时根据用户配置减免计费
- 完整的事件序列重放（Anthropic/Responses API）
- 通过 4 轮 Codex Review 和测试验证

Closes #xxx
```

### 10.2 提交文件

**新增文件**:
```bash
git add backend/app/core/redis_client.py
git add backend/app/models/cache_log.py
git add backend/app/services/cache_service.py
git add backend/app/services/cache_stats_service.py
git add backend/app/services/cache_key_generator.py
git add backend/app/middleware/cache_middleware.py
git add backend/app/middleware/stream_cache_middleware.py
git add backend/app/api/admin/cache.py
git add backend/app/api/user/cache.py
git add sql/add_cache_system_20260321.sql
git add backend/test_stream_cache.py
```

**修改文件**:
```bash
git add backend/app/models/user.py
git add backend/app/services/proxy_service.py
git add backend/app/main.py
git add backend/app/services/auth_service.py
git add sql/init.sql
git add frontend/src/views/admin/UserManage.vue
```

**文档文件**:
```bash
git add md/plan-ai-request-cache-20260321.md
git add md/plan-ai-request-cache-20260321-v2.md
git add md/impl-ai-request-cache-20260321.md
git add md/impl-cache-integration-20260321.md
git add md/codex-review-plan-v1-20260321.md
git add md/codex-review-plan-v2-20260321.md
git add md/codex-review-stream-cache-final-20260321.md
git add md/codex-review-responses-cache-20260321.md
git add md/cache-implementation-status-20260321.md
git add md/cache-test-report-20260321.md
git add md/stream-cache-test-guide-20260321.md
git add md/final-summary-cache-system-20260321.md
git add md/cache-system-changes-20260321.md
```

---

## 十一、后续优化建议

### 11.1 性能优化

1. **缓存预热**: 对热门请求进行缓存预热
2. **缓存压缩**: 对大型响应进行压缩存储
3. **缓存分片**: 使用 Redis Cluster 进行缓存分片

### 11.2 功能增强

1. **缓存失效策略**: 支持主动失效和版本控制
2. **缓存监控**: 添加缓存命中率监控和告警
3. **缓存分析**: 提供缓存使用分析报告

### 11.3 安全加固

1. **缓存隔离**: 不同用户的缓存完全隔离
2. **敏感信息过滤**: 自动过滤敏感信息
3. **访问控制**: 细粒度的缓存访问控制

---

**文档版本**: 1.0
**最后更新**: 2026-03-21
**维护者**: AI 开发团队
