# 流式缓存测试指南

**日期**: 2026-03-21
**状态**: 待测试

---

## 一、测试准备

### 1.1 启动依赖服务

```bash
# 1. 启动 Redis
redis-server --daemonize yes
redis-cli ping  # 应返回 PONG

# 2. 启动 MySQL（如果未运行）
# 根据你的环境启动 MySQL

# 3. 检查数据库连接
mysql -u root -p -e "USE modelinvoke; SHOW TABLES;"
```

### 1.2 启动后端服务

```bash
cd /Volumes/project/modelInvocationSystem/backend

# 激活 conda 环境
conda activate ai-invoke-service

# 启动后端服务（前台运行，方便查看日志）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

**预期输出**:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8085
```

---

## 二、手动测试流式缓存

### 2.1 测试环境变量

```bash
# API Key（替换为你的实际 API Key）
export API_KEY="sk-8f698230bcb52e4c210b039e5cfcac6c66396dfa3d6ee78c"
export BASE_URL="http://localhost:8085"
```

### 2.2 测试 1: 第一次请求（预期 MISS）

```bash
curl -N -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "请用一句话介绍 Python 的优点"}],
    "stream": true,
    "max_tokens": 100
  }'
```

**预期结果**:
- 响应头: `X-Cache-Status: STREAM`
- 后端日志: `Stream cache MISS for user xxx, key=xxxxxxxx...`
- 流式响应: 正常返回 SSE 格式的 chunks

### 2.3 测试 2: 相同请求（预期 HIT）

```bash
# 立即重复相同请求
curl -N -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "请用一句话介绍 Python 的优点"}],
    "stream": true,
    "max_tokens": 100
  }'
```

**预期结果**:
- 响应头: `X-Cache-Status: STREAM`
- 后端日志: `Stream cache HIT for user xxx, key=xxxxxxxx...`
- 流式响应: 与测试 1 内容完全一致
- 响应速度: 比测试 1 更快（无需调用上游 API）

### 2.4 测试 3: 不同请求（预期 MISS）

```bash
curl -N -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "请用一句话介绍 JavaScript 的优点"}],
    "stream": true,
    "max_tokens": 100
  }'
```

**预期结果**:
- 后端日志: `Stream cache MISS for user xxx, key=yyyyyyyy...`（不同的 cache key）
- 流式响应: 与测试 1/2 内容不同

---

## 三、验证缓存统计

### 3.1 查询缓存统计

```bash
curl -X GET "${BASE_URL}/api/user/cache/stats" \
  -H "Authorization: Bearer ${API_KEY}"
```

**预期结果**:
```json
{
  "hit_count": 1,
  "miss_count": 2,
  "hit_rate": 0.33,
  "saved_tokens": 150,
  "saved_cost": 0.000450
}
```

### 3.2 查询 Redis 缓存

```bash
# 查看所有缓存键
redis-cli KEYS "cache:stream:*"

# 查看用户缓存键集合
redis-cli SMEMBERS "cache:user_keys:1"

# 查看具体缓存内容（替换为实际的 cache_key）
redis-cli GET "cache:stream:xxxxxxxxxxxxxxxx"
```

---

## 四、验证事件序列

### 4.1 OpenAI 格式（默认）

**预期事件序列**:
```
data: {"id":"chatcmpl-cache-xxx","object":"chat.completion.chunk","choices":[{"delta":{"content":"Python"}}]}

data: {"id":"chatcmpl-cache-xxx","object":"chat.completion.chunk","choices":[{"delta":{"content":"是一门"}}]}

...

data: {"id":"chatcmpl-cache-xxx","object":"chat.completion.chunk","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 4.2 Anthropic 格式

**测试请求**:
```bash
curl -N -X POST "${BASE_URL}/v1/messages" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true,
    "max_tokens": 50
  }'
