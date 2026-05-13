## 用户原始需求

深度分析当前项目数据库连接池耗尽问题，确认根因，并自行决定采用合适方案进行优化修复，重点解决：

- API 请求在服务运行一段时间后超时，响应时间从毫秒级升到 120 秒
- 日志出现 `QueuePool limit reached`
- 高并发和运行约 1 小时后问题明显加重
- 已临时增大连接池，但需要从根因上修复

## 技术方案设计

### 当前问题判断

基于代码扫描，当前仓库的核心问题不是单纯“连接池默认值偏小”，而是同步 SQLAlchemy `Session` 在以下异步长链路中被长时间持有：

1. `async` 代理接口通过 `Depends(get_db)` 注入同步 `Session`
2. 在完成鉴权、模型解析、缓存分析后，仍将同一个 `Session` 传入上游 HTTP / SSE / WebSocket 长耗时流程
3. 请求结束前 FastAPI 不会执行 `get_db()` 的 `finally: db.close()`
4. 同时，定时健康检查将同一个同步 `Session` 共享给 `asyncio.gather()` 的并发任务

这会造成：

- 连接在长时间 `await` 期间无法回到连接池
- 单个 `Session` 跨异步任务复用，放大事务与连接占用风险
- 流式请求、WebSocket、健康检查成为连接池消耗大户

### 本次修复策略

本次不直接迁移全量异步 ORM，先采用低风险、可快速落地的“短会话”方案：

1. 数据库层增加连接池配置项与池状态采集能力
2. 提供统一的短会话辅助方法
3. 在代理链路中将数据库访问拆成三段：
   - 前置短读事务：鉴权、配置、模型与 channel 解析
   - 上游调用阶段：不持有数据库连接
   - 后置短写事务：成功/失败日志、计费、channel 健康状态更新
4. 健康检查任务改为“预查询 + 单 channel 独立会话写回”
5. 尽量保持现有业务逻辑、接口契约和计费逻辑不变

### 涉及文件清单

- `backend/app/database.py`
- `backend/app/config.py`
- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `backend/app/tasks/__init__.py`
- `backend/app/tasks/health_check.py`
- `backend/app/api/admin/health.py`
- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/middleware/cache_middleware.py`
- `backend/app/middleware/stream_cache_middleware.py`
- `backend/app/main.py`
- 视实现情况补充测试文件

### 关键实现点

#### 1. 连接池配置显式化

- 为 `pool_size` / `max_overflow` / `pool_timeout` / `pool_recycle` / `pool_pre_ping` 增加配置
- 避免完全依赖 SQLAlchemy 默认值

#### 2. 主动释放长链路连接

- 在请求进入上游长耗时 `await` 前，主动结束当前 `Session` 的连接占用
- 避免同步 `Session` 在 SSE / WebSocket / 上游 HTTP 期间长期占坑

#### 3. 后置写操作切换到独立短事务

- `channel` 成功/失败状态更新
- 请求日志、消费记录、API Key 统计
- 失败日志记录
- 图片积分扣减

这些逻辑改为独立短会话完成，不依赖前置请求会话继续存活

#### 4. 定时任务隔离会话

- 健康检查不再共享一个 `Session` 跨多个并发任务
- 每个 channel 检查写回时单独开会话，降低连接泄漏和并发冲突风险

#### 5. 监控与排查能力

- 增加连接池状态快照日志/方法
- 在启动与关键链路中输出池状态，便于观察 `checked out / overflow / current size`

## 实施步骤概要

1. 新增数据库配置项和短会话工具
2. 给数据库层增加连接池状态采集方法
3. 调整缓存中间件，在进入上游长耗时前释放会话连接
4. 重构 `ProxyService` 的成功/失败/计费/日志写入为独立短事务
5. 修复 Responses SSE / OpenAI SSE / Anthropic SSE / WebSocket 长链路
6. 重构健康检查并发逻辑，移除共享 `Session`
7. 补充基础验证
8. 产出 impl 文档并执行自审
