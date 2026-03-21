# AI 请求缓存系统 - 详细设计方案 v2

**创建时间**: 2026-03-21
**任务类型**: 大型（预计 15+ 步骤）
**核心目标**: 在代理层实现智能缓存机制，提高 AI 调用速度，同时确保不影响调用质量
**版本**: v2.0（根据 Codex 评估反馈修改）

---

## 📋 v2 版本修改说明

根据 Codex 评估报告（`codex-review-plan-v1-20260321.md`），本版本修复了以下 4 个关键问题：

1. ✅ **Cache Key 生成算法增强**：添加 `stop`、`response_format`、`top_k`、`seed` 参数
2. ✅ **messages 标准化增强**：添加 Unicode 标准化和空白字符处理
3. ✅ **缓存条件判断完善**：添加 `top_p`、`presence_penalty`、`frequency_penalty` 检查
4. ✅ **Redis 降级策略明确**：采用"不降级"方案，避免多实例数据不一致

---

## 1. 核心设计原则

### 1.1 缓存策略
- **缓存粒度**: 基于请求内容（messages + model + 关键参数）生成唯一 hash
- **缓存条件**（已增强）:
  - 仅缓存 `messages` 内容
  - 仅缓存确定性请求（`temperature=0` 且无其他随机性参数）
  - 排除 `stream=true` 的流式请求
  - 排除包含 `tools`/`functions` 的函数调用请求
  - 排除包含随机性参数的请求（`top_p`、`presence_penalty`、`frequency_penalty`）
- **缓存时效**: 默认 1 小时，可配置
- **缓存存储**: 仅使用 Redis（不降级到内存缓存）

### 1.2 质量保障机制（已增强）
- **参数白名单**（扩展）:
  - 必须参与 cache key 计算的参数：
    - `model`: 模型名称
    - `messages`: 对话内容
    - `max_tokens`: 最大生成长度
    - `stop`: 停止序列（影响生成结果）
    - `response_format`: 响应格式（如 JSON mode）
    - `top_k`: 采样参数（影响生成结果）
    - `seed`: 随机种子（某些模型支持）

- **参数黑名单**（扩展）: 以下参数存在时不缓存
  - `temperature > 0`: 随机性参数
  - `top_p != 1.0 且 != None`: 核采样参数
  - `presence_penalty != 0`: 存在惩罚
  - `frequency_penalty != 0`: 频率惩罚
  - `stream = true`: 流式请求
  - `tools` 或 `tool_choice`: 函数调用
  - `functions` 或 `function_call`: 旧版函数调用

- **用户控制**:
  - 用户级缓存开关：`user.enable_cache`
  - 请求头 `X-No-Cache: true` 强制跳过缓存
  - 请求头 `X-Cache-TTL: 3600` 自定义缓存时长

- **缓存标识**: 响应头返回 `X-Cache-Status: HIT/MISS/BYPASS`

### 1.3 成本优化
- **最小缓存阈值**: 仅缓存 prompt tokens > 1000 的请求
- **缓存收益计算**: 记录缓存命中节省的 tokens 和费用
- **Redis 容量控制**: 使用 Redis 的 LRU 淘汰策略，限制最大条数 10000

---

## 2. 技术架构设计

### 2.1 模块划分
```
backend/app/services/
├── cache_service.py          # 核心缓存服务（仅 Redis）
├── cache_key_generator.py    # Cache Key 生成器（增强版）
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
    INDEX idx_created_at (created_at),
    INDEX idx_user_status (user_id, cache_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='缓存日志表';

-- 用户表新增字段
ALTER TABLE user
ADD COLUMN enable_cache TINYINT DEFAULT 1 COMMENT '是否启用缓存（1=启用，0=禁用）',
ADD COLUMN cache_hit_count INT DEFAULT 0 COMMENT '缓存命中次数',
ADD COLUMN cache_saved_tokens BIGINT DEFAULT 0 COMMENT '累计节省 Tokens',
ADD INDEX idx_enable_cache (enable_cache);
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

# 缓存统计（每日聚合）
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

2. API Key 验证（现有逻辑）
   └─ 获取 user 对象

3. 检查缓存开关
   ├─ 全局缓存开关关闭 → 跳过缓存
   ├─ 用户禁用缓存 (user.enable_cache=False) → 跳过缓存
   ├─ 请求头 X-No-Cache=true → 跳过缓存
   └─ 继续

4. 检查缓存条件（增强版）
   ├─ stream=true → 跳过缓存
   ├─ temperature > 0 → 跳过缓存
   ├─ top_p != 1.0 且 != None → 跳过缓存
   ├─ presence_penalty != 0 → 跳过缓存
   ├─ frequency_penalty != 0 → 跳过缓存
   ├─ 包含 tools/functions → 跳过缓存
   ├─ prompt_tokens < 1000 → 跳过缓存
   └─ 继续

5. 生成 Cache Key（增强版）
   └─ SHA256(model + messages + max_tokens + stop + response_format + top_k + seed)

6. 查询 Redis 缓存
   ├─ 命中 → 返回缓存响应 + 记录统计 + 添加 X-Cache-Status: HIT
   └─ 未命中 → 继续

7. 模型解析（现有逻辑）
   └─ resolved_model

8. 渠道选择（现有逻辑）
   └─ channel

9. 调用上游 API（现有逻辑）
   └─ response

10. 保存响应到 Redis 缓存
    └─ 设置 TTL

11. 记录缓存日志（异步）
    └─ cache_status = MISS

12. 计费（现有逻辑）

13. 返回响应（添加 X-Cache-Status: MISS）
```

