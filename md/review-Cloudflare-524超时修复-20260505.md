# Cloudflare 524 超时修复 Review

## Findings

- Low: `nginx/api.xiaoleai.team.conf:41-42` 与 `nginx/agent-api-subdomain.template.conf:34-35` 仍然对所有请求固定发送 `Connection "upgrade"`。这对 WebSocket 可以，但对 SSE / 普通 HTTP POST 并不理想，建议改成基于 `$http_upgrade` 的条件映射，或拆分 WebSocket 与常规 API 的 location，避免把 hop-by-hop upgrade 语义带到流式文本请求里。
- Low: `backend/app/test/test_stream_heartbeat.py:10-39` 只验证了“心跳注释会发出”和“响应头已设置”，还没有覆盖 OpenAI / Anthropic / Responses 三条真实流式链路，也没有覆盖客户端中途断开时 `_with_sse_heartbeat()` 的取消与关闭路径。当前“兼容现有客户端”的结论更多是基于 SSE 规范和仓库内现有解析器行为推断，而不是端到端回归结果。
- Low: `nginx/api.xiaoleai.team.conf:50-61` 与 `nginx/agent-api-subdomain.template.conf:41-49` 将 `proxy_send_timeout` / `proxy_read_timeout` / `send_timeout` 全部提升到 `3600s`，这对流式请求是安全的，但对非流式长请求并不能绕过 Cloudflare 120 秒窗口，反而会放大异常请求的连接占用时间。建议后续按流式路由单独设置长超时，或在文档中明确这是“仅为 SSE 长连接兜底”的全局取舍。

## 结论

- `ProxyService._with_sse_heartbeat()` 使用 SSE 注释行 `: keep-alive`，协议层面是兼容的；仓库内现有解析器也只消费 `data:` / `event:` 行，例如 `frontend/src/utils/sse.js:71-85` 与 `frontend/src/utils/sse.js:169-180`，因此不会把心跳误当业务数据。就当前代码来看，OpenAI / Anthropic / Responses 三类客户端只要遵循标准 SSE 解析，均不应被破坏。
- 资源释放路径基本完整：`backend/app/services/proxy_service.py:3768-3797` 在 `finally` 中会取消未完成的 `__anext__()` task，并尝试 `aclose()` 上游异步迭代器；没有看到明显的连接泄漏或悬挂 task 路径。
- Nginx 新增的 `gzip off`、`proxy_buffering off`、`X-Accel-Buffering no` 与长超时设置，和本次“流式首包慢导致 Cloudflare 524”的目标是一致的。

## Residual Risk

- 非流式长请求仍可能在 Cloudflare 120 秒窗口内触发 524；这属于代理模式限制，不是本次流式心跳修复可以彻底消除的问题。
- 生产部署后仍需要实际执行 `nginx -t` 与 `nginx -s reload`，并用真实上游慢响应场景回归验证“首包前心跳持续可见”和“客户端主动断开后上游连接及时释放”。
