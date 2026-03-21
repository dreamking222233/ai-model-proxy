# 流式请求缓存方案 - 完整响应缓存 + 模拟流式输出

**方案编号**: Plan v1
**创建日期**: 2026-03-21
**任务类型**: 大型（预计 10+ 步骤）
**方案**: 缓存完整响应，命中时模拟流式输出（推荐）

---

## 📋 方案概述

### 核心思路
1. **缓存阶段**: 流式请求完成后，缓存完整的响应内容
2. **命中阶段**: 从缓存读取完整响应，按原始速度模拟流式输出（SSE 格式）
3. **用户体验**: 保持流式输出的视觉效果，用户无感知

### 技术优势
- ✅ 用户体验一致（保持流式输出效果）
- ✅ 实现复杂度适中
- ✅ 兼容现有客户端（无需修改客户端代码）
- ✅ 支持所有流式协议（OpenAI、Anthropic、Responses API）

### 技术挑战
- ⚠️ 需要模拟流式输出速度（避免瞬间输出）
- ⚠️ 需要正确构造 SSE 格式
- ⚠️ 需要处理流式响应的中断和错误

---

## 🎯 实施范围

### 覆盖的请求类型
1. **OpenAI 流式请求** (`_stream_openai_request`)
2. **Anthropic 流式请求** (`_stream_anthropic_request`)
3. **Responses API 流式请求** (`_stream_responses_request`)

### 不覆盖的请求类型
- ❌ WebSocket 请求（技术复杂度高，优先级低）
- ✅ 非流式请求（已在上一阶段完成）

---

## 🏗️ 架构设计

### 1. 缓存数据结构

#### 1.1 缓存的内容
```python
{
    "chunks": [
        {
            "content": "Hello",
            "delta_ms": 50,  # 与上一个 chunk 的时间间隔（毫秒）
            "finish_reason": None
        },
        {
            "content": " world",
            "delta_ms": 45,
            "finish_reason": None
        },
        {
            "content": "",
            "delta_ms": 30,
            "finish_reason": "stop"
        }
    ],
    "model": "gpt-4",
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
    },
    "protocol": "openai",  # openai | anthropic | responses
    "total_duration_ms": 1250  # 总耗时
}
```

#### 1.2 为什么记录时间间隔？
- 模拟真实的流式输出速度
- 避免缓存命中时瞬间输出所有内容（体验差）
- 保持用户对"AI 正在思考"的感知

### 2. 核心组件改造

#### 2.1 CacheService 扩展

**新增方法**:
```python
class CacheService:
    async def save_stream_response(
        self,
        cache_key: str,
        chunks: List[Dict],
        model: str,
        usage: Dict,
        protocol: str,
        ttl: int = None
    ) -> bool:
        """保存流式响应到缓存"""
        pass

    async def get_stream_response(
        self,
        cache_key: str
    ) -> Optional[Dict]:
        """获取缓存的流式响应"""
        pass
```

**实现要点**:
- 使用 JSON 序列化存储 chunks 列表
- 记录每个 chunk 的时间间隔（delta_ms）
- 存储协议类型（用于正确构造 SSE 格式）

#### 2.2 StreamCacheMiddleware（新增）

**职责**: 包装流式请求，处理缓存逻辑

**核心方法**:
```python
class StreamCacheMiddleware:
    @staticmethod
    async def wrap_stream_request(
        request_body: Dict,
        headers: Dict,
        user: SysUser,
        db: Session,
        upstream_stream_call: Callable,
        unified_model: str,
        protocol: str  # "openai" | "anthropic" | "responses"
    ) -> AsyncGenerator[str, None]:
        """
        包装流式请求，处理缓存逻辑

        返回: SSE 格式的流式响应（AsyncGenerator）
        """
        pass

    @staticmethod
    async def replay_cached_stream(
        cached_data: Dict,
        protocol: str
    ) -> AsyncGenerator[str, None]:
        """
        从缓存重放流式响应

        参数:
        - cached_data: 缓存的完整响应数据
        - protocol: 协议类型（openai/anthropic/responses）

        返回: SSE 格式的流式响应
        """
        pass

    @staticmethod
    def _format_sse_chunk(
        chunk: Dict,
        protocol: str
    ) -> str:
        """
        根据协议格式化 SSE chunk

        OpenAI 格式:
        data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}

        Anthropic 格式:
        data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}

        Responses 格式:
        data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}
        """
        pass
```

**关键逻辑**:
1. **缓存查询**: 先查询缓存，如果命中则调用 `replay_cached_stream`
2. **上游调用**: 如果未命中，调用 `upstream_stream_call`，同时收集 chunks
3. **缓存保存**: 流式响应完成后，保存到缓存
4. **模拟延迟**: 重放时根据 `delta_ms` 使用 `asyncio.sleep` 模拟延迟

#### 2.3 ProxyService 集成

