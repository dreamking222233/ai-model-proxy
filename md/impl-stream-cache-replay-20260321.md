# 流式请求缓存实施报告 - 缓存完整响应 + 模拟流式输出

**实施日期**: 2026-03-21
**项目**: modelInvocationSystem
**实施阶段**: 流式请求缓存（Phase 2）

---

## 📊 实施概览

### 完成状态
- ✅ **StreamCollector 类**: 已实现（收集 chunks 和时间间隔）
- ✅ **CacheService 扩展**: 已实现（save_stream_response / get_stream_response）
- ✅ **StreamCacheMiddleware**: 已实现（核心中间件）
- ✅ **SSE 格式构造**: 已实现（OpenAI / Anthropic / Responses 三种协议）
- ✅ **OpenAI 流式集成**: 已完成（_stream_openai_request）
- ✅ **Anthropic 流式集成**: 已完成（_stream_anthropic_request）
- ✅ **Responses API 流式集成**: 已完成（_stream_responses_request）
- ⏸️ **Codex Review**: 进行中

### 完成度评估
- **代码实现**: 100%
- **集成完成度**: 100%（三种流式协议均已集成）
- **可上线性**: 待 Codex Review 后确认

---

## ✅ 本次实施完成工作清单

### 1. 新建文件：stream_cache_middleware.py

**文件**: `backend/app/middleware/stream_cache_middleware.py`

#### 1.1 StreamCollector 类
```python
class StreamCollector:
    """收集流式响应内容，用于事后保存到缓存"""

    def __init__(self):
        self.chunks = []
        self.start_time = time.time()
        self.last_chunk_time = self.start_time

    def add_chunk(self, content: str, finish_reason: str = None):
        """添加 chunk，记录时间间隔"""
        delta_ms = int((time.time() - self.last_chunk_time) * 1000)
        self.chunks.append({
            "content": content,
            "delta_ms": max(0, delta_ms),
            "finish_reason": finish_reason,
        })
        self.last_chunk_time = time.time()
```

#### 1.2 SSE 格式构造（三种协议）
```python
# OpenAI 格式
def _format_openai_sse(chunk, model) -> str:
    return f"data: {json.dumps({'choices': [{'delta': {'content': chunk['content']}}]})}\n\n"

# Anthropic 格式
def _format_anthropic_sse(chunk) -> str:
    return f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', ...})}\n\n"

# Responses API 格式
def _format_responses_sse(chunk) -> str:
    return f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': chunk['content']})}\n\n"
```

#### 1.3 StreamCacheMiddleware 核心逻辑
```python
class StreamCacheMiddleware:
    @staticmethod
    async def wrap_stream_request(...) -> AsyncGenerator[str, None]:
        """
        1. 判断是否应该缓存（移除 stream=True，复用 should_cache 逻辑）
        2. 缓存命中 → 调用 replay_cached_stream() 模拟流式输出
        3. 缓存未命中 → 调用上游，收集 chunks，完成后保存缓存
        """

    @staticmethod
    async def replay_cached_stream(cached_data, protocol) -> AsyncGenerator[str, None]:
        """
        从缓存重放流式响应
        - 根据 delta_ms 模拟真实延迟（最长 200ms）
        - 按协议格式构造 SSE
        """
```

---

### 2. 修改文件：cache_service.py

**文件**: `backend/app/services/cache_service.py`

**新增方法**:

```python
async def save_stream_response(self, cache_key, data, user_id, ttl=3600) -> bool:
    """保存流式响应到 Redis（key: cache:stream:{cache_key}）"""

async def get_stream_response(self, cache_key) -> Optional[Dict]:
    """获取缓存的流式响应（key: cache:stream:{cache_key}）"""
```

**Redis Key 命名规范**:
- 非流式缓存: `cache:content:{cache_key}`
- 流式缓存: `cache:stream:{cache_key}`
- 用户缓存键集合: `cache:user_keys:{user_id}`

---

### 3. 修改文件：proxy_service.py

**文件**: `backend/app/services/proxy_service.py`

#### 3.1 新增导入
```python
from app.middleware.stream_cache_middleware import StreamCacheMiddleware
```

#### 3.2 _stream_openai_request 改造
**核心改动**:
1. 定义 `billing_callback` 记录计费 tokens
2. 将上游调用封装为接受 `(collector, collected_usage)` 参数的异步生成器
3. 在 upstream_call 中收集文本 chunks 和 usage tokens
4. 使用 `StreamCacheMiddleware.wrap_stream_request()` 包装整个流式请求
5. 流式响应完成后，根据 `billing_is_cache_hit` + `cache_billing_enabled` 决定计费

