# AI 客户端接入指南

本文档说明如何将各种 AI 客户端（OpenClaw、Cursor、Continue、Cline 等）接入本中转平台。

## 🎯 核心原则

### 1. 路径兼容性

本平台同时支持带 `/v1` 和不带 `/v1` 的路径：

| 协议 | 标准路径 | 兼容路径 |
|------|---------|---------|
| Anthropic | `/v1/messages` | `/messages` |
| OpenAI | `/v1/chat/completions` | `/chat/completions` |
| Models | `/v1/models` | `/models` |

**配置建议**：
- 如果客户端自动添加 `/v1`：baseUrl 不要包含 `/v1`
- 如果客户端不添加 `/v1`：baseUrl 需要包含 `/v1`

### 2. Header 兼容性

本平台入口同时兼容多种常见认证头：
- ✅ `Authorization: Bearer sk-...`
- ✅ `X-API-Key: sk-...`
- ✅ `anthropic-api-key: sk-...`

另外，平台会向上游透传有限白名单头（如 `User-Agent`、`anthropic-version`、`anthropic-beta`、`OpenAI-Organization`、`OpenAI-Project`），便于兼容 OpenClaw 与部分上游网关。

### 3. 认证方式

支持三种常见 API Key 认证方式：

```bash
# 方式 1：Authorization Bearer
Authorization: Bearer sk-your-api-key

# 方式 2：X-API-Key
X-API-Key: sk-your-api-key

# 方式 3：Anthropic 兼容头
anthropic-api-key: sk-your-api-key
```

## 📱 客户端配置示例

### OpenClaw

详见：[OpenClaw 接入配置指南](./openclaw-integration.md)

**推荐配置**（Anthropic 协议）：
```json
{
  "baseUrl": "https://your-domain.com",
  "apiKey": "sk-your-api-key",
  "api": "anthropic-messages",
  "headers": {
    "User-Agent": "Mozilla/5.0"
  }
}
```

说明：
- `anthropic-messages` 推荐 `baseUrl` 不带 `/v1`
- `openai-completions` 推荐 `baseUrl` 带 `/v1`
- OpenClaw 的 Anthropic 自定义校验更接近 `X-API-Key` + `anthropic-version`

### Cursor

1. 打开 Cursor 设置
2. 找到"OpenAI API Key"配置
3. 填入：
   - API Key: `sk-your-api-key`
   - Base URL: `https://your-domain.com/v1`

### Continue (VS Code 插件)

编辑 `~/.continue/config.json`：

```json
{
  "models": [
    {
      "title": "Your Relay GPT-4",
      "provider": "openai",
      "model": "gpt-4",
      "apiKey": "sk-your-api-key",
      "apiBase": "https://your-domain.com/v1"
    }
  ]
}
```

### Cline (VS Code 插件)

1. 打开 Cline 设置
2. 选择"Custom API"
3. 填入：
   - API Key: `sk-your-api-key`
   - Base URL: `https://your-domain.com/v1`
   - Model: 选择可用模型

### OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-your-api-key",
    base_url="https://your-domain.com/v1"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Anthropic Python SDK

```python
from anthropic import Anthropic

client = Anthropic(
    api_key="sk-your-api-key",
    base_url="https://your-domain.com"  # 不要包含 /v1
)

response = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```

### LangChain

```python
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(
    model_name="gpt-4",
    openai_api_key="sk-your-api-key",
    openai_api_base="https://your-domain.com/v1"
)
```

### LlamaIndex

```python
from llama_index.llms import OpenAI

llm = OpenAI(
    model="gpt-4",
    api_key="sk-your-api-key",
    api_base="https://your-domain.com/v1"
)
```

## 🧪 测试验证

### 快速测试

```bash
# 测试 OpenAI 协议
curl https://your-domain.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'

# 测试 Anthropic 协议
curl https://your-domain.com/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-your-api-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'

# 获取模型列表
curl https://your-domain.com/v1/models \
  -H "Authorization: Bearer sk-your-api-key"
```

### 验证清单

- [ ] API Key 有效
- [ ] baseUrl 配置正确
- [ ] 模型名称存在
- [ ] 余额充足（按量计费用户）
- [ ] 套餐未过期（时间套餐用户）

## 🚨 常见问题

### 401 Unauthorized

**可能原因**：
1. API Key 无效或已过期
2. API Key 被禁用
3. 用户账户被禁用

**解决方法**：
1. 检查 API Key 是否正确
2. 登录平台查看 API Key 状态
3. 联系管理员

### 403 Forbidden

**可能原因**：
1. 时间套餐已过期
2. 用户账户被禁用
3. 上游兼容网关要求的认证 header 或 `User-Agent` 不匹配

**解决方法**：
1. 检查套餐有效期
2. 充值余额或续费套餐
3. 核对客户端发往中转的 header 以及中转后台的上游认证配置

### 404 Not Found

**可能原因**：
1. baseUrl 配置错误（路径重复）
2. 模型名称不存在

**解决方法**：
1. 检查 baseUrl 是否包含多余的 `/v1`
2. 使用 `/v1/models` 端点查看可用模型

### 余额不足

**错误信息**：`Insufficient balance`

**解决方法**：
1. 登录平台查看余额
2. 联系管理员充值
3. 或切换到时间套餐模式

## 📊 计费说明

### 按量计费模式

- 根据实际 Token 消耗计费
- 费用 = (输入 Token × 输入单价 + 输出 Token × 输出单价) × 价格倍率 × Token 倍率
- 余额不足时无法调用

### 时间套餐模式

- 在有效期内无限使用
- 不扣除余额
- 过期后自动停止服务

## 🔧 高级配置

### 自定义请求头

某些客户端支持自定义请求头，可以添加：

```json
{
  "headers": {
    "User-Agent": "MyApp/1.0",
    "X-Custom-Header": "value"
  }
}
```

### 流式输出

本平台完全支持流式输出（SSE）：

```python
# OpenAI SDK
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True  # 启用流式输出
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")
```

### 超时设置

建议设置合理的超时时间：

```python
client = OpenAI(
    api_key="sk-your-api-key",
    base_url="https://your-domain.com/v1",
    timeout=60.0  # 60 秒超时
)
```

## 📞 获取帮助

如果遇到问题：

1. **查看日志**：登录平台查看请求日志和错误详情
2. **测试 API**：使用 curl 命令测试基本连通性
3. **检查配置**：对照本文档检查配置是否正确
4. **联系支持**：提供错误日志和配置信息

## 🔗 相关文档

- [OpenClaw 接入配置指南](./openclaw-integration.md)
- [API 参考文档](./api-reference.md)
- [计费说明](./billing.md)

---

**最后更新**：2026-03-17
