# Codex Review: 流式缓存实施代码

**日期**: 2026-03-21
**Review 范围**:
- `app/middleware/stream_cache_middleware.py` (新建)
- `app/services/cache_service.py` (新增方法)
- `app/services/proxy_service.py` (修改三个流式方法)

---

## 1. Bug 列表

### BUG-01: `X-Cache-Status` header 始终为 "BYPASS"（Critical）

**文件**: `proxy_service.py` L1411-1420、L1721-1730、L785-794

**问题描述**: 三个流式方法（`_stream_openai_request`、`_stream_anthropic_request`、`_stream_responses_request`）都在方法末尾构造 `StreamingResponse`：

```python
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        ...
        "X-Cache-Status": cache_status,   # <-- 此时 cache_status 永远是 "BYPASS"
    },
)
```

`StreamingResponse` 在创建时立即读取 `cache_status` 的值构造 headers dict。但此时 `event_generator()` 尚未开始执行（它是惰性 async generator），所以：
- `cache_status` 的初始值是 `"BYPASS"`（L1273、L1585、L658）
- `upstream_call` 内部通过 `nonlocal cache_status` 将其修改为 `"MISS"`（仅在 `_stream_openai_request` 中做了，L1286-1287）
- `wrap_stream_request` 内部将其设置为 `"HIT"` 或 `"MISS"`，但这些修改发生在 generator 被消费时

**结果**: **客户端收到的 `X-Cache-Status` header 永远是 `"BYPASS"`**，无论实际是否命中缓存。

**影响**: 客户端（如前端 UI）无法通过 header 判断请求是否命中缓存，影响调试和用户体验。

**修复方案**: 由于 SSE 的 HTTP headers 在 body 发送前就已返回，无法在 generator 执行过程中修改。可选方案：
1. **在 SSE 流中注入 cache status 事件**（推荐）：在 `replay_cached_stream` 的第一个 chunk 前 yield 一个自定义 SSE 事件 `event: cache_status\ndata: {"status": "HIT"}\n\n`
2. **使用 `background` 参数或 middleware 方案**：先执行缓存查询，在返回 `StreamingResponse` 前确定 cache_status

---

### BUG-02: `upstream_call` 调用签名不一致 — BYPASS 分支参数不匹配（Critical）

**文件**: `stream_cache_middleware.py` L246、L278 vs L362

**问题描述**: `wrap_stream_request` 的 `upstream_call` 参数类型注解为：
```python
upstream_call: Callable[[], AsyncGenerator[str, None]]  # 无参数
```

但在代码中有两种调用方式：
- **BYPASS 分支**（L278）：`upstream_call()` — 无参数调用
- **MISS 分支**（L362）：`upstream_call(collector, collected_usage)` — 传入两个参数

而在 `proxy_service.py` 中，三个 `upstream_call` 的实际定义都接受两个参数：
```python
async def upstream_call(collector, collected_usage):  # 需要 2 个参数
```

**结果**: **当缓存被 BYPASS 时（L278），调用 `upstream_call()` 不传参数会导致 `TypeError: upstream_call() missing 2 required positional arguments`**。

这意味着所有 `_should_cache_stream` 返回 `False` 的请求都会报错崩溃。

**影响**: 严重的运行时错误。任何不满足缓存条件的流式请求（如 `temperature > 0`、用户关闭缓存、`CACHE_ENABLED=false`）都会失败。

**修复方案**:
```python
# 方案 A: BYPASS 分支也创建 dummy collector/usage
if not StreamCacheMiddleware._should_cache_stream(request_body, headers, user):
    logger.debug(f"Stream cache bypassed for user {user.id}")
    dummy_collector = StreamCollector()
    dummy_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    async for chunk in upstream_call(dummy_collector, dummy_usage):
        yield chunk
    return

# 方案 B (更优): 修改 upstream_call 使参数可选
async def upstream_call(collector=None, collected_usage=None):
    if collector is None:
        collector = StreamCollector()  # 丢弃
    if collected_usage is None:
        collected_usage = {}
    ...
```

---

### BUG-03: `billing_callback` 在缓存 BYPASS 分支未被调用（Major）

**文件**: `stream_cache_middleware.py` L276-280

**问题描述**: 当 `_should_cache_stream()` 返回 `False` 时，代码直接透传上游流：
```python
async for chunk in upstream_call():
    yield chunk
return
```

