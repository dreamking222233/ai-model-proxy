# v1/responses 接口 502 错误修复计划

## 问题现象

Codex CLI 调用本地反代服务的 v1/responses 接口时出现：
```
• Reconnecting... 1/5 (5s • esc to interrupt)
  └ Unexpected status 502 Bad Gateway: Unknown error, url: http://localhost:8085/v1/responses
```

## 问题分析

### 1. 当前实现架构
```
Codex CLI → /v1/responses → ProxyService.handle_responses_request
                                ↓
                    转换为 Chat Completions 格式
                                ↓
                    调用上游 /chat/completions
                                ↓
                    转换回 Responses API SSE 格式
```

### 2. 已识别的问题点

#### 问题 A: 异常处理不完整
**位置**: `proxy_service.py:120-131`
```python
except Exception as e:
    last_error = e
    logger.warning("Channel %s failed: %s", channel.name, e)
    ProxyService._record_channel_failure(db, channel)
    continue

# 最后抛出 503 错误，但 Codex 收到的是 502
raise ServiceException(503, f"All channels failed: {error_detail}", "ALL_CHANNELS_FAILED")
```

**问题**:
- 异常被捕获但没有详细日志
- ServiceException 可能在中间件层被转换为 502
- 缺少对上游 HTTP 错误的精确处理

#### 问题 B: SSE 流异常处理缺陷
**位置**: `proxy_service.py:234-237`
```python
except Exception as e:
    stream_error = e
    logger.error("Responses API stream error: %s", e)
    yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'message': str(e)}})}\n\n"
```

**问题**:
- 流式响应中的异常会导致连接中断
- Codex CLI 可能无法正确解析错误事件
- 没有在异常时发送正确的 HTTP 状态码

#### 问题 C: 上游连接失败处理
**位置**: `proxy_service.py:196-199`
```python
async with client.stream("POST", url, json=chat_request, headers=headers) as response:
    if response.status_code != 200:
        body = await response.aread()
        raise Exception(f"Upstream returned HTTP {response.status_code}: {body.decode('utf-8', errors='replace')[:500]}")
```

**问题**:
- 上游返回非 200 状态码时，异常在 event_generator 内部抛出
- StreamingResponse 已经开始返回，无法修改 HTTP 状态码
- 导致客户端收到 200 状态码但流中断

#### 问题 D: 缺少请求/响应日志
**位置**: `openai_proxy.py:131-133`
```python
logger.info(f"Codex request body: {body}")
logger.info(f"Codex request headers: {dict(request.headers)}")
```

**问题**:
- 日志级别为 info，可能未启用
- 缺少上游请求/响应的详细日志
- 无法追踪完整的请求链路

#### 问题 E: 协议转换可能不完整
**位置**: `proxy_service.py:74-83`
```python
if isinstance(input_data, str):
    request_data["input"] = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": input_data}]
        }
    ]
```

**问题**:
- Codex CLI 发送的实际格式可能与预期不符
- 缺少对 Codex 特定字段的处理（如 `modalities`、`instructions` 等）

### 3. 参考 CLIProxyAPI 项目的正确实现

根据 GitHub 项目分析，关键差异：

1. **直接转发而非转换**: CLIProxyAPI 可能直接转发 Responses API 请求到支持该协议的上游
2. **错误处理**: 在 StreamingResponse 返回前验证上游连接
3. **SSE 格式**: 严格遵循 OpenAI Responses API 的事件格式

## 修复方案

### 阶段 1: 增强日志和诊断 (优先级: 高)

**目标**: 先定位具体失败原因

1. 添加详细的请求/响应日志
2. 记录上游 API 的完整错误信息
3. 添加 Codex CLI 请求格式的验证日志

**文件**:
- `backend/app/services/proxy_service.py`
- `backend/app/api/proxy/openai_proxy.py`

### 阶段 2: 修复异常处理机制 (优先级: 高)

**目标**: 确保异常正确传递给客户端