```

**预期事件序列**:
```
event: message_start
data: {"type":"message_start","message":{...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":10}}

event: message_stop
data: {"type":"message_stop"}
```

---

## 五、故障排查

### 5.1 HTTP 500 错误

**可能原因**:
1. Redis 未启动
2. 数据库连接失败
3. API Key 无效或用户不存在
4. 上游 API 配置错误

**排查步骤**:
```bash
# 1. 检查 Redis
redis-cli ping

# 2. 检查数据库
mysql -u root -p -e "SELECT * FROM modelinvoke.sys_user WHERE id=1;"

# 3. 检查 API Key
mysql -u root -p -e "SELECT * FROM modelinvoke.sys_api_key WHERE api_key='sk-8f698230bcb52e4c210b039e5cfcac6c66396dfa3d6ee78c';"

# 4. 查看后端日志
# 在后端服务的控制台查看详细错误堆栈
```

### 5.2 缓存未命中

**可能原因**:
1. 缓存已过期（默认 TTL 3600 秒）
2. 请求参数不同（messages、model、max_tokens 等）
3. 缓存被清空

**排查步骤**:
```bash
# 查看 Redis 中的缓存键
redis-cli KEYS "cache:stream:*"

# 查看缓存内容
redis-cli GET "cache:stream:xxxxxxxx"

# 查看后端日志中的 cache key
# 日志格式: Stream cache MISS for user xxx, key=xxxxxxxx...
```

### 5.3 事件序列不完整

**排查步骤**:
1. 使用 `curl -N` 确保不缓冲输出
2. 检查后端日志中是否有异常
3. 使用 `tcpdump` 或 Wireshark 抓包查看实际响应

---

## 六、自动化测试脚本

测试脚本位置: `/Volumes/project/modelInvocationSystem/backend/test_stream_cache.py`

**运行方式**:
```bash
cd /Volumes/project/modelInvocationSystem/backend
conda activate ai-invoke-service
python test_stream_cache.py
```

**注意事项**:
- 确保 Redis 和后端服务已启动
- 确保 API Key 有效
- 脚本会自动执行 4 次请求并验证缓存行为

---

## 七、验收标准

### 7.1 功能验收

- [ ] 第一次请求返回 MISS，创建缓存
- [ ] 第二次相同请求返回 HIT，从缓存读取
- [ ] 缓存命中时响应内容与 MISS 时完全一致
- [ ] 缓存命中时响应速度明显更快
- [ ] 不同请求生成不同的 cache key

### 7.2 事件序列验收

- [ ] OpenAI 格式: 完整的 delta chunks + `[DONE]`
- [ ] Anthropic 格式: 完整的 6 个事件（message_start → content_block_start → content_block_delta → content_block_stop → message_delta → message_stop）
- [ ] Responses API 格式: 完整的前置事件 + delta + 结束事件

### 7.3 统计验收

- [ ] 缓存统计 API 返回正确的 hit_count 和 miss_count
- [ ] Redis 中存储了正确的缓存数据
- [ ] 数据库中记录了缓存日志（cache_log 表）
- [ ] 用户表中更新了缓存统计（cache_hit_count、cache_saved_tokens）

---

## 八、已知限制

### 8.1 X-Cache-Status 响应头

**限制**: `X-Cache-Status` 响应头固定为 `"STREAM"`，无法反映实际的 HIT/MISS 状态。

**原因**: FastAPI/Starlette 的 `StreamingResponse` 在构造时就固定了 headers，此时 generator 尚未执行，无法获取实际的缓存状态。

**解决方案**: 实际的缓存状态通过后端日志记录：
- `Stream cache HIT for user xxx, key=xxxxxxxx...`
- `Stream cache MISS for user xxx, key=xxxxxxxx...`

### 8.2 缓存 TTL

**默认 TTL**: 3600 秒（1 小时）

**自定义 TTL**: 通过请求头 `X-Cache-TTL` 设置（单位：秒）
```bash
curl -N -X POST "${BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "X-Cache-TTL: 7200" \
  -d '...'
```

---

## 九、相关文档

- **Codex Review 报告**: `md/codex-review-stream-cache-round3-20260321.md`
- **实现文档**: `md/impl-ai-request-cache-20260321.md`
- **计划文档**: `md/plan-ai-request-cache-20260321-v2.md`

---

**测试完成后请更新本文档的验收标准清单。**
