# AI 请求缓存系统 - 详细设计方案

**创建时间**: 2026-03-21
**任务类型**: 大型（预计 15+ 步骤）
**核心目标**: 在代理层实现智能缓存机制，提高 AI 调用速度，同时确保不影响调用质量

---

## 1. 核心设计原则

### 1.1 缓存策略
- **缓存粒度**: 基于请求内容（messages + model + 关键参数）生成唯一 hash
- **缓存条件**:
  - 仅缓存 `messages` 内容（不缓存 system prompt 变化频繁的场景）
  - 仅缓存确定性请求（`temperature=0` 或未设置 temperature）
  - 排除 `stream=true` 的流式请求
  - 排除包含 `tools`/`tool_choice` 的函数调用请求
- **缓存时效**: 默认 1 小时，可配置（考虑模型更新频率）
- **缓存存储**: 优先 Redis，降级到内存缓存

### 1.2 质量保障机制
- **参数白名单**: 只有 `model`, `messages`, `max_tokens` 参与 cache key 计算
- **参数黑名单**: `temperature > 0`, `top_p`, `presence_penalty`, `frequency_penalty` 等随机性参数存在时不缓存
- **用户控制**:
  - 请求头 `X-No-Cache: true` 强制跳过缓存
  - 请求头 `X-Cache-TTL: 3600` 自定义缓存时长
- **缓存标识**: 响应头返回 `X-Cache-Status: HIT/MISS/BYPASS`

### 1.3 成本优化
- **最小缓存阈值**: 仅缓存 prompt tokens > 1000 的请求
- **缓存收益计算**: 记录缓存命中节省的 tokens 和费用
- **LRU 淘汰策略**: 内存缓存限制 1000 条，Redis 限制 10000 条

---

## 2. 技术架构设计

### 2.1 模块划分
```
backend/app/services/
├── cache_service.py          # 核心缓存服务
├── cache_key_generator.py    # Cache Key 生成器
└── cache_stats_service.py    # 缓存统计服务

backend/app/models/
└── cache_log.py              # 缓存日志模型（新增）

backend/app/core/
└── redis_client.py           # Redis 客户端封装（新增）
```

### 2.2 数据库设计
```sql
-- 缓存日志表
CREATE TABLE cache_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    cache_key VARCHAR(64) NOT NULL COMMENT 'Cache Key (SHA256)',
    user_id INT NOT NULL COMMENT '用户 ID',
    model VARCHAR(100) NOT NULL COMMENT '模型名称',
    prompt_tokens INT NOT NULL COMMENT 'Prompt Tokens',
    completion_tokens INT NOT NULL COMMENT 'Completion Tokens',
    cache_status ENUM('HIT', 'MISS', 'BYPASS') NOT NULL COMMENT '缓存状态',
    saved_tokens INT DEFAULT 0 COMMENT '节省的 Tokens',
    saved_cost DECIMAL(10, 6) DEFAULT 0 COMMENT '节省的费用',
    ttl INT NOT NULL COMMENT '缓存时长（秒）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_cache_key (cache_key),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='缓存日志表';

-- 用户表新增字段
ALTER TABLE user
ADD COLUMN enable_cache TINYINT DEFAULT 1 COMMENT '是否启用缓存（1=启用，0=禁用）',
ADD COLUMN cache_hit_count INT DEFAULT 0 COMMENT '缓存命中次数',
ADD COLUMN cache_saved_tokens BIGINT DEFAULT 0 COMMENT '累计节省 Tokens';
```

### 2.3 Redis 数据结构
```
# 缓存内容
Key: cache:content:{cache_key}
Value: JSON {
    "response": {...},           # 完整响应体
    "model": "gpt-4",
    "prompt_tokens": 1500,
    "completion_tokens": 300,
    "created_at": 1710998400
}
TTL: 3600 秒（可配置）

# 缓存统计
Key: cache:stats:{user_id}:{date}
Value: Hash {
    "hit_count": 10,
    "miss_count": 5,
    "saved_tokens": 15000,
    "saved_cost": 0.45
}
TTL: 30 天
```

---

## 3. 核心流程设计

### 3.1 请求处理流程
```
1. 接收请求 → proxy_service.forward_request()
2. 检查缓存开关
   ├─ 用户禁用缓存 → 跳过缓存
   ├─ 请求头 X-No-Cache → 跳过缓存
   └─ 继续
3. 检查缓存条件
   ├─ stream=true → 跳过缓存
   ├─ temperature > 0 → 跳过缓存
   ├─ 包含 tools → 跳过缓存
   ├─ prompt_tokens < 1000 → 跳过缓存
   └─ 继续
4. 生成 Cache Key
   └─ SHA256(model + messages + max_tokens)
5. 查询缓存
   ├─ Redis 查询
   │  ├─ 命中 → 返回缓存响应 + 记录统计
   │  └─ 未命中 → 继续
   └─ 内存缓存查询
      ├─ 命中 → 返回缓存响应 + 记录统计
      └─ 未命中 → 继续
6. 调用上游 API
7. 保存响应到缓存
   ├─ 保存到 Redis
   └─ 保存到内存缓存
8. 记录缓存日志
9. 返回响应（添加 X-Cache-Status 头）
```

