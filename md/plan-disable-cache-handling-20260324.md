# Disable Cache Handling Plan

## 用户原始需求

- 关闭缓存
- 清除所有缓存相关的处理
- 避免缓存继续影响请求链路和正常对话

## 技术方案设计

### 1. 问题判断

当前缓存相关逻辑不仅包括 Redis 读写本身，还包括：

- `CacheMiddleware` / `StreamCacheMiddleware` 在代理主链路中的接入
- `ProxyService` 中基于缓存命中状态的计费和响应头处理
- `main.py` 中注册的用户端 / 管理端缓存接口

即使前一轮已经恢复了上游请求默认透传，缓存处理仍然挂在运行时主链路中，并继续暴露缓存语义（如 `X-Cache-Status`）。

### 2. 目标

本次目标不是迁移数据库，而是把缓存从运行时逻辑中彻底摘掉：

1. 代理请求主链路不再执行缓存读写、缓存统计、缓存重放
2. 不再在响应里暴露缓存状态
3. 不再注册缓存专用 API 路由
4. 避免运行时因为缓存代码 import 而初始化 Redis

### 3. 实施原则

- 保留数据库字段、历史表、缓存文件，避免扩大成数据迁移任务
- 将缓存中间件改为纯透传，确保现有调用点不需要大规模重构
- 从应用入口移除缓存路由，停止对外暴露缓存管理能力
- 移除响应头中的缓存语义，避免客户端误判

## 涉及文件清单

- `backend/app/middleware/cache_middleware.py`
- `backend/app/middleware/stream_cache_middleware.py`
- `backend/app/services/proxy_service.py`
- `backend/app/main.py`
- `md/plan-disable-cache-handling-20260324.md`
- `md/impl-disable-cache-handling-20260324.md`

## 实施步骤概要

1. 将 `CacheMiddleware` 改为纯透传，不再依赖 Redis / cache service / stats service
2. 将 `StreamCacheMiddleware` 改为纯透传，仅保留流式调用所需的 collector 占位能力
3. 从 `ProxyService` 中移除缓存状态响应头
4. 从 `main.py` 中移除缓存 API 路由注册
5. 执行本地语法校验
6. 编写 impl 文档并做一次本地自审