### 3.2 Cache Key 生成算法（增强版）
```python
import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional

def normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    标准化 messages，确保相同语义的内容生成相同的 cache key
    """
    normalized = []

    for msg in messages:
        normalized_msg = {"role": msg["role"]}

        # 标准化 content
        if isinstance(msg.get("content"), str):
            content = msg["content"]
            # Unicode 标准化（全角/半角统一）
            content = unicodedata.normalize("NFKC", content)
            # 移除多余空白字符（连续空格、Tab、换行）
            content = re.sub(r'\s+', ' ', content).strip()
            normalized_msg["content"] = content
        elif isinstance(msg.get("content"), list):
            # 多模态内容（图片等）直接保留
            normalized_msg["content"] = msg["content"]

        # 保留 name 字段（某些 API 支持）
        if "name" in msg:
            normalized_msg["name"] = msg["name"]

        normalized.append(normalized_msg)

    return normalized


def generate_cache_key(request_body: Dict[str, Any]) -> str:
    """
    生成缓存键，包含所有影响响应内容的参数
    """
    cache_components = {
        "model": request_body.get("model"),
        "messages": normalize_messages(request_body.get("messages", [])),
        "max_tokens": request_body.get("max_tokens"),
        "stop": request_body.get("stop"),
        "response_format": request_body.get("response_format"),
        "top_k": request_body.get("top_k"),
        "seed": request_body.get("seed")
    }

    # 移除 None 值（避免 None 和未设置的差异）
    cache_components = {
        k: v for k, v in cache_components.items()
        if v is not None
    }

    # 生成 SHA256 hash
    cache_str = json.dumps(cache_components, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cache_str.encode()).hexdigest()
```

### 3.3 缓存条件判断（增强版）
```python
import os
from typing import Dict, Any

def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    估算 prompt tokens（简单实现：字符数 / 4）
    """
    total_chars = sum(
        len(msg.get("content", ""))
        for msg in messages
        if isinstance(msg.get("content"), str)
    )
    return total_chars // 4


def should_cache(
    request_body: Dict[str, Any],
    headers: Dict[str, str],
    user: Any
) -> bool:
    """
    判断请求是否应该缓存（增强版）
    """
    # 1. 检查用户缓存开关
    if not user.enable_cache:
        return False

    # 2. 检查请求头
    if headers.get("X-No-Cache") == "true":
        return False

    # 3. 检查流式请求
    if request_body.get("stream") is True:
        return False

    # 4. 检查随机性参数（严格检查）
    if request_body.get("temperature", 0) > 0:
        return False

    top_p = request_body.get("top_p")
    if top_p is not None and top_p != 1.0:
        return False

    if request_body.get("presence_penalty", 0) != 0:
        return False

    if request_body.get("frequency_penalty", 0) != 0:
        return False

    # 5. 检查函数调用
    if "tools" in request_body or "tool_choice" in request_body:
        return False

    if "functions" in request_body or "function_call" in request_body:
        return False

    # 6. 检查 tokens 阈值
    estimated_tokens = estimate_tokens(request_body.get("messages", []))
    min_tokens = int(os.getenv("CACHE_MIN_PROMPT_TOKENS", 1000))
    if estimated_tokens < min_tokens:
        return False

    return True
```

---

## 4. 详细实现步骤

### Phase 1: 基础设施搭建（3 步）