### 3.2 Cache Key 生成算法
```python
def generate_cache_key(request_body: dict) -> str:
    """
    生成缓存键，仅基于影响响应内容的核心参数
    """
    cache_components = {
        "model": request_body.get("model"),
        "messages": request_body.get("messages"),
        "max_tokens": request_body.get("max_tokens")
    }

    # 标准化 messages（移除空白字符差异）
    normalized_messages = [
        {
            "role": msg["role"],
            "content": msg["content"].strip() if isinstance(msg["content"], str) else msg["content"]
        }
        for msg in cache_components["messages"]
    ]

    cache_components["messages"] = normalized_messages

    # 生成 SHA256 hash
    cache_str = json.dumps(cache_components, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cache_str.encode()).hexdigest()
```

---

## 4. 详细实现步骤

### Phase 1: 基础设施搭建（3 步）
1. **创建 Redis 客户端封装**
   - 文件: `backend/app/core/redis_client.py`
   - 功能: 连接池管理、异常处理、降级到内存缓存
   - 配置: 从环境变量读取 Redis 连接信息

2. **创建数据库表**
   - 执行 SQL: 创建 `cache_log` 表
   - 修改 `user` 表: 添加缓存相关字段
   - 更新 `init.sql`

3. **创建缓存日志模型**
   - 文件: `backend/app/models/cache_log.py`
   - 字段: 对应数据库表结构
   - 关系: 关联 `user` 表

### Phase 2: 核心缓存服务（4 步）
4. **实现 Cache Key 生成器**
   - 文件: `backend/app/services/cache_key_generator.py`
   - 类: `CacheKeyGenerator`
   - 方法:
     - `should_cache(request_body)`: 判断是否应该缓存
     - `generate_key(request_body)`: 生成 cache key
     - `normalize_messages(messages)`: 标准化 messages

5. **实现核心缓存服务**
   - 文件: `backend/app/services/cache_service.py`
   - 类: `CacheService`
   - 方法:
     - `get_cached_response(cache_key)`: 查询缓存
     - `save_response(cache_key, response, ttl)`: 保存缓存
     - `_get_from_redis(cache_key)`: Redis 查询
     - `_get_from_memory(cache_key)`: 内存查询
     - `_save_to_redis(cache_key, data, ttl)`: Redis 保存
     - `_save_to_memory(cache_key, data)`: 内存保存（LRU）

6. **实现缓存统计服务**
   - 文件: `backend/app/services/cache_stats_service.py`
   - 类: `CacheStatsService`
   - 方法:
     - `record_cache_hit(user_id, saved_tokens, saved_cost)`: 记录命中
     - `record_cache_miss(user_id)`: 记录未命中
     - `get_user_stats(user_id, date_range)`: 获取用户统计
     - `update_user_cache_stats(user_id)`: 更新用户表统计

7. **集成到 ProxyService**
   - 文件: `backend/app/services/proxy_service.py`
   - 修改 `forward_request()` 方法:
     - 在调用上游前检查缓存
     - 在返回响应后保存缓存
     - 添加 `X-Cache-Status` 响应头
     - 记录缓存日志

### Phase 3: API 和管理功能（3 步）
8. **创建缓存管理 API**
   - 文件: `backend/app/api/v1/cache.py`
   - 端点:
     - `GET /api/v1/cache/stats`: 获取缓存统计
     - `DELETE /api/v1/cache/clear`: 清空用户缓存
     - `PUT /api/v1/cache/config`: 更新缓存配置

9. **更新用户配置 API**
   - 文件: `backend/app/api/v1/user.py`
   - 修改 `update_user()`: 支持更新 `enable_cache` 字段
   - 修改 `get_user_info()`: 返回缓存统计信息

10. **前端缓存统计页面**
    - 文件: `frontend/src/views/cache/CacheStats.vue`
    - 功能:
      - 展示缓存命中率、节省 tokens、节省费用
      - 图表展示缓存趋势
      - 缓存开关控制
      - 清空缓存按钮

### Phase 4: 测试和优化（5 步）
11. **单元测试**
    - 文件: `backend/tests/test_cache_service.py`
    - 测试用例:
      - Cache Key 生成一致性
      - 缓存命中/未命中逻辑
      - Redis 降级到内存缓存
      - TTL 过期处理

12. **集成测试**
    - 文件: `backend/tests/test_proxy_with_cache.py`
    - 测试场景:
      - 相同请求第二次命中缓存
      - 不同 temperature 不命中缓存
      - 流式请求跳过缓存
      - X-No-Cache 头生效

13. **性能测试**
    - 工具: Locust 或 Apache Bench
    - 指标:
      - 缓存命中时响应时间 < 50ms
      - Redis 查询延迟 < 10ms
      - 内存缓存命中率 > 80%

14. **监控和日志**
    - 添加日志记录:
      - 缓存命中/未命中日志
      - Redis 连接异常日志
      - 缓存淘汰日志
    - Prometheus 指标（可选）:
      - `cache_hit_total`
      - `cache_miss_total`
      - `cache_saved_tokens_total`

