# Cloudflare 524 超时修复 Plan

## 用户原始需求

当前项目是已部署到正式环境的 AI 中转站，域名通过 Cloudflare CDN 解析。用户请求后端接口时偶发 `API Error: 524`，Cloudflare 返回说明源站已建立连接，但 120 秒 Proxy Read Timeout 窗口内没有返回完整响应。需要深度阅读项目并处理该生产问题。

## 技术方案设计

### 问题判断

- Cloudflare 524 的关键条件是连接已建立，但源站长时间没有向 Cloudflare 输出响应字节。
- 当前代理服务流式接口在等待上游首个 token 期间不会向客户端输出任何字节；如果上游首包超过 Cloudflare 读取窗口，会触发 524。
- 当前非流式文本请求默认上游读取超时为 120 秒，图片请求为 300 秒；非流式长请求在 Cloudflare 代理模式下天然容易超过 120 秒，不能只靠提高源站超时解决。
- 当前 Nginx `proxy_read_timeout` 为 60 秒，低于 Cloudflare 读取窗口；流式链路虽然关闭 buffering，但缺少 `X-Accel-Buffering: no` 等响应头。

### 核心修复

- 为所有后端 SSE 流式响应增加首包注释心跳与周期心跳，保证即使上游长时间无 token，也能持续向 Cloudflare 输出字节。
- 统一流式响应头，加入 `Cache-Control: no-cache, no-transform` 与 `X-Accel-Buffering: no`，避免代理层缓存/压缩/缓冲影响 SSE。
- 调整 Nginx API 配置，把后端读取/发送超时提高到适合长连接的窗口，并显式关闭 gzip/buffering。
- 明确非流式超过 120 秒的请求仍可能被 Cloudflare 524，后续应引导客户端使用 `stream=true` 或改异步任务轮询。

## 涉及文件清单

- `backend/app/config.py`
- `backend/app/services/proxy_service.py`
- `backend/app/test/test_stream_heartbeat.py`
- `nginx/api.xiaoleai.team.conf`
- `nginx/agent-api-subdomain.template.conf`
- `md/impl-Cloudflare-524超时修复-20260505.md`

## 实施步骤概要

- [x] 阅读后端入口、代理路由、代理服务、Nginx 配置。
- [ ] 增加可配置的 SSE 心跳间隔。
- [ ] 在 `ProxyService` 增加通用 SSE 心跳包装器和统一响应头方法。
- [ ] 将五个 `StreamingResponse` 返回点切换到通用包装器。
- [ ] 更新 Nginx API 配置和代理 API 模板。
- [ ] 增加心跳单元测试。
- [ ] 运行 Python 编译和相关测试。
- [ ] 创建 Impl 文档并执行自审。
