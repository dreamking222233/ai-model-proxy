## 任务概述

本次针对数据库连接池耗尽问题完成了第一阶段根因修复，目标不是继续单纯扩容连接池，而是缩短同步 SQLAlchemy `Session` 的持有时间，避免在异步代理请求、SSE/WebSocket 和定时任务中跨 `await` 长时间占用连接。

## 文件变更清单

- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/main.py`
- `backend/app/api/admin/health.py`
- `backend/app/middleware/cache_middleware.py`
- `backend/app/middleware/stream_cache_middleware.py`
- `backend/app/services/health_service.py`
- `backend/app/services/proxy_service.py`
- `backend/app/tasks/__init__.py`
- `md/plan-db-session-lifecycle-20260424.md`

## 核心代码说明

### 1. 数据库层补充显式连接池配置

在 `config.py` / `database.py` 中新增并启用：

- `DB_POOL_SIZE=20`
- `DB_MAX_OVERFLOW=40`
- `DB_POOL_TIMEOUT=30`
- `DB_POOL_RECYCLE=3600`
- `DB_POOL_PRE_PING=True`

同时新增：

- `release_session_connection(db)`：主动释放请求会话当前连接
- `session_scope()`：用于后置短事务写入
- `get_pool_status_snapshot()`：输出连接池状态快照

### 2. 长链路前主动释放请求会话连接

在以下关键路径加入 `release_session_connection(db)`：

- 非流式缓存中间件
- 流式缓存中间件
- OpenAI / Responses / Anthropic / Image 上游请求入口
- Responses WebSocket 每轮转发前
- Anthropic prompt cache 变体构建后

效果是：

- 前置鉴权、配置读取、模型解析仍可复用请求会话
- 进入上游 HTTP / SSE / WebSocket 长等待前，连接主动回池

### 3. 后置成功/失败写入改为独立短事务

`proxy_service.py` 中以下逻辑已切换为 `session_scope()` 独立写入：

- `_record_channel_failure`
- `_record_success`
- `_deduct_balance_and_log`
- `_log_failed_request`
- `_deduct_image_credits_and_log`

这样即使原始请求会话已经提前释放，后置记账、请求日志、消费记录、API Key 统计、channel 健康状态写回仍能正常执行，而且每次写完立即归还连接。

### 4. 健康检查任务不再共享同一个 Session 跨并发任务

`health_service.py` 中：

- `check_all_channels()` 只负责预查询 channel 和健康检查模型
- 进入 `asyncio.gather()` 前主动释放原会话连接
- 单个 channel 的检查结果写回改为 `_check_and_record()` 内部单独开短会话

这样避免了：

- 同一 `Session` 被多个异步任务共享
- 网络健康检查期间长期占用同一数据库连接

### 5. 监控能力补充

新增：

- 启动/关闭时记录连接池状态
- 定时健康检查开始/结束记录连接池状态
- 管理接口 `GET /api/admin/health/db-pool`

便于后续观察：

- 当前池大小
- checked in / checked out / overflow
- 配置值和池状态字符串

## 测试验证

已执行：

```bash
python -m py_compile backend/app/config.py backend/app/database.py backend/app/main.py backend/app/api/admin/health.py backend/app/tasks/__init__.py backend/app/services/health_service.py backend/app/services/proxy_service.py backend/app/middleware/cache_middleware.py backend/app/middleware/stream_cache_middleware.py
```

结果：

- 通过，无语法错误

## 待观察项

- 目前仍使用同步 SQLAlchemy，会话生命周期问题已显著收敛，但未完成全量异步 ORM 迁移
- `require_admin/get_current_user` 这类鉴权依赖仍使用请求级 `Session`，不过不再处于主要耗尽链路
- 后续建议结合压测重点观察流式请求和 WebSocket 场景下的 `checkedout` 峰值是否明显下降