15. **文档编写**
    - 文件: `docs/cache-system.md`
    - 内容:
      - 缓存机制说明
      - 配置参数说明
      - API 使用示例
      - 故障排查指南

---

## 5. 配置参数

### 5.1 环境变量（.env）
```bash
# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_MAX_CONNECTIONS=10

# 缓存配置
CACHE_ENABLED=true                    # 全局缓存开关
CACHE_DEFAULT_TTL=3600                # 默认缓存时长（秒）
CACHE_MIN_PROMPT_TOKENS=1000          # 最小缓存阈值
CACHE_MAX_MEMORY_SIZE=1000            # 内存缓存最大条数
CACHE_MAX_REDIS_SIZE=10000            # Redis 缓存最大条数
```

### 5.2 数据库配置
```python
# backend/app/models/user.py
class User(Base):
    # ... 现有字段
    enable_cache: Mapped[bool] = mapped_column(default=True)
    cache_hit_count: Mapped[int] = mapped_column(default=0)
    cache_saved_tokens: Mapped[int] = mapped_column(default=0)
```

---

## 6. 风险评估与应对

### 6.1 质量风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 缓存过期内容 | 用户获得过时响应 | 设置合理 TTL（1 小时），提供强制刷新机制 |
| 参数差异导致错误命中 | 不同请求返回相同响应 | 严格的 Cache Key 生成算法，仅包含核心参数 |
| 随机性参数被缓存 | 用户期望随机但得到固定响应 | 黑名单机制，temperature > 0 时不缓存 |

### 6.2 性能风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Redis 连接失败 | 缓存服务不可用 | 自动降级到内存缓存，记录异常日志 |
| 内存缓存占用过高 | 服务器内存不足 | LRU 淘汰策略，限制最大条数 1000 |
| 缓存穿透 | 大量请求打到上游 | 布隆过滤器（可选），缓存空结果 |

### 6.3 成本风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 缓存命中率低 | Redis 成本浪费 | 监控命中率，低于 20% 时调整策略 |
| 缓存大量无用内容 | 存储成本高 | 最小 tokens 阈值，定期清理过期数据 |

---

## 7. 成功指标

### 7.1 性能指标
- 缓存命中率 > 30%（第一周）
- 缓存命中率 > 50%（稳定后）
- 缓存响应时间 < 50ms
- Redis 可用性 > 99.9%

### 7.2 成本指标
- 每用户平均节省 tokens > 10000/天
- 每用户平均节省费用 > $0.5/天
- 缓存存储成本 < 节省费用的 10%

### 7.3 质量指标
- 用户投诉缓存错误 = 0
- 缓存相关 bug < 2 个/月
- 缓存服务可用性 > 99.5%

---

## 8. 实施时间表

| 阶段 | 步骤 | 预计时间 |
|------|------|----------|
| Phase 1 | 步骤 1-3 | 2 小时 |
| Phase 2 | 步骤 4-7 | 4 小时 |
| Phase 3 | 步骤 8-10 | 3 小时 |
| Phase 4 | 步骤 11-15 | 3 小时 |
| **总计** | **15 步** | **12 小时** |

---

## 9. 后续优化方向

1. **智能缓存预热**: 分析高频请求，提前缓存热点内容
2. **分布式缓存**: 多实例部署时使用 Redis Cluster
3. **缓存压缩**: 对大响应体进行 gzip 压缩
4. **语义缓存**: 使用向量相似度匹配语义相近的请求
5. **A/B 测试**: 对比缓存开启前后的用户满意度

---

## 10. 附录

### 10.1 关键代码示例

#### Cache Key 生成
```python
def generate_cache_key(request_body: dict) -> str:
    cache_components = {
        "model": request_body.get("model"),
        "messages": normalize_messages(request_body.get("messages", [])),
        "max_tokens": request_body.get("max_tokens")
    }
    cache_str = json.dumps(cache_components, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cache_str.encode()).hexdigest()
```

#### 缓存条件判断
```python
def should_cache(request_body: dict, headers: dict) -> bool:
    # 检查请求头
    if headers.get("X-No-Cache") == "true":
        return False

    # 检查流式请求
    if request_body.get("stream") is True:
        return False

    # 检查随机性参数
    if request_body.get("temperature", 0) > 0:
        return False

    # 检查函数调用
    if "tools" in request_body or "tool_choice" in request_body:
        return False

    # 检查 tokens 阈值
    estimated_tokens = estimate_tokens(request_body.get("messages", []))
    if estimated_tokens < 1000:
        return False

    return True
```

### 10.2 数据库索引优化
```sql
-- 缓存日志表索引
CREATE INDEX idx_cache_log_user_status ON cache_log(user_id, cache_status);
CREATE INDEX idx_cache_log_created_at ON cache_log(created_at);

-- 用户表索引
CREATE INDEX idx_user_enable_cache ON user(enable_cache);
```

---

**Plan 版本**: v1.0
**最后更新**: 2026-03-21
**待 Codex 评估**: ✅
