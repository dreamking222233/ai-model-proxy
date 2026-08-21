# OpenClaw 接入配置指南

本文档说明如何将 OpenClaw 接入本 AI 模型中转平台，避免常见的 403/404 错误。

## 📋 快速开始

### 1. 获取 API Key

1. 登录平台：`https://your-domain.com`
2. 进入"API 密钥管理"页面
3. 创建新的 API Key（格式：`sk-xxxxxx`）
4. 复制并妥善保存 API Key

### 2. 配置 OpenClaw

编辑 `~/.openclaw/openclaw.json` 和 `~/.openclaw/agents/main/agent/models.json`，添加以下配置：

## 🔧 配置方案

### 方案一：Anthropic 协议（推荐）

**优点**：兼容性最好，不易出错

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "your-relay": {
        "baseUrl": "https://your-domain.com",
        "apiKey": "sk-your-api-key-here",
        "api": "anthropic-messages",
        "headers": {
          "User-Agent": "Mozilla/5.0"
        },
        "models": [
          {
            "id": "claude-sonnet-4",
            "name": "Claude Sonnet 4",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {
              "input": 0,
              "output": 0,
              "cacheRead": 0,
              "cacheWrite": 0
            },
            "contextWindow": 200000,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "your-relay/claude-sonnet-4"
      }
    }
  }
}
```

**关键配置说明**：
- `baseUrl`: **不要**包含 `/v1`，只写域名
- `api`: 必须是 `anthropic-messages`（严格枚举）
- `headers.User-Agent`: 建议显式设置，便于穿透某些上游 WAF
- OpenClaw 自定义 Anthropic 校验默认更接近 `x-api-key` + `anthropic-version`

### 方案二：OpenAI 协议

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "your-relay": {
        "baseUrl": "https://your-domain.com/v1",
        "apiKey": "sk-your-api-key-here",
        "api": "openai-completions",
        "headers": {
          "User-Agent": "Mozilla/5.0"
        },
        "models": [
          {
            "id": "gpt-4",
            "name": "GPT-4",
            "reasoning": false,
            "input": ["text"],
            "cost": {
              "input": 0,
              "output": 0
            },
            "contextWindow": 128000,
            "maxTokens": 4096
          }
        ]
      }
    }
  }
}
```

**关键配置说明**：
- `baseUrl`: 推荐包含 `/v1` 路径；本平台也兼容不带 `/v1` 的写法
- `api`: 必须是 `openai-completions`（严格枚举）

## 🚨 常见问题排查

### 问题 1：403 错误 "Your request was blocked"

**常见原因**：
- 上游要求的认证 header 与实际发送的不一致
- OpenClaw / curl / 中转之间的请求头存在差异
- 某些上游或 WAF 会额外检查 `User-Agent`

**排查建议**：
```json
"headers": {
  "User-Agent": "Mozilla/5.0"
}
```

并同时核对：
- Anthropic 协议时，客户端更常见的是 `X-API-Key` + `anthropic-version`
- OpenAI 协议时，通常是 `Authorization: Bearer ...`
- 如果上游要求特殊认证头，请在中转后台按上游要求配置

### 问题 2：404 错误（路径变成 /v1/v1/messages）

**原因**：baseUrl 配置错误

**解决**：
- Anthropic 协议：`baseUrl` **不要**包含 `/v1`
- OpenAI 协议：`baseUrl` **需要**包含 `/v1`

### 问题 3：配置不生效

**原因**：只修改了一处配置文件

**解决**：必须同时修改两个文件：
1. `~/.openclaw/openclaw.json`
2. `~/.openclaw/agents/main/agent/models.json`

修改后执行验证：
```bash
openclaw models status
openclaw models list --provider your-relay
```

### 问题 4：API 字段报错 "Config invalid"

**原因**：`api` 字段值不正确

**解决**：只允许以下 3 个值：
- `anthropic-messages`
- `openai-completions`
- `openai-responses`

**错误示例**（不要这样写）：
- ❌ `"api": "openai"`
- ❌ `"api": "openai-chat"`
- ❌ `"api": "anthropic"`

### 问题 5：请求成功但界面空回复

**原因**：OpenAI 协议返回格式映射问题

**解决**：切换到 Anthropic 协议（方案一）