**改造方法**:
- `_stream_openai_request`
- `_stream_anthropic_request`
- `_stream_responses_request`

**改造模式**:
```python
async def _stream_openai_request(self, ...):
    # 原有逻辑...

    # 定义上游流式调用
    async def upstream_stream_call():
        async with httpx.AsyncClient(...) as client:
            async with client.stream("POST", url, json=request_data, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield line

    # 使用缓存中间件包装
    stream_generator = StreamCacheMiddleware.wrap_stream_request(
        request_body=request_data,
        headers=request_headers or {},
        user=user,
        db=db,
        upstream_stream_call=upstream_stream_call,
        unified_model=unified_model,
        protocol="openai"
    )

    # 返回流式响应
    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={"X-Cache-Status": "..."}
    )
```

---

## 🔧 实施细节

### 1. 流式响应收集器

**目的**: 在流式输出的同时收集完整响应

```python
class StreamCollector:
    def __init__(self):
        self.chunks = []
        self.start_time = time.time()
        self.last_chunk_time = self.start_time

    def add_chunk(self, content: str, finish_reason: str = None):
        """添加一个 chunk"""
        current_time = time.time()
        delta_ms = int((current_time - self.last_chunk_time) * 1000)

        self.chunks.append({
            "content": content,
            "delta_ms": delta_ms,
            "finish_reason": finish_reason
        })

        self.last_chunk_time = current_time

    def get_collected_data(self, model: str, usage: Dict, protocol: str) -> Dict:
        """获取收集的完整数据"""
        return {
            "chunks": self.chunks,
            "model": model,
            "usage": usage,
            "protocol": protocol,
            "total_duration_ms": int((time.time() - self.start_time) * 1000)
        }
```

### 2. SSE 格式构造

#### 2.1 OpenAI 格式
```python
def _format_openai_sse(chunk: Dict) -> str:
    if chunk["finish_reason"]:
        data = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": chunk["finish_reason"]
            }]
        }
    else:
        data = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {"content": chunk["content"]},
                "finish_reason": None
            }]
        }

    return f"data: {json.dumps(data)}\n\n"
```

#### 2.2 Anthropic 格式
```python
def _format_anthropic_sse(chunk: Dict) -> str:
    if chunk["finish_reason"]:
        data = {
            "type": "message_stop"
        }
    else:
        data = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "text_delta",
                "text": chunk["content"]
            }
        }

    return f"data: {json.dumps(data)}\n\n"
```

#### 2.3 Responses 格式
```python
def _format_responses_sse(chunk: Dict) -> str:
    # Responses API 使用类似 Anthropic 的格式
    return _format_anthropic_sse(chunk)
```

### 3. 缓存重放逻辑

```python
async def replay_cached_stream(
    cached_data: Dict,
    protocol: str
) -> AsyncGenerator[str, None]:
    """从缓存重放流式响应"""
    chunks = cached_data["chunks"]

    for chunk in chunks:
        # 模拟延迟
        if chunk["delta_ms"] > 0:
            await asyncio.sleep(chunk["delta_ms"] / 1000.0)

        # 格式化 SSE
        sse_line = StreamCacheMiddleware._format_sse_chunk(chunk, protocol)
        yield sse_line

    # 发送结束标记
    yield "data: [DONE]\n\n"
```

### 4. 缓存条件判断

**复用现有逻辑** (`CacheMiddleware.should_cache`):
- 用户启用缓存 (`user.enable_cache == 1`)
- 全局缓存开关 (`CACHE_ENABLED=true`)
- 请求头未设置 `X-No-Cache: true`
- Prompt tokens >= `CACHE_MIN_PROMPT_TOKENS`
- 请求不包含随机性参数（temperature=0, top_p=1）

**流式请求特殊处理**:
- ✅ 流式请求也可以缓存（缓存完整响应）
- ✅ 缓存命中时模拟流式输出

### 5. 计费逻辑

**复用现有逻辑** (`CacheMiddleware.get_billing_tokens`):
- `cache_billing_enabled = 0`: 按原始 tokens 计费
- `cache_billing_enabled = 1`: 按缓存后 tokens 计费（0 tokens）

**流式请求计费时机**:
- 流式响应完成后，统一扣费
- 使用 `ProxyService._deduct_balance_and_log` 方法

---

## 📁 文件改动清单

### 新增文件（1 个）
1. `backend/app/middleware/stream_cache_middleware.py` - 流式缓存中间件

### 修改文件（2 个）
1. `backend/app/services/cache_service.py` - 添加流式缓存方法
2. `backend/app/services/proxy_service.py` - 集成流式缓存中间件
   - `_stream_openai_request` (约 200 行)
   - `_stream_anthropic_request` (约 200 行)
   - `_stream_responses_request` (约 200 行)

---

## 🧪 测试计划

