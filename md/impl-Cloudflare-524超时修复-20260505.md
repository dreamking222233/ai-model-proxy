# Cloudflare 524 超时修复 Impl

## 任务概述

本次针对生产环境偶发 `Cloudflare 524` 做了链路级修复，重点处理 API 流式请求在上游首包较慢时，源站长时间无字节返回给 Cloudflare 的问题。

## 文件变更清单

- `backend/app/config.py`
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_stream_heartbeat.py`
- `nginx/api.xiaoleai.team.conf`
- `nginx/agent-api-subdomain.template.conf`
- `md/plan-Cloudflare-524超时修复-20260505.md`

## 核心代码说明

### 1. 后端统一 SSE 心跳

- 新增 `STREAM_HEARTBEAT_INTERVAL_SECONDS` 配置，默认 `20` 秒。
- 在 `ProxyService` 中新增：
  - `_stream_response_headers()`：统一设置 `Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no` 等 SSE 友好响应头。
  - `_with_sse_heartbeat()`：当上游流在等待首包或后续 chunk 时，定时输出 `: keep-alive` SSE 注释心跳。
  - `_build_streaming_response()`：统一包装所有 `StreamingResponse` 返回点。
- 已将 OpenAI / Anthropic / Responses 的 5 个流式 HTTP 响应入口全部切换到新包装器。

### 2. Nginx 长连接配置

- `api.xiaoleai.team.conf` 与 `agent-api-subdomain.template.conf` 均已调整：
  - 关闭 `gzip`
  - `proxy_send_timeout` / `proxy_read_timeout` / `send_timeout` 提升到 `3600s`
  - 显式关闭 `proxy_cache`
  - 打开 `chunked_transfer_encoding`
  - 增加 `X-Accel-Buffering: no`

### 3. 风险边界

- 这次修复主要解决“流式接口长时间无首包导致的 524”。
- 对于非流式长请求，如果源站到 Cloudflare 在 120 秒内始终没有任何响应字节，Cloudflare 代理模式下仍可能返回 524。
- 这类请求后续应优先改为 `stream=true`，或改造成异步任务 + 轮询结果。

## 测试验证

- `python -m py_compile backend/app/config.py backend/app/services/proxy_service.py backend/app/test/test_stream_heartbeat.py`
- `python -m unittest app.test.test_stream_heartbeat`

补充说明：
- 测试运行时出现 Redis 连接失败提示：`localhost:6379 Operation not permitted`。这是当前沙箱环境限制导致，测试本身已降级为禁用缓存并通过，不影响本次心跳逻辑验证。