在这个分支中，**`billing_callback` 的调用依赖于 `upstream_call` 内部自行调用**（如 `proxy_service.py` L731、L1351、L1665）。

这部分目前是正确的——`upstream_call` 内部已经调用了 `billing_callback`。

但存在一个微妙的一致性问题：如果未来有人修改 `upstream_call` 移除内部的 `billing_callback` 调用（认为应该由 `wrap_stream_request` 统一处理），BYPASS 分支的计费就会丢失。

**当前状态**: 功能正确，但架构上 billing 的职责分散在两处，容易产生维护 bug。

**建议**: 在 `wrap_stream_request` 中统一管理 `billing_callback` 的调用时机，或在代码中添加明确注释说明 BYPASS 分支的 billing 由 `upstream_call` 内部负责。

---

### BUG-04: `CacheStatsService` 需要 `AsyncSession`，但传入的是同步 `Session`（Major）

**文件**: `stream_cache_middleware.py` L13、L307、L386 vs `cache_stats_service.py` L8、L20

**问题描述**:
- `CacheStatsService.__init__` 接受 `AsyncSession`（来自 `sqlalchemy.ext.asyncio`）
- `CacheStatsService.record_cache_hit` / `record_cache_miss` 内部使用 `await self.db.execute(...)` 和 `await self.db.commit()`
- 但 `stream_cache_middleware.py` 中的 `wrap_stream_request` 接受的 `db` 参数类型注解为 `Session`（同步 Session，来自 `sqlalchemy.orm`）
- 调用处 `proxy_service.py` 传入的也是 `db: Session`

**结果**: 如果传入的确实是同步 `Session` 对象：
- `await self.db.execute(...)` 会抛出 `TypeError`（同步 Session 不支持 await）
- `await self.db.commit()` 同样会失败
- **缓存统计记录会全部静默失败**（被外层 `try/except` 捕获后只打日志）

**影响**: 缓存命中/未命中统计不会写入数据库，用户看不到缓存统计数据。但不影响核心功能（缓存读写本身正常）。

**修复方案**: 确认 `db` 的实际运行时类型。如果整个项目使用 async SQLAlchemy，需要统一类型注解为 `AsyncSession`。如果是同步 Session，则 `CacheStatsService` 需要去掉 `await`。

---

### BUG-05: `clear_user_cache` 不会清除流式缓存（Minor）

**文件**: `cache_service.py` L93-129、L179

**问题描述**: `clear_user_cache` 遍历 `cache:user_keys:{user_id}` 集合中的 key，对每个 key 删除 `cache:content:{cache_key}`。

但流式缓存的 key 格式是 `cache:stream:{cache_key}`，而 `add_user_cache_key` 在保存流式缓存时传入的是 `f"stream:{cache_key}"`（L179）。

所以 `clear_user_cache` 遍历时会拿到 `"stream:abc123"` 这样的 key，然后拼接成 `"cache:content:stream:abc123"` 去删除——这个 key 在 Redis 中不存在。

**结果**: 用户调用"清空缓存"功能时，流式缓存不会被清除。

**修复方案**:
```python
async def clear_user_cache(self, user_id: int) -> int:
    ...
    for cache_key in cache_keys:
        # 判断是否是流式缓存 key
        if cache_key.startswith("stream:"):
            actual_key = f"cache:{cache_key}"  # -> cache:stream:xxx
        else:
            actual_key = f"cache:content:{cache_key}"
        if self.redis.delete(actual_key):
            count += 1
    ...
```

---

### BUG-06: Anthropic 缓存重放缺少 `message_start` 和 `message_delta` 事件（Major）

**文件**: `stream_cache_middleware.py` L125-146

**问题描述**: Anthropic 的完整 SSE 流格式包含多个事件类型：
```
event: message_start
data: {"type":"message_start","message":{"id":"...","model":"...","usage":{"input_tokens":N},...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":N}}

event: message_stop
data: {"type":"message_stop"}
```

但缓存重放 `_format_anthropic_sse` 只生成了 `content_block_delta` 和 `message_stop` 两种事件。缺少：
- `message_start`（包含 model、id、input usage 等元信息）
- `content_block_start` / `content_block_stop`
- `message_delta`（包含 stop_reason 和 output usage）

**结果**: 依赖完整 Anthropic 事件序列的客户端（如 Claude SDK）可能无法正确解析缓存重放的流。具体表现可能是：
- 客户端拿不到 `message.id`
- 客户端拿不到 `usage` 信息
- 某些客户端 SDK 会因缺少 `message_start` 事件而报错