#### 步骤 1: 创建 Redis 客户端封装
- **文件**: `backend/app/core/redis_client.py`
- **功能**:
  - 连接池管理（最大连接数 10）
  - 异常处理（连接失败时记录日志）
  - **不降级到内存缓存**（避免多实例数据不一致）
- **配置**: 从环境变量读取 Redis 连接信息
- **关键代码**:
  ```python
  import redis
  from redis.connection import ConnectionPool
  import logging

  logger = logging.getLogger(__name__)

  class RedisClient:
      def __init__(self):
          self.pool = ConnectionPool(
              host=os.getenv("REDIS_HOST", "localhost"),
              port=int(os.getenv("REDIS_PORT", 6379)),
              password=os.getenv("REDIS_PASSWORD", None),
              db=int(os.getenv("REDIS_DB", 0)),
              max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", 10)),
              decode_responses=True
          )
          self.client = redis.Redis(connection_pool=self.pool)

      def get(self, key: str) -> Optional[str]:
          try:
              return self.client.get(key)
          except redis.ConnectionError as e:
              logger.error(f"Redis connection failed: {e}")
              return None  # 不降级，直接返回 None

      def set(self, key: str, value: str, ex: int = 3600) -> bool:
          try:
              return self.client.set(key, value, ex=ex)
          except redis.ConnectionError as e:
              logger.error(f"Redis connection failed: {e}")
              return False

      def delete(self, key: str) -> bool:
          try:
              return self.client.delete(key) > 0
          except redis.ConnectionError as e:
              logger.error(f"Redis connection failed: {e}")
              return False
  ```

#### 步骤 2: 创建数据库表
- **执行 SQL**: 创建 `cache_log` 表
- **修改 `user` 表**: 添加缓存相关字段
- **更新 `sql/init.sql`**: 添加建表语句
- **迁移脚本**: `sql/migrations/add_cache_tables.sql`

#### 步骤 3: 创建缓存日志模型
- **文件**: `backend/app/models/cache_log.py`
- **字段**: 对应数据库表结构
- **关系**: 关联 `user` 表
- **关键代码**:
  ```python
  from sqlalchemy import Column, Integer, String, Enum, DECIMAL, DateTime, BigInteger, ForeignKey
  from sqlalchemy.orm import relationship
  from app.models.base import Base
  import enum

  class CacheStatus(str, enum.Enum):
      HIT = "HIT"
      MISS = "MISS"
      BYPASS = "BYPASS"

  class CacheLog(Base):
      __tablename__ = "cache_log"

      id = Column(BigInteger, primary_key=True, autoincrement=True)
      cache_key = Column(String(64), nullable=False, index=True)
      user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
      model = Column(String(100), nullable=False)
      prompt_tokens = Column(Integer, nullable=False)
      completion_tokens = Column(Integer, nullable=False)
      cache_status = Column(Enum(CacheStatus), nullable=False)
      saved_tokens = Column(Integer, default=0)
      saved_cost = Column(DECIMAL(10, 6), default=0)
      ttl = Column(Integer, nullable=False)
      created_at = Column(DateTime, nullable=False, index=True)

      # 关系
      user = relationship("User", back_populates="cache_logs")
  ```

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
CACHE_MAX_REDIS_SIZE=10000            # Redis 缓存最大条数
```

### 5.2 数据库配置
```python
# backend/app/models/user.py
from sqlalchemy import Column, Integer, Boolean, BigInteger

class User(Base):
    # ... 现有字段
    enable_cache = Column(Boolean, default=True, index=True)
    cache_hit_count = Column(Integer, default=0)
    cache_saved_tokens = Column(BigInteger, default=0)

    # 关系
    cache_logs = relationship("CacheLog", back_populates="user")
