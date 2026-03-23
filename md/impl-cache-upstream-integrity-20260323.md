# Cache Upstream Integrity Impl

## 任务概述

本次调整的目标是恢复 Claude 请求到上游 `http://43.156.153.12:8080/` 时的默认透传行为，避免系统为了兼容或缓存而修改请求体、删除请求头或触发二次兼容重试。

调整后：

- 缓存仍然只在系统内部使用 Redis 等基础设施实现
- 不再因为兼容逻辑删除 Anthropic 请求参数
- 不再删除客户端传入的 `anthropic-beta`
- 不再对 `43.156.153.12` Claude 链路做 legacy 兼容识别与兼容重试

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `md/plan-cache-upstream-integrity-20260323.md`
- `md/impl-cache-upstream-integrity-20260323.md`

## 核心代码说明

### 1. 停用 legacy `43.156.153.12` Claude relay 特殊识别

将 `_is_legacy_kiro_amazonq_host()` 改为直接返回 `False`。

结果：

- 不再把 `43.156.153.12` 当作需要兼容重试的特殊 Claude relay
- 不再触发兼容分支下的二次转发
- `43.156` Claude 链路恢复为按原始请求只发送一次

### 2. 停用显式 Kiro / AmazonQ 兼容识别

将 `_is_kiro_amazonq_channel()` 和 `_should_apply_kiro_amazonq_compat()` 改为直接返回 `False`。

结果：

- 代理不再因渠道名称、描述或 IP 信息进入兼容改写模式
- 上游请求参数恢复默认透传

### 3. 恢复 OpenAI / Anthropic 请求体默认透传

将以下两个预处理函数恢复为深拷贝后原样返回：

- `_prepare_openai_request_for_channel()`
- `_prepare_anthropic_request_for_channel()`

同时将 `_sanitize_anthropic_content_for_kiro()` 改为仅做深拷贝，不再删除：

- `cache_control`
- `signature`
- `thinking`
- `redacted_thinking`

结果：

- 不再删除顶层 `thinking`、`context_management`、`output_config`、`metadata`、`betas`
- 不再清洗消息 block 内容
- 上游收到的请求体与客户端原始请求保持一致

### 4. 恢复 Anthropic 请求头默认透传

删除 `_build_headers()` 中对 `anthropic-beta` 的删除逻辑。

结果：

- 即使请求带 `anthropic-beta`，也会继续透传到上游
- 请求头不再因为兼容逻辑被改写

## 未修改内容

以下缓存能力保留不变：

- `CacheMiddleware`
- `StreamCacheMiddleware`
- `CacheService`
- `CacheStatsService`
- Redis 存储结构和缓存统计

本次只处理“上游请求完整性”，没有改动系统内部 Redis 缓存读写。

## 测试验证

已完成：

1. 语法校验

```bash
python -m py_compile backend/app/services/proxy_service.py
```

2. 定向行为校验

使用 `PYTHONPATH=backend python` 直接调用静态方法验证：

- `_is_legacy_kiro_amazonq_host(...) == False`
- `_is_kiro_amazonq_channel(...) == False`
- `_should_apply_kiro_amazonq_compat(...) == False`
- `_prepare_anthropic_request_for_channel()` 返回值与输入完全一致
- `_build_headers()` 不再删除 `anthropic-beta`

## 待继续验证

- 用真实 Claude / Claude Code 请求再次验证 `43.156.153.12:8080` 链路是否恢复正常对话
- 观察上游若仍报错，是否为上游自身对参数或上下文大小的限制，而非本系统删字段导致