**影响**: 部分 Anthropic SDK 客户端可能无法正确处理缓存重放的响应。

**修复方案**: 在 `replay_cached_stream` 开始时补发 `message_start`、`content_block_start` 事件，在结束时补发 `content_block_stop`、`message_delta` 事件。需要在 `StreamCollector` 中额外记录 model、usage 等元信息。

---

### BUG-07: Responses API 缓存重放缺少关键事件（Major）

**文件**: `stream_cache_middleware.py` L149-161

**问题描述**: Responses API 的完整 SSE 流也包含多个事件：
```
data: {"type":"response.created","response":{...}}
data: {"type":"response.in_progress",...}
data: {"type":"response.output_item.added",...}
data: {"type":"response.content_part.added",...}
data: {"type":"response.output_text.delta","delta":"Hello"}
data: {"type":"response.output_text.done",...}
data: {"type":"response.content_part.done",...}
data: {"type":"response.output_item.done",...}
data: {"type":"response.completed","response":{...}}
data: [DONE]
```

但 `_format_responses_sse` 只重放了 `response.output_text.delta` 和 `response.completed`。缺少 `response.created`、`response.in_progress`、`response.output_item.added` 等包围事件。

**影响**: 与 BUG-06 类似，依赖完整事件流的客户端可能无法正确处理。

---

### BUG-08: OpenAI 缓存重放时每个 chunk 生成不同的 `id`（Minor）

**文件**: `stream_cache_middleware.py` L90

**问题描述**: `_format_openai_sse` 每次调用都生成新的 `chunk_id = f"chatcmpl-cache-{uuid.uuid4().hex[:8]}"`。

但在真实的 OpenAI 流式响应中，同一次 completion 的所有 chunk 共享相同的 `id`。

**结果**: 某些客户端可能依赖 id 一致性来关联同一次 completion 的所有 chunks。

**修复方案**: 在 `replay_cached_stream` 开始时生成一次 `chunk_id`，传给所有 `_format_openai_sse` 调用。

---

### BUG-09: `cache_service` 方法声明为 `async` 但使用同步 Redis 操作（Minor）

**文件**: `cache_service.py` L21-45、L47-91、L152-189、L191-214

**问题描述**: `CacheService` 的方法全部声明为 `async def`，但内部调用的是同步 Redis 操作：
```python
cached_data = self.redis.get(...)   # 同步调用
self.redis.set(...)                 # 同步调用
```

这些同步 Redis 操作会阻塞事件循环。虽然单次 Redis 操作通常很快（< 1ms），但在高并发场景下仍可能成为瓶颈。

**修复方案**: 使用 `aioredis` 或在线程池中执行同步 Redis 操作：
```python
import asyncio
cached_data = await asyncio.to_thread(self.redis.get, f"cache:stream:{cache_key}")
```

---

### BUG-10: Redis 存储大小无限制检查（Minor）

**文件**: `cache_service.py` L152-189

**问题描述**: `save_stream_response` 将完整的流式响应序列化为 JSON 后直接存入 Redis，没有检查数据大小。

对于长对话（如 4k+ completion tokens），chunks 数据可能达到数百 KB。如果大量这样的响应被缓存，可能占用大量 Redis 内存。

**修复方案**:
```python
serialized = json.dumps(data, ensure_ascii=False)
max_size = int(os.getenv("CACHE_MAX_STREAM_SIZE_BYTES", 512 * 1024))  # 512KB
if len(serialized.encode()) > max_size:
    logger.warning(f"Stream cache too large ({len(serialized)} bytes), skipping")
    return False
```

---

## 2. 改进建议

### 2.1 统一 billing 调用时机

当前 billing 的调用职责分散：
- **MISS 分支**: `upstream_call` 内部调用 `billing_callback(input_tokens, output_tokens, False)`
- **HIT 分支**: `wrap_stream_request` 内部调用 `billing_callback(usage["prompt_tokens"], ..., True)`
- **BYPASS 分支**: 依赖 `upstream_call` 内部调用

建议统一由 `wrap_stream_request` 管理 billing，`upstream_call` 不调用 billing_callback，只负责收集 usage 数据。这需要在 MISS 分支的 `finally` 块中添加 billing 调用。

### 2.2 模拟延迟策略优化

当前 `replay_cached_stream`（L214-218）的延迟策略：
```python
wait_ms = min(delta_ms, 200)
await asyncio.sleep(wait_ms / 1000.0)
```