## 📡 支持的 API 端点

本平台同时支持以下端点格式：

### Anthropic 协议
- ✅ `POST /v1/messages`（标准格式）
- ✅ `POST /messages`（兼容格式，推荐用于 OpenClaw）

### OpenAI 协议
- ✅ `POST /v1/chat/completions`（标准格式）
- ✅ `POST /chat/completions`（兼容格式）
- ✅ `GET /v1/models`（模型列表）
- ✅ `GET /models`（模型列表，兼容格式）

## 🧪 测试验证

### 使用 curl 测试

**Anthropic 协议**：
```bash
curl https://your-domain.com/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-your-api-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

也可以测试入口对兼容头的支持：

```bash
curl https://your-domain.com/messages \
  -H "Content-Type: application/json" \
  -H "anthropic-api-key: sk-your-api-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

**OpenAI 协议**：
```bash
curl https://your-domain.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

### 使用 OpenClaw 命令测试

```bash
# 查看模型状态
openclaw models status

# 查看指定 provider 的模型
openclaw models list --provider your-relay

# 综合诊断
openclaw doctor

# 查看实时日志
tail -f /tmp/openclaw/openclaw-$(date +%F).log
```

## 📝 完整配置示例

### 多模型配置示例

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "your-relay": {
        "baseUrl": "https://your-domain.com",
        "apiKey": "sk-your-api-key-here",
        "api": "anthropic-messages",
        "headers": {
          "User-Agent": "Mozilla/5.0"
        },
        "models": [
          {
            "id": "claude-sonnet-4",
            "name": "Claude Sonnet 4",
            "reasoning": false,
            "input": ["text", "image"],
            "contextWindow": 200000,
            "maxTokens": 8192
          },
          {
            "id": "claude-opus-4",
            "name": "Claude Opus 4",
            "reasoning": false,
            "input": ["text", "image"],
            "contextWindow": 200000,
            "maxTokens": 4096
          },
          {
            "id": "gpt-4",
            "name": "GPT-4",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 128000,
            "maxTokens": 4096
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "your-relay/claude-sonnet-4",
        "fallback": "your-relay/gpt-4"
      }
    }
  }
}
```

## 🔍 排查流程

按以下顺序排查问题：

1. **验证 API Key 有效性**
   ```bash
   curl https://your-domain.com/v1/models \
     -H "Authorization: Bearer sk-your-api-key"
   ```

2. **对比 curl 和 OpenClaw 请求差异**
   - User-Agent
   - URL 路径
   - 认证 header（Authorization / X-API-Key / anthropic-api-key）
   - API 协议格式
   - 是否存在 `/models` 探测请求

3. **校验 api 字段值**
   - 必须是严格枚举值
   - 不能自定义

4. **同步修改两处配置文件**
   - `openclaw.json`
   - `agents/main/agent/models.json`

5. **执行验证命令**
   ```bash
   openclaw models status
   openclaw doctor
   ```

## 💡 最佳实践

1. **优先使用 Anthropic 协议**
   - 兼容性更好
   - 不易出现路径问题

2. **始终添加自定义 User-Agent**
   ```json
   "headers": {
     "User-Agent": "Mozilla/5.0"
   }
   ```

3. **baseUrl 不要包含 /v1**（Anthropic 协议）
   ```json
   "baseUrl": "https://your-domain.com"
   ```

4. **修改配置后立即验证**
   ```bash
   openclaw models status
   ```

5. **OpenAI 协议优先使用带 `/v1` 的 baseUrl**
   ```json
   "baseUrl": "https://your-domain.com/v1"
   ```

6. **查看日志定位问题**
   ```bash
   tail -f /tmp/openclaw/openclaw-$(date +%F).log
   ```

## 📞 技术支持

如果按照本文档配置后仍有问题，请提供以下信息：

1. OpenClaw 版本：`openclaw --version`
2. 配置文件内容（隐藏 API Key）
3. 错误日志：`~/.openclaw/agents/main/sessions/{sessionId}.jsonl`
4. curl 测试结果

## 🔗 相关链接

- [平台管理后台](https://your-domain.com/admin)
- [用户控制台](https://your-domain.com/user)
- [API 文档](https://your-domain.com/docs)

---

**最后更新**：2026-03-17