```python
async def upstream_call(collector, collected_usage):
    """上游流式调用，同时通过 collector 收集 chunks"""
    async with httpx.AsyncClient(...) as client:
        async with client.stream("POST", url, ...) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    # 提取 usage
                    if usage:
                        collected_usage["prompt_tokens"] = input_tokens
                        collected_usage["completion_tokens"] = output_tokens
                    # 收集 chunk
                    content = delta.get("content", "")
                    if content or finish_reason:
                        collector.add_chunk(content or "", finish_reason)
                    yield f"data: {data_str}\n\n"
    billing_callback(input_tokens, output_tokens, False)
```

#### 3.3 _stream_anthropic_request 改造
与 OpenAI 集成相同模式，适配 Anthropic 协议：
- 从 `message_start` 提取 `input_tokens`
- 从 `message_delta` 提取 `output_tokens`
- 从 `content_block_delta` 收集文本内容

#### 3.4 _stream_responses_request 改造
与 OpenAI 集成相同模式，适配 Responses API 协议：
- 从 `response.completed` 提取 usage
- 从 `response.output_text.delta` 收集文本内容

---

## 📁 本次实施修改文件清单

### 新增文件（1 个）
1. `backend/app/middleware/stream_cache_middleware.py` — 流式缓存中间件（~280 行）

### 修改文件（2 个）
1. `backend/app/services/cache_service.py` — 新增流式缓存方法（+65 行）
2. `backend/app/services/proxy_service.py` — 三处流式方法改造（+~150 行）

---

## 🎯 技术亮点

### 1. 透明缓存设计
- 流式请求缓存对上游和下游完全透明
- `upstream_call` 函数封装上游调用，中间件不感知具体协议细节
- 降级行为：Redis 不可用时自动跳过缓存，请求正常转发

### 2. 真实延迟模拟
- 记录每个 chunk 的实际时间间隔（delta_ms）
- 重放时模拟真实延迟（压缩到最长 200ms 避免过慢）
- 用户体验与真实流式输出接近

### 3. 三协议统一支持
- OpenAI: `data: {choices: [{delta: {content: "..."}}]}`
- Anthropic: `event: content_block_delta\ndata: {type: "content_block_delta", ...}`
- Responses API: `data: {type: "response.output_text.delta", delta: "..."}`

### 4. 完善的计费机制
- 缓存命中时通过 `billing_callback` 传递 tokens 和 `is_cache_hit` 标志
- `cache_billing_enabled = 1` 时按 0 tokens 计费（节省费用）
- `cache_billing_enabled = 0` 时按原始 tokens 计费（默认）

### 5. 安全的缓存保存
- 只有流式响应完整成功才保存缓存（`stream_success` 标志）
- 流式中断不保存不完整数据
- 缓存数据损坏时自动删除并降级

---

## 🔧 缓存数据结构

### 流式响应缓存格式
```python
{
    "chunks": [
        {
            "content": "Hello",
            "delta_ms": 50,      # 与上一个 chunk 的时间间隔（毫秒）
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
        "completion_tokens": 20
    },
    "protocol": "openai",         # openai | anthropic | responses
    "total_duration_ms": 1250     # 总耗时
}
```

### Redis Key 命名
| 类型 | Key 格式 |
|------|---------|
| 非流式缓存内容 | `cache:content:{cache_key}` |
| 流式缓存内容 | `cache:stream:{cache_key}` |
| 用户缓存键集合 | `cache:user_keys:{user_id}` |

---

## ⏸️ 待确认事项

### Codex Review 关注点
1. `cache_status` 响应头在 StreamingResponse 中的可见性问题
2. `upstream_call(collector, collected_usage)` 函数签名的一致性
3. SSE 格式的正确性验证（各协议客户端兼容性）
4. `billing_callback` 的调用时机和竞态问题

---

## 🚀 缓存覆盖范围总结

| 请求类型 | 协议 | 缓存支持 | 说明 |
|---------|------|---------|------|
| 非流式 | OpenAI | ✅ | Phase 1 完成 |
| 非流式 | Anthropic | ✅ | Phase 1 完成 |
| 流式 | OpenAI | ✅ | Phase 2 完成 |
| 流式 | Anthropic | ✅ | Phase 2 完成 |
| 流式 | Responses API | ✅ | Phase 2 完成 |
| WebSocket | Responses API | ❌ | 暂不实现（复杂度高） |

---

**报告结束**
**实施者**: Claude Code
**项目路径**: `/Volumes/project/modelInvocationSystem`
**文档日期**: 2026-03-21