### 1. 功能测试
- [ ] OpenAI 流式请求缓存未命中 → 正常流式输出
- [ ] OpenAI 流式请求缓存命中 → 模拟流式输出
- [ ] Anthropic 流式请求缓存未命中 → 正常流式输出
- [ ] Anthropic 流式请求缓存命中 → 模拟流式输出
- [ ] Responses API 流式请求缓存未命中 → 正常流式输出
- [ ] Responses API 流式请求缓存命中 → 模拟流式输出

### 2. 计费测试
- [ ] `cache_billing_enabled = 0` → 缓存命中仍按原始 tokens 计费
- [ ] `cache_billing_enabled = 1` → 缓存命中按 0 tokens 计费

### 3. 边界测试
- [ ] Redis 连接失败 → 降级到直接调用上游
- [ ] 流式响应中断 → 不保存缓存
- [ ] 缓存数据损坏 → 降级到直接调用上游

### 4. 性能测试
- [ ] 缓存命中响应时间 < 100ms（首字节）
- [ ] 模拟流式输出速度接近真实速度
- [ ] Redis 存储大小合理（单个响应 < 100KB）

---

## ⚠️ 风险与缓解

### 风险 1: 模拟延迟不准确
**影响**: 用户感知缓存命中时输出速度异常
**缓解**:
- 记录真实的 chunk 时间间隔
- 支持配置延迟倍率（如 0.8x 加速）

### 风险 2: SSE 格式不兼容
**影响**: 客户端解析失败
**缓解**:
- 严格按照官方协议构造 SSE
- 添加单元测试验证格式正确性

### 风险 3: 流式响应中断
**影响**: 缓存不完整数据
**缓解**:
- 只有流式响应完整结束才保存缓存
- 捕获异常，中断时不保存缓存

### 风险 4: Redis 存储压力
**影响**: Redis 内存占用过高
**缓解**:
- 设置合理的 TTL（默认 1 小时）
- 限制单个响应大小（如 100KB）
- 使用 LRU 淘汰策略

---

## 📊 预期收益

### 性能收益
- 缓存命中时首字节响应时间: **< 100ms**（vs 原始 1-3 秒）
- 总响应时间: **与原始流式输出相同**（模拟延迟）
- 上游 API 调用减少: **30-50%**（预期缓存命中率）

### 成本收益
- 每用户每天节省 tokens: **10,000+**（假设 30% 缓存命中率）
- 每用户每天节省费用: **$0.5+**（假设 GPT-4 价格）
- Redis 存储成本: **< $0.05/用户/天**（可忽略）

### 用户体验
- ✅ 保持流式输出的视觉效果
- ✅ 无需修改客户端代码
- ✅ 透明的缓存机制

---

## 🚀 实施步骤（预计 10+ 步）

### Phase 1: 核心组件开发（4 步）
1. 创建 `StreamCollector` 类（收集流式响应）
2. 扩展 `CacheService`（添加流式缓存方法）
3. 创建 `StreamCacheMiddleware`（核心中间件）
4. 实现 SSE 格式构造方法（OpenAI/Anthropic/Responses）

### Phase 2: ProxyService 集成（3 步）
5. 集成到 `_stream_openai_request`
6. 集成到 `_stream_anthropic_request`
7. 集成到 `_stream_responses_request`

### Phase 3: 测试与优化（3 步）
8. 功能测试（缓存命中/未命中）
9. 计费测试（cache_billing_enabled）
10. 性能测试（响应时间、模拟延迟）

### Phase 4: 文档与 Review（2 步）
11. 编写实施报告（impl-stream-cache-replay-20260321.md）
12. Codex Review（代码质量、安全性、性能）

---

## 📝 待 Codex 评估的问题

### 1. 架构设计
- [ ] `StreamCacheMiddleware` 的设计是否合理？
- [ ] 缓存数据结构是否完整？
- [ ] 是否有更优的实现方式？

### 2. 性能考虑
- [ ] 模拟延迟的实现是否会阻塞其他请求？
- [ ] Redis 存储大小是否合理？
- [ ] 是否需要压缩缓存数据？

### 3. 安全性
- [ ] 缓存数据是否需要加密？
- [ ] 是否有缓存投毒风险？
- [ ] 用户隔离是否充分？

### 4. 兼容性
- [ ] SSE 格式是否完全兼容官方协议？
- [ ] 是否支持所有客户端（curl、SDK、Web）？
- [ ] 是否需要处理特殊字符转义？

### 5. 边界情况
- [ ] 流式响应中断如何处理？
- [ ] Redis 连接失败如何降级？
- [ ] 缓存数据损坏如何处理？

---

## 📞 联系与支持

**方案设计者**: Claude Code
**项目路径**: `/Volumes/project/modelInvocationSystem`
**文档日期**: 2026-03-21
**下一步**: 等待 Codex 评估

---

**Plan v1 结束**
