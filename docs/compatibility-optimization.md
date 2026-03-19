# 中转服务兼容性优化说明

## 📋 优化概述

本次优化主要解决 OpenClaw 等 AI 客户端接入中转平台时可能遇到的 403/404 错误问题。

## 🎯 解决的问题

### 1. 403 错误：认证头或上游拦截不兼容
**问题**：OpenClaw、curl、中转和上游之间的认证 header / `User-Agent` 可能不一致，部分上游或 WAF 会直接返回 403。

**我们的方案**：
- ✅ 本平台**不拦截**任何 User-Agent
- ✅ 中间件不检查 User-Agent
- ✅ 入口同时兼容 `Authorization`、`X-API-Key`、`anthropic-api-key`
- ✅ 向上游透传 `User-Agent`、Anthropic/OpenAI 常见附加头
- ✅ Anthropic 上游始终补齐 `anthropic-version`

### 2. 404 错误：路径重复
**问题**：客户端配置 `baseUrl: https://xxx.com/v1`，SDK 又自动拼接 `/v1/messages`，导致 `/v1/v1/messages`

**我们的方案**：
- ✅ 同时支持 `/v1/messages` 和 `/messages` 两种路径
- ✅ 同时支持 `/v1/chat/completions` 和 `/chat/completions`
- ✅ 客户端可以灵活配置 baseUrl

### 3. 配置混淆
**问题**：用户不清楚 baseUrl 应该包含还是不包含 `/v1`

**我们的方案**：
- ✅ 提供详细的接入文档
- ✅ 提供多种配置示例
- ✅ 说明不同协议的配置差异

## 🔧 技术实现

### 1. 新增 API 端点

#### Anthropic 协议
```python
# 原有端点（保持不变）
POST /v1/messages

# 新增兼容端点
POST /messages  # 不带 /v1 前缀
```

#### OpenAI 协议
```python
# 原有端点（保持不变）
POST /v1/chat/completions
GET /v1/models

# 新增兼容端点
POST /chat/completions  # 不带 /v1 前缀
GET /models             # 不带 /v1 前缀
```

### 2. 路由配置

**文件**：`backend/app/api/proxy/anthropic_proxy.py`
```python
@router.post("/v1/messages")
async def anthropic_messages_v1(...):
    """标准 Anthropic 端点"""
    pass

@router.post("/messages")
async def anthropic_messages_root(...):
    """兼容端点，用于 baseUrl 不含 /v1 的配置"""
    pass
```

**文件**：`backend/app/api/proxy/openai_proxy.py`
```python
@router.post("/v1/chat/completions")
async def openai_chat_completions_v1(...):
    """标准 OpenAI 端点"""
    pass

@router.post("/chat/completions")
async def openai_chat_completions_root(...):
    """兼容端点，用于 baseUrl 不含 /v1 的配置"""
    pass
```

### 3. 中间件验证

**文件**：`backend/app/core/middleware.py`
- ✅ 不检查 User-Agent
- ✅ 只记录请求日志
- ✅ 不拦截任何请求头

**文件**：`backend/app/core/dependencies.py`
- ✅ 只验证 API Key 有效性
- ✅ 不检查 User-Agent
- ✅ 支持三种常见认证方式（Authorization Bearer、X-API-Key、anthropic-api-key）

## 📚 文档

### 1. OpenClaw 专用接入指南
**文件**：`docs/openclaw-integration.md`

内容包括：
- 快速开始指南
- 两种配置方案（Anthropic 协议 vs OpenAI 协议）
- 常见问题排查（403/404/配置不生效等）
- 完整配置示例
- 测试验证方法
- 排查流程

### 2. 通用客户端接入指南
**文件**：`docs/client-integration-guide.md`

内容包括：
- 核心原则（路径兼容性、User-Agent 兼容性、认证方式）
- 多种客户端配置示例（OpenClaw、Cursor、Continue、Cline 等）
- SDK 使用示例（Python、LangChain、LlamaIndex）
- 测试验证方法
- 常见问题解答
- 计费说明

## 🧪 测试验证

### 测试 Anthropic 协议

```bash
# 测试标准端点
curl https://your-domain.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-your-api-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "claude-sonnet-4", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'

# 测试兼容端点
curl https://your-domain.com/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-your-api-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "claude-sonnet-4", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'
```

### 测试 OpenAI 协议

```bash
# 测试标准端点
curl https://your-domain.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'

# 测试兼容端点
curl https://your-domain.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'
```

### 测试模型列表

```bash
# 测试标准端点
curl https://your-domain.com/v1/models \
  -H "Authorization: Bearer sk-your-api-key"

# 测试兼容端点
curl https://your-domain.com/models \
  -H "Authorization: Bearer sk-your-api-key"
```

## 📊 兼容性矩阵

| 客户端 | 协议 | baseUrl 配置 | 状态 |
|--------|------|-------------|------|
| OpenClaw | Anthropic | `https://domain.com` | ✅ 完全兼容 |
| OpenClaw | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |
| Cursor | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |
| Continue | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |
| Cline | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |
| OpenAI SDK | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |
| Anthropic SDK | Anthropic | `https://domain.com` | ✅ 完全兼容 |
| LangChain | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |
| LlamaIndex | OpenAI | `https://domain.com/v1` | ✅ 完全兼容 |

## 🎉 优化效果

### 优化前
- ❌ 只支持 `/v1/messages` 和 `/v1/chat/completions`
- ❌ 用户配置 baseUrl 容易出错
- ❌ 缺少接入文档

### 优化后
- ✅ 同时支持带 `/v1` 和不带 `/v1` 的路径
- ✅ 灵活的 baseUrl 配置
- ✅ 详细的接入文档和示例
- ✅ 完全兼容 OpenClaw 等主流客户端
- ✅ 不拦截任何 User-Agent
- ✅ 支持多种认证头并透传关键附加头

## 🔄 向后兼容性

本次优化**完全向后兼容**：
- ✅ 原有端点保持不变
- ✅ 原有配置继续有效
- ✅ 不影响现有用户
- ✅ 只是新增了兼容端点

## 📝 更新日志

**2026-03-17**
- 新增 Anthropic 协议兼容端点 `/messages`
- 新增 OpenAI 协议兼容端点 `/chat/completions` 和 `/models`
- 创建 OpenClaw 接入配置指南
- 创建通用客户端接入指南
- 验证中间件不拦截任何 User-Agent

## 🔗 相关文档

- [OpenClaw 接入配置指南](./openclaw-integration.md)
- [通用客户端接入指南](./client-integration-guide.md)

---

**维护者**：AI Model Proxy Team
**最后更新**：2026-03-17
