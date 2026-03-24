# Disable Cache Handling Impl

## 任务概述

本次调整的目标是清除系统运行时的缓存相关处理，避免缓存继续参与请求转发、流式响应、统计接口和客户端响应语义。

处理后：

- 请求主链路不再执行缓存读写
- 流式请求不再做缓存收集、缓存重放
- 对外不再注册缓存管理 API
- 响应中不再返回 `X-Cache-Status`

## 文件变更清单

- `backend/app/api/admin/cache.py`
- `backend/app/api/user/cache.py`
- `backend/app/middleware/cache_middleware.py`
- `backend/app/middleware/stream_cache_middleware.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/auth_service.py`
- `backend/app/schemas/user.py`
- `backend/app/main.py`
- `md/plan-disable-cache-handling-20260324.md`
- `md/impl-disable-cache-handling-20260324.md`

## 核心代码说明

### 1. `CacheMiddleware` 改为纯透传

`cache_middleware.py` 已不再：

- 引用 `cache_service`
- 引用 `CacheStatsService`
- 生成 cache key
- 查询或写入 Redis
- 处理缓存命中计费

当前行为：

- `wrap_request()` 直接执行 `upstream_call()`
- `get_billing_tokens()` 始终按实际 token 计费

### 2. `StreamCacheMiddleware` 改为纯透传

`stream_cache_middleware.py` 已不再：

- 查询流式缓存
- 保存流式缓存
- 重放缓存 SSE
- 引用 Redis / cache service / stats service

当前仅保留：

- `StreamCollector` 占位类，兼容现有调用签名
- `wrap_stream_request()` 直接把上游流式响应原样透传

### 3. 清理 `ProxyService` 中的缓存语义

在 `proxy_service.py` 中：

- 保留现有调用结构，继续调用中间件占位层
- 但由于中间件已经改为透传，请求链路不再执行缓存
- 删除所有 `X-Cache-Status` 响应头

这样客户端不再看到缓存命中/未命中状态，避免误判。

### 4. 下线缓存 API 路由

在 `main.py` 中移除：

- `admin_cache_router`
- `user_cache_router`

结果：

- 运行时不再注册 `/api/admin/cache/*`
- 运行时不再注册 `/api/user/cache/*`

同时避免这些路由在启动时继续引入缓存服务依赖。

### 5. 删除缓存 API 文件与对外配置入口

已删除：

- `backend/app/api/admin/cache.py`
- `backend/app/api/user/cache.py`

同时清理：

- `auth_service.py` 中用户信息返回的缓存字段
- `schemas/user.py` 中用户更新请求里的缓存配置字段

结果：

- 前后端接口层不再把缓存视为一个可配置功能
- 管理员和用户都不能再通过 API 操作缓存配置

## 保留但未处理的内容

本次没有处理以下历史遗留内容：

- 数据库中的缓存字段与 `cache_log` 表
- 用户资料接口中仍存在的缓存字段返回

其中“用户资料接口中的缓存字段返回”已在本次清理；仍保留的是数据库字段、日志表以及未接入运行时的缓存服务类文件。

## 测试验证

已完成：

1. 语法校验

```bash
python -m py_compile \
  backend/app/middleware/cache_middleware.py \
  backend/app/middleware/stream_cache_middleware.py \
  backend/app/services/proxy_service.py \
  backend/app/main.py
```

2. 定向检索验证

- 运行时代码中已无 `X-Cache-Status`
- `main.py` 已无缓存路由注册和相关 import

## 当前结果

系统运行时的缓存处理已被摘除，缓存不会再参与请求转发和流式响应链路。