```

---

## 6. 风险评估与应对

### 6.1 质量风险（已降低）
| 风险 | 影响 | 应对措施 | 状态 |
|------|------|----------|------|
| 缓存过期内容 | 用户获得过时响应 | 设置合理 TTL（1 小时），提供强制刷新机制 | ✅ 已实施 |
| 参数差异导致错误命中 | 不同请求返回相同响应 | **增强 Cache Key 算法，包含所有影响响应的参数** | ✅ 已修复 |
| 随机性参数被缓存 | 用户期望随机但得到固定响应 | **严格检查所有随机性参数** | ✅ 已修复 |

### 6.2 性能风险（已优化）
| 风险 | 影响 | 应对措施 | 状态 |
|------|------|----------|------|
| Redis 连接失败 | 缓存服务不可用 | **不降级，直接跳过缓存，记录异常日志** | ✅ 已修复 |
| 缓存穿透 | 大量请求打到上游 | 可选：使用分布式锁（Phase 4 优化） | 🔄 待优化 |

### 6.3 成本风险
| 风险 | 影响 | 应对措施 | 状态 |
|------|------|----------|------|
| 缓存命中率低 | Redis 成本浪费 | 监控命中率，低于 20% 时调整策略 | ✅ 已实施 |
| 缓存大量无用内容 | 存储成本高 | 最小 tokens 阈值，Redis LRU 淘汰 | ✅ 已实施 |

---

### Phase 2: 核心缓存服务（4 步）

#### 步骤 4: 实现 Cache Key 生成器（增强版）
- **文件**: `backend/app/services/cache_key_generator.py`
- **类**: `CacheKeyGenerator`
- **方法**:
  - `should_cache(request_body, headers, user)`: 判断是否应该缓存（增强版）
  - `generate_key(request_body)`: 生成 cache key（增强版）
  - `normalize_messages(messages)`: 标准化 messages（增强版）
  - `estimate_tokens(messages)`: 估算 prompt tokens
- **关键改进**:
  - ✅ 添加 `stop`、`response_format`、`top_k`、`seed` 参数到 cache key
  - ✅ Unicode 标准化（NFKC）
  - ✅ 多余空白字符处理
  - ✅ 严格检查所有随机性参数

#### 步骤 5: 实现核心缓存服务（仅 Redis）
- **文件**: `backend/app/services/cache_service.py`
- **类**: `CacheService`
- **方法**:
  - `get_cached_response(cache_key)`: 查询 Redis 缓存
  - `save_response(cache_key, response, ttl)`: 保存到 Redis
  - `clear_user_cache(user_id)`: 清空用户缓存
- **关键代码**:
  ```python
  import json
  from typing import Optional, Dict, Any
  from app.core.redis_client import RedisClient
  import logging

  logger = logging.getLogger(__name__)

  class CacheService:
      def __init__(self, redis_client: RedisClient):
          self.redis = redis_client

      async def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
          """查询 Redis 缓存"""
          try:
              cached_data = self.redis.get(f"cache:content:{cache_key}")
              if cached_data:
                  return json.loads(cached_data)
              return None
          except Exception as e:
              logger.error(f"Failed to get cache: {e}")
              return None

      async def save_response(
          self,
          cache_key: str,
          response: Dict[str, Any],
          ttl: int = 3600
      ) -> bool:
          """保存响应到 Redis"""
          try:
              cache_data = {
                  "response": response,
                  "model": response.get("model"),
                  "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                  "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                  "created_at": int(time.time())
              }
              return self.redis.set(
                  f"cache:content:{cache_key}",
                  json.dumps(cache_data),
                  ex=ttl
              )
          except Exception as e:
              logger.error(f"Failed to save cache: {e}")
              return False

      async def clear_user_cache(self, user_id: int) -> int:
          """清空用户的所有缓存"""
          # 注意：需要维护用户的 cache_key 列表，或使用 Redis SCAN
          # 这里简化实现，实际需要在保存缓存时记录 user_id -> cache_keys 映射
          pass
  ```

#### 步骤 6: 实现缓存统计服务
- **文件**: `backend/app/services/cache_stats_service.py`
- **类**: `CacheStatsService`
- **方法**:
  - `record_cache_hit(user_id, cache_key, saved_tokens, saved_cost)`: 记录命中
  - `record_cache_miss(user_id, cache_key)`: 记录未命中
  - `get_user_stats(user_id, start_date, end_date)`: 获取用户统计
  - `update_user_cache_stats(user_id)`: 更新用户表统计
- **关键代码**:
  ```python
  from datetime import datetime
  from sqlalchemy.ext.asyncio import AsyncSession
  from app.models.cache_log import CacheLog, CacheStatus
  from app.models.user import User
  from sqlalchemy import select, update

  class CacheStatsService:
      def __init__(self, db: AsyncSession, redis_client: RedisClient):
          self.db = db
          self.redis = redis_client

      async def record_cache_hit(
          self,
          user_id: int,
          cache_key: str,
          model: str,
          prompt_tokens: int,
          completion_tokens: int,
          saved_tokens: int,
          saved_cost: float,
          ttl: int
      ):
          """记录缓存命中（修复：添加事务处理）"""
          try:
              # 1. 写入数据库日志
              cache_log = CacheLog(
                  cache_key=cache_key,
                  user_id=user_id,
                  model=model,
                  prompt_tokens=prompt_tokens,
                  completion_tokens=completion_tokens,
                  cache_status=CacheStatus.HIT,
                  saved_tokens=saved_tokens,
                  saved_cost=saved_cost,
                  ttl=ttl,
                  created_at=datetime.now()
              )
              self.db.add(cache_log)

              # 2. 更新用户表统计
              await self.db.execute(
                  update(User)
                  .where(User.id == user_id)
                  .values(
                      cache_hit_count=User.cache_hit_count + 1,
                      cache_saved_tokens=User.cache_saved_tokens + saved_tokens
                  )
              )

              # 3. 提交事务
              await self.db.commit()

              # 4. 更新 Redis 统计（事务成功后）
              today = datetime.now().strftime("%Y-%m-%d")
              stats_key = f"cache:stats:{user_id}:{today}"
              self.redis.client.hincrby(stats_key, "hit_count", 1)
              self.redis.client.hincrbyfloat(stats_key, "saved_tokens", saved_tokens)
              self.redis.client.hincrbyfloat(stats_key, "saved_cost", saved_cost)
              self.redis.client.expire(stats_key, 30 * 24 * 3600)  # 30 天

          except Exception as e:
              await self.db.rollback()
              logger.error(f"Failed to record cache hit: {e}")

      async def record_cache_miss(
          self,
          user_id: int,
          cache_key: str,
          model: str,
          prompt_tokens: int,
          completion_tokens: int,
          ttl: int
      ):
          """记录缓存未命中"""
          cache_log = CacheLog(
              cache_key=cache_key,
              user_id=user_id,
              model=model,
              prompt_tokens=prompt_tokens,
              completion_tokens=completion_tokens,
              cache_status=CacheStatus.MISS,
              saved_tokens=0,
              saved_cost=0,
              ttl=ttl,
              created_at=datetime.now()
          )
          self.db.add(cache_log)

          # 更新 Redis 统计
          today = datetime.now().strftime("%Y-%m-%d")
          stats_key = f"cache:stats:{user_id}:{today}"
          self.redis.client.hincrby(stats_key, "miss_count", 1)
  ```

#### 步骤 7: 集成到 ProxyService
- **文件**: `backend/app/services/proxy_service.py`
- **修改**: `forward_request()` 方法
- **集成点**:
  ```python
  async def forward_request(
      self,
      api_key: str,
      request_body: dict,
      headers: dict
  ) -> dict:
      # 1. API Key 验证（现有逻辑）
      user = await self._verify_api_key(api_key)

      # 2. 检查缓存（新增，添加异常处理）
      cache_key = None
      try:
          if cache_key_generator.should_cache(request_body, headers, user):
              cache_key = cache_key_generator.generate_key(request_body)
              cached_response = await cache_service.get_cached_response(cache_key)

              if cached_response:
                  # 缓存命中
                  response = cached_response["response"]

                  # 记录统计
                  await cache_stats_service.record_cache_hit(
                      user_id=user.id,
                      cache_key=cache_key,
                      model=cached_response["model"],
                      prompt_tokens=cached_response["prompt_tokens"],
                      completion_tokens=cached_response["completion_tokens"],
                      saved_tokens=cached_response["prompt_tokens"] + cached_response["completion_tokens"],
                      saved_cost=self._calculate_cost(...),
                      ttl=3600
                  )

                  # 添加响应头
                  response["_cache_status"] = "HIT"
                  return response
      except Exception as e:
          logger.warning(f"Cache check failed, bypassing cache: {e}")
          cache_key = None  # 确保后续不保存缓存

      # 3. 模型解析（现有逻辑）
      resolved_model = await self._resolve_model(...)

      # 4. 渠道选择（现有逻辑）
      channel = await self._select_channel(...)

      # 5. 上游转发（现有逻辑）
      response = await self._forward_to_upstream(...)

      # 6. 保存缓存（新增，添加异常处理）
      if cache_key:
          try:
              ttl = int(headers.get("X-Cache-TTL", 3600))
              await cache_service.save_response(cache_key, response, ttl)

              # 记录统计
              await cache_stats_service.record_cache_miss(
                  user_id=user.id,
                  cache_key=cache_key,
                  model=response.get("model"),
                  prompt_tokens=response.get("usage", {}).get("prompt_tokens", 0),
                  completion_tokens=response.get("usage", {}).get("completion_tokens", 0),
                  ttl=ttl
              )
          except Exception as e:
              logger.warning(f"Failed to save cache, continuing: {e}")

      # 7. 计费（现有逻辑）
      await self._bill_tokens(...)

      # 8. 添加响应头
      response["_cache_status"] = "MISS" if cache_key else "BYPASS"
      return response
  ```

---

### Phase 3: API 和管理功能（3 步）

#### 步骤 8: 创建缓存管理 API
- **文件**: `backend/app/api/v1/cache.py`
- **端点**:
  ```python
  from fastapi import APIRouter, Depends
  from app.core.deps import get_current_user
  from app.services.cache_service import CacheService
  from app.services.cache_stats_service import CacheStatsService

  router = APIRouter(prefix="/cache", tags=["cache"])

  @router.get("/stats")
  async def get_cache_stats(
      start_date: str = None,
      end_date: str = None,
      current_user: User = Depends(get_current_user)
  ):
      """获取缓存统计"""
      stats = await cache_stats_service.get_user_stats(
          user_id=current_user.id,
          start_date=start_date,
          end_date=end_date
      )
      return {
          "hit_count": stats["hit_count"],
          "miss_count": stats["miss_count"],
          "hit_rate": stats["hit_count"] / (stats["hit_count"] + stats["miss_count"]),
          "saved_tokens": stats["saved_tokens"],
          "saved_cost": stats["saved_cost"]
      }

  @router.delete("/clear")
  async def clear_cache(
      current_user: User = Depends(get_current_user)
  ):
      """清空用户缓存"""
      count = await cache_service.clear_user_cache(current_user.id)
      return {"message": f"Cleared {count} cache entries"}

  @router.put("/config")
  async def update_cache_config(
      enable_cache: bool,
      current_user: User = Depends(get_current_user)
  ):
      """更新缓存配置"""
      await db.execute(
          update(User)
          .where(User.id == current_user.id)
          .values(enable_cache=enable_cache)
      )

      # 如果禁用缓存，清空已有缓存
      if not enable_cache:
          await cache_service.clear_user_cache(current_user.id)

      return {"message": "Cache config updated"}
  ```

#### 步骤 9: 更新用户配置 API
- **文件**: `backend/app/api/v1/user.py`
- **修改**: 添加缓存相关字段到响应
- **关键代码**:
  ```python
  @router.get("/info")
  async def get_user_info(current_user: User = Depends(get_current_user)):
      return {
          "id": current_user.id,
          "username": current_user.username,
          # ... 现有字段
          "enable_cache": current_user.enable_cache,
          "cache_hit_count": current_user.cache_hit_count,
          "cache_saved_tokens": current_user.cache_saved_tokens
      }

  @router.put("/update")
  async def update_user(
      enable_cache: bool = None,
      # ... 其他字段
      current_user: User = Depends(get_current_user)
  ):
      update_data = {}
      if enable_cache is not None:
          update_data["enable_cache"] = enable_cache

      # 更新用户
      await db.execute(
          update(User)
          .where(User.id == current_user.id)
          .values(**update_data)
      )

      return {"message": "User updated"}
  ```

#### 步骤 10: 前端缓存统计页面
- **文件**: `frontend/src/views/cache/CacheStats.vue`
- **功能**:
  - 展示缓存命中率、节省 tokens、节省费用
  - 图表展示缓存趋势（使用 ECharts）
  - 缓存开关控制
  - 清空缓存按钮
- **关键组件**:
  ```vue
  <template>
    <div class="cache-stats">
      <a-card title="缓存统计">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic title="缓存命中率" :value="hitRate" suffix="%" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="节省 Tokens" :value="savedTokens" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="节省费用" :value="savedCost" prefix="$" />
          </a-col>
          <a-col :span="6">
            <a-switch v-model="enableCache" @change="updateCacheConfig" />
            <span>缓存开关</span>
          </a-col>
        </a-row>

        <div class="chart-container">
          <div ref="chartRef" style="width: 100%; height: 400px;"></div>
        </div>

        <a-button type="danger" @click="clearCache">清空缓存</a-button>
      </a-card>
    </div>
  </template>

  <script>
  import * as echarts from 'echarts'
  import { getCacheStats, clearCache, updateCacheConfig } from '@/api/cache'

  export default {
    data() {
      return {
        hitRate: 0,
        savedTokens: 0,
        savedCost: 0,
        enableCache: true
      }
    },
    mounted() {
      this.loadStats()
      this.initChart()
    },
    methods: {
      async loadStats() {
        const res = await getCacheStats()
        this.hitRate = (res.hit_rate * 100).toFixed(2)
        this.savedTokens = res.saved_tokens
        this.savedCost = res.saved_cost.toFixed(4)
      },
      initChart() {
        const chart = echarts.init(this.$refs.chartRef)
        // 配置图表...
      },
      async clearCache() {
        await clearCache()
        this.$message.success('缓存已清空')
        this.loadStats()
      },
      async updateCacheConfig() {
        await updateCacheConfig({ enable_cache: this.enableCache })
        this.$message.success('配置已更新')
      }
    }
  }
  </script>
  ```

---

### Phase 4: 测试和优化（5 步）

#### 步骤 11: 单元测试
- **文件**: `backend/tests/test_cache_service.py`
- **测试用例**:
  ```python
  import pytest
  from app.services.cache_key_generator import CacheKeyGenerator, normalize_messages, generate_cache_key

  def test_cache_key_consistency():
      """测试相同请求生成相同 cache key"""
      request1 = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}],
          "max_tokens": 100
      }
      request2 = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}],
          "max_tokens": 100
      }
      assert generate_cache_key(request1) == generate_cache_key(request2)

  def test_cache_key_with_different_stop():
      """测试不同 stop 参数生成不同 cache key"""
      request1 = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}],
          "stop": ["\n"]
      }
      request2 = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}],
          "stop": ["\n\n"]
      }
      assert generate_cache_key(request1) != generate_cache_key(request2)

  def test_normalize_messages_unicode():
      """测试 Unicode 标准化"""
      messages1 = [{"role": "user", "content": "Hello　World"}]  # 全角空格
      messages2 = [{"role": "user", "content": "Hello World"}]   # 半角空格
      assert normalize_messages(messages1) == normalize_messages(messages2)

  def test_should_cache_with_temperature():
      """测试 temperature > 0 不缓存"""
      request = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}],
          "temperature": 0.7
      }
      user = MockUser(enable_cache=True)
      assert not should_cache(request, {}, user)
  ```

#### 步骤 12: 集成测试
- **文件**: `backend/tests/test_proxy_with_cache.py`
- **测试场景**:
  ```python
  @pytest.mark.asyncio
  async def test_cache_hit_on_second_request():
      """测试第二次请求命中缓存"""
      request_body = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}]
      }

      # 第一次请求
      response1 = await proxy_service.forward_request(api_key, request_body, {})
      assert response1["_cache_status"] == "MISS"

      # 第二次请求
      response2 = await proxy_service.forward_request(api_key, request_body, {})
      assert response2["_cache_status"] == "HIT"
      assert response1["id"] == response2["id"]  # 相同响应

  @pytest.mark.asyncio
  async def test_no_cache_header():
      """测试 X-No-Cache 头生效"""
      request_body = {
          "model": "gpt-4",
          "messages": [{"role": "user", "content": "Hello"}]
      }
      headers = {"X-No-Cache": "true"}

      response = await proxy_service.forward_request(api_key, request_body, headers)
      assert response["_cache_status"] == "BYPASS"
  ```

#### 步骤 13: 性能测试
- **工具**: Locust
- **文件**: `backend/tests/locustfile.py`
- **测试脚本**:
  ```python
  from locust import HttpUser, task, between

  class CachePerformanceTest(HttpUser):
      wait_time = between(1, 2)

      @task
      def test_cached_request(self):
          """测试缓存命中性能"""
          self.client.post(
              "/v1/chat/completions",
              json={
                  "model": "gpt-4",
                  "messages": [{"role": "user", "content": "Hello"}]
              },
              headers={"Authorization": f"Bearer {API_KEY}"}
          )
  ```
- **性能指标**:
  - 缓存命中响应时间 < 50ms
  - Redis 查询延迟 < 10ms
  - 吞吐量 > 1000 req/s（缓存命中时）

#### 步骤 14: 监控和日志
- **日志配置**: `backend/app/core/logging_config.py`
- **日志内容**:
  ```python
  logger.info(f"Cache HIT: user={user_id}, key={cache_key[:8]}, saved_tokens={saved_tokens}")
  logger.info(f"Cache MISS: user={user_id}, key={cache_key[:8]}")
  logger.warning(f"Redis connection failed: {error}")
  logger.error(f"Cache service error: {error}")
  ```
- **监控指标**（可选 Prometheus）:
  ```python
  from prometheus_client import Counter, Histogram

  cache_hit_total = Counter('cache_hit_total', 'Total cache hits')
  cache_miss_total = Counter('cache_miss_total', 'Total cache misses')
  cache_saved_tokens_total = Counter('cache_saved_tokens_total', 'Total saved tokens')
  cache_response_time = Histogram('cache_response_time_seconds', 'Cache response time')
  ```

#### 步骤 15: 文档编写
- **文件**: `docs/cache-system.md`
- **内容大纲**:
  ```markdown
  # AI 请求缓存系统文档

  ## 1. 概述
  - 缓存机制说明
  - 适用场景
  - 性能提升预期

  ## 2. 使用指南
  ### 2.1 启用缓存
  - 用户级缓存开关
  - 请求级缓存控制

  ### 2.2 缓存策略
  - 哪些请求会被缓存
  - 哪些请求不会被缓存

  ### 2.3 自定义配置
  - X-No-Cache 头
  - X-Cache-TTL 头

  ## 3. API 参考
  - GET /api/v1/cache/stats
  - DELETE /api/v1/cache/clear
  - PUT /api/v1/cache/config

  ## 4. 配置参数
  - 环境变量说明
  - 默认值

  ## 5. 故障排查
  - Redis 连接失败
  - 缓存命中率低
  - 缓存数据不一致

  ## 6. 最佳实践
  - 何时使用缓存
  - 如何优化缓存命中率
  ```

---

## 7. 实施时间表

| 阶段 | 步骤 | 预计时间 | 依赖 |
|------|------|----------|------|
| Phase 1 | 步骤 1-3 | 2 小时 | 无 |
| Phase 2 | 步骤 4-7 | 4 小时 | Phase 1 完成 |
| Phase 3 | 步骤 8-10 | 3 小时 | Phase 2 完成 |
| Phase 4 | 步骤 11-15 | 3 小时 | Phase 3 完成 |
| **总计** | **15 步** | **12 小时** | - |

---

## 8. 成功指标

### 8.1 性能指标
- 缓存命中率 > 30%（第一周）
- 缓存命中率 > 50%（稳定后）
- 缓存响应时间 < 50ms
- Redis 可用性 > 99.9%

### 8.2 成本指标
- 每用户平均节省 tokens > 10000/天
- 每用户平均节省费用 > $0.5/天
- 缓存存储成本 < 节省费用的 10%

### 8.3 质量指标
- 用户投诉缓存错误 = 0
- 缓存相关 bug < 2 个/月
- 缓存服务可用性 > 99.5%

---

## 9. 回滚方案

### 9.1 紧急回滚
如果缓存系统出现严重问题，可以通过以下方式快速回滚：

1. **关闭全局缓存开关**:
   ```bash
   # 修改 .env
   CACHE_ENABLED=false
   # 重启服务
   ```

2. **代码回滚**:
   ```bash
   git revert <commit-hash>
   git push
   ```

3. **数据库回滚**:
   ```sql
   -- 删除缓存相关字段（如果需要）
   ALTER TABLE user DROP COLUMN enable_cache;
   ALTER TABLE user DROP COLUMN cache_hit_count;
   ALTER TABLE user DROP COLUMN cache_saved_tokens;
   DROP TABLE cache_log;
   ```

### 9.2 灰度发布
建议采用灰度发布策略：
1. 先对 10% 用户启用缓存
2. 监控 24 小时，检查错误率和性能
3. 逐步扩大到 50%、100%

---

## 10. 后续优化方向

1. **智能缓存预热**: 分析高频请求，提前缓存热点内容
2. **分布式缓存**: 多实例部署时使用 Redis Cluster
3. **缓存压缩**: 对大响应体进行 gzip 压缩
4. **语义缓存**: 使用向量相似度匹配语义相近的请求
5. **并发控制**: 使用分布式锁避免缓存穿透
6. **A/B 测试**: 对比缓存开启前后的用户满意度

---

**Plan 版本**: v2.0
**最后更新**: 2026-03-21
**Codex 评估状态**: 待重新评估
**修改内容**: 修复 4 个关键质量问题

---

## 📝 下一步

Plan v2 已完整设计完成，包含：
- ✅ Phase 1: 基础设施搭建（3 步）
- ✅ Phase 2: 核心缓存服务（4 步）
- ✅ Phase 3: API 和管理功能（3 步）
- ✅ Phase 4: 测试和优化（5 步）

现在需要提交 Codex 重新评估 v2 版本。
