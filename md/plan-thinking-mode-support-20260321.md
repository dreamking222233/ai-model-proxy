# Thinking 模式支持 - 实施计划

**日期**: 2026-03-21
**功能**: 为系统添加 Claude Thinking 模式支持
**渠道**: 43.156.153.12-Claude (ID: 9)

---

## 一、需求分析

### 1.1 Thinking 模式特性

**Anthropic 协议** (`/v1/messages`):
- 请求模型名: `claude-sonnet-4.5-thinking`, `claude-haiku-4.5-thinking`
- 响应包含 `thinking` 类型的 content block
- 结构:
```json
{
  "content": [
    {"type": "thinking", "thinking": "思考过程..."},
    {"type": "text", "text": "最终回答"}
  ]
}
```

**OpenAI 协议** (`/v1/chat/completions`):
- 请求模型名: `claude-sonnet-4-5-thinking`, `claude-haiku-4-5-thinking`
- 响应包含 `reasoning_content` 字段
- 结构:
```json
{
  "message": {
    "reasoning_content": "思考过程...",
    "content": "最终回答"
  }
}
```

### 1.2 系统支持协议

当前系统支持三种输出协议:
1. **OpenAI 协议** - `/v1/chat/completions`
2. **Anthropic 协议** - `/v1/messages`
3. **Responses API** - WebSocket 协议

需要确保 thinking 内容在所有协议中正确转换和输出。

---

## 二、数据库配置

### 2.1 统一模型创建 ✅

已完成:
```sql
INSERT INTO unified_model VALUES
(26, 'claude-sonnet-4-5-thinking', 'Claude Sonnet 4.5 Thinking', 'chat', 'openai', 8192, 3.000000, 15.000000, 1, ...),
(27, 'claude-haiku-4-5-thinking', 'Claude Haiku 4.5 Thinking', 'chat', 'openai', 8192, 0.800000, 4.000000, 1, ...);
```

### 2.2 模型映射创建 ✅

已完成:
```sql
INSERT INTO model_channel_mapping VALUES
(51, 26, 9, 'claude-sonnet-4-5-thinking', 1),
(52, 27, 9, 'claude-haiku-4-5-thinking', 1);
```

---

## 三、后端实现

### 3.1 核心处理逻辑

**位置**: `backend/app/services/proxy_service.py`

#### 3.1.1 Anthropic → OpenAI 转换

当上游返回 Anthropic 格式时，需要转换为 OpenAI 格式:

```python
def _convert_anthropic_thinking_to_openai(anthropic_response: dict) -> dict:
    """
    Convert Anthropic thinking response to OpenAI format.

    Input (Anthropic):
    {
      "content": [
        {"type": "thinking", "thinking": "..."},
        {"type": "text", "text": "..."}
      ]
    }

    Output (OpenAI):
    {
      "choices": [{
        "message": {
          "reasoning_content": "...",
          "content": "..."
        }
      }]
    }
    """
```

#### 3.1.2 OpenAI → Anthropic 转换

当上游返回 OpenAI 格式时，需要转换为 Anthropic 格式:

```python
def _convert_openai_thinking_to_anthropic(openai_response: dict) -> dict:
    """
    Convert OpenAI thinking response to Anthropic format.

    Input (OpenAI):
    {
      "message": {
        "reasoning_content": "...",
        "content": "..."
      }
    }

    Output (Anthropic):
    {
      "content": [
        {"type": "thinking", "thinking": "..."},
        {"type": "text", "text": "..."}
      ]
    }
    """
```

#### 3.1.3 流式响应处理

**OpenAI 流式**:
- 需要在 SSE 流中添加 `reasoning_content` 字段
- 格式: `data: {"choices":[{"delta":{"reasoning_content":"..."}}]}`

**Anthropic 流式**:
- 需要添加 `content_block_start` 事件 (type: thinking)
- 需要添加 `content_block_delta` 事件 (delta.thinking)
- 格式:
```
event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"..."}}
```

### 3.2 修改点

#### 3.2.1 非流式请求处理

**OpenAI 协议** (`proxy_openai_chat_completion`):
1. 检测上游响应是否包含 thinking 内容
2. 如果用户请求 Anthropic 格式，转换为 Anthropic 格式
3. 如果用户请求 OpenAI 格式，保持原样

**Anthropic 协议** (`proxy_anthropic_messages`):
1. 检测上游响应是否包含 thinking 内容
2. 如果用户请求 OpenAI 格式，转换为 OpenAI 格式
3. 如果用户请求 Anthropic 格式，保持原样

#### 3.2.2 流式请求处理

**OpenAI 流式** (`_proxy_openai_stream`):
1. 解析 SSE 流中的 thinking 内容
2. 如果用户请求 Anthropic 格式，转换事件序列
3. 如果用户请求 OpenAI 格式，保持原样

**Anthropic 流式** (`_proxy_anthropic_stream`):
1. 解析 SSE 流中的 thinking 内容
2. 如果用户请求 OpenAI 格式，转换事件序列
3. 如果用户请求 Anthropic 格式，保持原样

---

## 四、实施步骤

### Step 1: 添加 Thinking 检测函数
- 检测响应是否包含 thinking 内容
- 支持 OpenAI 和 Anthropic 两种格式

### Step 2: 添加格式转换函数
- Anthropic → OpenAI
- OpenAI → Anthropic
- 流式和非流式分别处理

### Step 3: 集成到现有代理逻辑
- 修改 `proxy_openai_chat_completion`
- 修改 `proxy_anthropic_messages`
- 修改 `_proxy_openai_stream`
- 修改 `_proxy_anthropic_stream`

### Step 4: 测试验证
- 测试 OpenAI → OpenAI (保持原样)
- 测试 Anthropic → Anthropic (保持原样)
- 测试 OpenAI → Anthropic (转换)
- 测试 Anthropic → OpenAI (转换)
- 测试流式和非流式

---

## 五、关键注意事项

### 5.1 协议识别

用户请求的协议由请求路径决定:
- `/v1/chat/completions` → OpenAI 协议
- `/v1/messages` → Anthropic 协议

上游响应的协议由渠道的 `protocol_type` 决定:
- `protocol_type = "openai"` → 上游返回 OpenAI 格式
- `protocol_type = "anthropic"` → 上游返回 Anthropic 格式

### 5.2 Token 统计

Thinking 内容也会消耗 tokens，需要正确统计:
- OpenAI 格式: `usage.completion_tokens` 包含 thinking + content
- Anthropic 格式: `usage.output_tokens` 包含 thinking + content

### 5.3 缓存兼容性

Thinking 模式的响应结构不同，需要确保:
- 缓存键生成不受 thinking 影响
- 缓存内容包含完整的 thinking 信息
- 缓存重放时正确还原 thinking 内容

---

## 六、文件清单

### 修改文件
1. `backend/app/services/proxy_service.py` - 核心代理逻辑

### 新增文件
1. `md/plan-thinking-mode-support-20260321.md` - 本计划文档
2. `md/impl-thinking-mode-support-20260321.md` - 实施报告（待创建）

---

**计划版本**: 1.0
**最后更新**: 2026-03-21