建议增加一个「快速模式」选项（通过请求头 `X-Cache-No-Delay: true` 控制），允许客户端选择跳过延迟直接接收全部缓存内容，减少缓存响应总耗时。

### 2.3 添加缓存版本号机制

当前缓存数据格式如果将来变化（如添加新字段），旧缓存可能无法兼容。建议在缓存数据中添加 `"version": 1` 字段，读取时检查版本兼容性。

### 2.4 `wrap_stream_request` 类型注解修正

```python
# 当前（不正确）
upstream_call: Callable[[], AsyncGenerator[str, None]]

# 应改为
upstream_call: Callable[[StreamCollector, Dict[str, int]], AsyncGenerator[str, None]]
```

### 2.5 添加流式缓存的 TTL 上限保护

```python
ttl = int(headers.get("X-Cache-TTL", 3600))
```

L372 直接信任客户端传入的 TTL，恶意用户可以设置超长 TTL（如 `999999999`）。建议添加上限：
```python
MAX_STREAM_CACHE_TTL = 86400  # 24小时
ttl = min(int(headers.get("X-Cache-TTL", 3600)), MAX_STREAM_CACHE_TTL)
```

### 2.6 流式收集应记录更多元数据

`StreamCollector` 当前只收集 `content`、`delta_ms`、`finish_reason`。建议额外记录：
- 首个 chunk 的延迟（TTFT - Time To First Token）
- 总 chunk 数量
- 协议特有的事件包围信息（用于修复 BUG-06/07）

---

## 3. 性能分析

### 3.1 `asyncio.sleep` 是否阻塞事件循环？

**结论: 不会阻塞。** `asyncio.sleep` 是协程原语，会让出事件循环控制权。但大量小 sleep 可能造成不必要的上下文切换开销。建议在 `delta_ms < 5` 时跳过 sleep。

### 3.2 chunk 收集的内存风险

`StreamCollector.chunks` 是一个 `List[Dict]`，对于长响应可能占用较多内存。但由于每个请求独立的 collector 实例在请求结束后会被 GC 回收，且同一时间的并发请求数有限，实际风险较低。

### 3.3 Redis 存储压力

- 每个流式缓存包含完整的 chunks 列表 + 时间间隔数据
- 典型大小：500 token 响应 ≈ 10-30KB，5000 token 响应 ≈ 100-300KB
- 默认 TTL 3600s，Redis 会自动过期
- 建议：添加大小上限检查（见 BUG-10）

---

## 4. 整体评价

### 评级: **需修改** ⚠️

**架构设计**: ⭐⭐⭐⭐ (4/5)
- 中间件模式设计合理，与 `CacheMiddleware`（非流式）保持一致
- 收集器模式（StreamCollector）清晰分离了数据收集与缓存存储
- 延迟模拟方案有合理的上限控制

**正确性**: ⭐⭐ (2/5)
- **2 个 Critical Bug**：BUG-01（header 永远是 BYPASS）和 BUG-02（BYPASS 分支参数不匹配导致 TypeError）
- **3 个 Major Bug**：BUG-04（Session 类型不匹配）、BUG-06/07（协议重放不完整）
- 这些问题在生产环境中会导致功能异常

**兼容性**: ⭐⭐ (2/5)
- OpenAI 格式基本正确，但 chunk id 不一致（BUG-08）
- Anthropic 和 Responses API 的缓存重放缺少关键事件，可能导致客户端兼容性问题

**错误处理**: ⭐⭐⭐⭐ (4/5)
- 异常捕获覆盖全面，不会因缓存逻辑导致请求完全失败
- `stream_success` 标志逻辑正确
- Redis 异常被优雅降级处理

### 必须修复才能上线的项目：
1. **BUG-02**（Critical）：BYPASS 分支的 `upstream_call()` 无参调用导致 TypeError
2. **BUG-01**（Critical）：`X-Cache-Status` header 永远是 BYPASS
3. **BUG-04**（Major）：Session/AsyncSession 类型不匹配
4. **BUG-05**（Minor 但影响用户体验）：清空缓存不清除流式缓存

### 可以后续迭代的项目：
- BUG-06/07（协议完整性）：当前简化的重放格式可能对大多数纯文本客户端已经够用
- BUG-08/09/10（质量改进）：不影响核心功能

---

*Review by Codex | 2026-03-21*