1. **在 StreamingResponse 返回前验证上游连接**
   ```python
   # 先建立连接并验证状态码
   async with client.stream("POST", url, ...) as response:
       if response.status_code != 200:
           # 在这里抛出异常，让外层处理
           raise ServiceException(502, f"Upstream error: {response.status_code}")

       # 状态码正常才返回 StreamingResponse
       async def event_generator():
           # 流式处理
   ```

2. **改进 ServiceException 到 HTTP 状态码的映射**
   - 确保 503 不会被转换为 502
   - 添加上游错误的透传机制

3. **优化多渠道故障转移逻辑**
   - 区分可重试错误和不可重试错误
   - 避免在所有渠道都失败时返回模糊的 "Unknown error"

**文件**:
- `backend/app/services/proxy_service.py:156-266`
- `backend/app/core/exceptions.py`

### 阶段 3: 完善协议转换 (优先级: 中)

**目标**: 确保与 Codex CLI 的完全兼容

1. **验证 Codex CLI 的实际请求格式**
   - 添加请求体 schema 验证
   - 记录所有未处理的字段

2. **完善 input 字段的处理**
   - 支持 Codex 的多模态输入
   - 处理 `instructions` 等特殊字段

3. **优化 SSE 事件流格式**
   - 确保事件顺序符合 Responses API 规范
   - 添加必要的元数据字段

**文件**:
- `backend/app/services/proxy_service.py:74-88, 134-153`

### 阶段 4: 添加健康检查和测试 (优先级: 低)

**目标**: 预防性监控

1. 添加 v1/responses 接口的健康检查端点
2. 编写集成测试模拟 Codex CLI 请求
3. 添加上游渠道的连通性检测

**文件**:
- `backend/app/api/admin/health.py`
- `backend/tests/test_responses_api.py` (新建)

## 实施步骤

### Step 1: 启用详细日志 (5 分钟)
- [ ] 修改 `openai_proxy.py` 添加详细日志
- [ ] 修改 `proxy_service.py` 添加上游请求/响应日志
- [ ] 重启服务并复现问题，收集日志

### Step 2: 修复核心异常处理 (20 分钟)
- [ ] 重构 `_stream_responses_request` 的异常处理
- [ ] 在返回 StreamingResponse 前验证上游连接
- [ ] 优化 ServiceException 的状态码映射
- [ ] 测试修复效果

### Step 3: 完善协议转换 (15 分钟)
- [ ] 添加 Codex 请求格式的验证
- [ ] 完善 input 字段的处理逻辑
- [ ] 优化 SSE 事件流格式
- [ ] 测试与 Codex CLI 的兼容性

### Step 4: 验证和测试 (10 分钟)
- [ ] 使用 Codex CLI 进行端到端测试
- [ ] 验证错误场景的处理
- [ ] 检查日志输出是否完整

## 关键代码位置

| 文件 | 行号 | 问题 | 优先级 |
|------|------|------|--------|
| `proxy_service.py` | 120-131 | 异常处理不完整 | 高 |
| `proxy_service.py` | 196-199 | 上游连接失败处理 | 高 |
| `proxy_service.py` | 234-237 | SSE 流异常处理 | 高 |
| `proxy_service.py` | 74-88 | 协议转换可能不完整 | 中 |
| `openai_proxy.py` | 131-133 | 日志不足 | 高 |
| `exceptions.py` | 22-23 | 状态码映射 | 中 |

## 预期结果

修复后，Codex CLI 应该能够：
1. 成功连接到 v1/responses 接口
2. 接收流式响应
3. 在错误时收到明确的错误信息（而非 502 Unknown error）
4. 支持多轮对话和工具调用

## 风险评估

- **低风险**: 日志增强不影响现有功能
- **中风险**: 异常处理修改可能影响其他接口
- **缓解措施**:
  - 仅修改 Responses API 相关代码
  - 保持 Chat Completions 接口不变
  - 充分测试后再部署

## 参考资料

- OpenAI Responses API 文档: https://platform.openai.com/docs/api-reference/responses
- Codex CLI 源码: https://github.com/anthropics/claude-code
- CLIProxyAPI 参考实现: https://github.com/router-for-me/CLIProxyAPI
