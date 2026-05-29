[根目录](../CLAUDE.md) > **backend**

# backend — 模块文档

## 模块职责

FastAPI 后端，承担以下核心职责：

1. **代理转发引擎**：将用户的 OpenAI / Anthropic / Responses / Image 格式请求转发至上游 LLM 渠道，支持 SSE 流式、非流式、WebSocket 三种传输模式。
2. **多渠道管理与故障转移**：维护渠道优先级、健康分、熔断器，自动在渠道间切换。
3. **多租户（代理商）体系**：通过请求 Host 解析站点归属，隔离平台直营用户与代理商用户。
4. **计费与余额**：按 token 用量或图片积分扣费，支持按量计费与套餐两种模式。
5. **用户/代理商/管理员 API**：提供完整的管理后台、用户自助、代理商运营接口。
6. **定时任务**：渠道健康检查、套餐过期维护。

---

## 入口与启动

```
backend/
├── run.py                  # 启动入口：uvicorn app.main:app
└── app/
    ├── main.py             # FastAPI 应用实例、路由注册、lifespan
    ├── config.py           # pydantic-settings 配置（读取 .env）
    └── database.py         # SQLAlchemy engine、SessionLocal、session_scope
```

启动命令：

```bash
python run.py
# 等价于：uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload
```

`lifespan` 钩子在启动时：
1. 从 `system_config` 表读取 `health_check_interval`。
2. 启动 APScheduler（健康检查 + 套餐维护两个定时任务）。
3. 执行一次启动健康检查（非阻塞，失败不影响启动）。

---

## 对外接口

### 认证接口 `/api/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册（自动绑定代理商站点） |
| POST | `/api/auth/login` | 用户名密码登录，返回 JWT |
| POST | `/api/auth/forgot-password` | 通过用户名+邮箱重置密码 |
| POST | `/api/auth/forgot-password/verify` | 验证身份（不重置） |

### 公开接口 `/api/public`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/public/site/config` | 返回当前站点配置（名称/公告/是否允许注册） |

### 代理接口（需 API Key）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat/completions` | OpenAI Chat Completions（标准） |
| POST | `/chat/completions` | OpenAI Chat Completions（无前缀） |
| GET | `/v1/models` | 模型列表 |
| GET | `/models` | 模型列表（无前缀） |
| POST | `/v1/messages` | Anthropic Messages API |
| POST | `/messages` | Anthropic Messages API（无前缀） |
| POST | `/v1/messages/count_tokens` | Anthropic token 计数 |
| POST | `/v1/responses` | OpenAI Responses API（Codex CLI） |
| POST | `/responses` | Responses API（无前缀） |
| WS | `/v1/responses` | Responses API WebSocket |
| WS | `/responses` | Responses API WebSocket（无前缀） |
| POST | `/v1/images/generations` | 图片生成 |
| POST | `/v1/images/edits` | 图片编辑 |

### 管理员接口 `/api/admin`（需 JWT + admin 角色）

| 前缀 | 说明 |
|------|------|
| `/api/admin/channels` | 渠道 CRUD |
| `/api/admin/models` | 模型 CRUD、覆盖规则 |
| `/api/admin/users` | 用户管理、余额充值/扣减 |
| `/api/admin/agents` | 代理商管理、资产管理、结算 |
| `/api/admin/logs` | 请求日志、操作日志、消费记录 |
| `/api/admin/health` | 渠道健康状态、手动触发检查 |
| `/api/admin/system` | 系统配置 KV、仪表盘统计 |
| `/api/admin/redemption` | 兑换码创建/批量/删除 |
| `/api/admin/subscription` | 套餐模板管理、为用户开通套餐 |

### 用户接口 `/api/user`（需 JWT）

| 前缀 | 说明 |
|------|------|
| `/api/user/api-keys` | API Key 管理 |
| `/api/user/balance` | 余额查询、消费记录 |
| `/api/user/profile` | 个人信息、修改密码 |
| `/api/user/models` | 可用模型列表 |
| `/api/user/stats` | 用量统计、排行 |
| `/api/user/redemption` | 兑换码充值 |

### 代理商接口 `/api/agent`（需 JWT + agent 角色）

| 前缀 | 说明 |
|------|------|
| `/api/agent/users` | 管理旗下用户 |
| `/api/agent/logs` | 查看旗下请求记录 |
| `/api/agent/stats` | 用量统计 |
| `/api/agent/system` | 站点配置 |
| `/api/agent/subscription` | 套餐发放 |
| `/api/agent/redemption` | 兑换码管理 |

---

## 关键依赖与配置

### Python 依赖（主要）

| 包 | 用途 |
|----|------|
| `fastapi` | Web 框架 |
| `uvicorn` | ASGI 服务器 |
| `sqlalchemy` | ORM（同步） |
| `pymysql` | MySQL 驱动 |
| `pydantic-settings` | 配置管理 |
| `python-jose[cryptography]` | JWT |
| `passlib[bcrypt]` | 密码哈希 |
| `httpx` | 异步 HTTP 客户端（上游请求） |
| `apscheduler` | 定时任务 |
| `redis` | Redis 客户端 |

### 配置项（`app/config.py`）

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `mysql+pymysql://...` | MySQL 连接串 |
| `DB_POOL_SIZE` | 20 | 连接池大小 |
| `DB_MAX_OVERFLOW` | 40 | 最大溢出连接 |
| `JWT_SECRET_KEY` | 内置默认（生产必须修改） | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | 1440（24h） | Token 有效期 |
| `SERVER_PORT` | 8085 | 监听端口 |
| `STREAM_HEARTBEAT_INTERVAL_SECONDS` | 20 | SSE 心跳间隔 |
| `CORS_ORIGINS` | localhost + xiaoleai.team | CORS 白名单 |
| `PLATFORM_SITE_NAME` | 小乐AI | 平台名称 |

Redis 配置通过环境变量读取（不在 `config.py` 中）：

| 环境变量 | 默认值 |
|----------|--------|
| `REDIS_HOST` | localhost |
| `REDIS_PORT` | 6379 |
| `REDIS_PASSWORD` | 空 |
| `REDIS_DB` | 0 |
| `CACHE_ENABLED` | true |

---

## 数据模型

### 核心表一览

| 表名 | ORM 类 | 说明 |
|------|--------|------|
| `sys_user` | `SysUser` | 系统用户（含角色、代理归属、订阅状态） |
| `user_api_key` | `UserApiKey` | 用户 API Key（SHA256 哈希存储） |
| `channel` | `Channel` | 上游渠道（URL、API Key、健康状态、熔断器） |
| `unified_model` | `UnifiedModel` | 统一模型定义（名称、协议、定价） |
| `model_channel_mapping` | `ModelChannelMapping` | 模型与渠道的映射关系 |
| `model_override_rule` | `ModelOverrideRule` | 模型别名/重定向规则 |
| `model_image_resolution_rule` | `ModelImageResolutionRule` | 图片模型分辨率计费规则 |
| `agent` | `Agent` | 代理商租户（域名、站点配置） |
| `agent_balance` | `AgentBalance` | 代理商 USD 余额池 |
| `agent_image_balance` | `AgentImageBalance` | 代理商图片积分池 |
| `agent_subscription_inventory` | `AgentSubscriptionInventory` | 代理商套餐库存 |
| `agent_daily_limit` | `AgentDailyLimit` | 代理商每日限额 |
| `agent_settlement_record` | `AgentSettlementRecord` | 代理商结算记录 |
| `user_balance` | `UserBalance` | 用户 USD 余额 |
| `user_image_balance` | `UserImageBalance` | 用户图片积分余额 |
| `consumption_record` | `ConsumptionRecord` | 每次请求消费记录（含计费快照） |
| `image_credit_record` | `ImageCreditRecord` | 图片积分流水 |
| `request_log` | `RequestLog` | 请求日志（含 token、缓存、会话、压缩等字段） |
| `health_check_log` | `HealthCheckLog` | 渠道健康检查日志 |
| `operation_log` | `OperationLog` | 操作审计日志 |
| `system_config` | `SystemConfig` | 系统配置 KV 表 |
| `redemption_code` | `RedemptionCode` | 兑换码 |
| `subscription_plan` | `SubscriptionPlan` | 套餐模板 |
| `user_subscription` | `UserSubscription` | 用户套餐记录 |
| `subscription_usage_cycle` | `SubscriptionUsageCycle` | 套餐每日用量周期 |
| `conversation_session` | `ConversationSession` | 会话状态（含压缩模式、上游会话 ID） |
| `conversation_checkpoint` | `ConversationCheckpoint` | 会话历史压缩检查点 |
| `request_cache_summary` | `RequestCacheSummary` | 请求体缓存分析摘要 |

### 关键字段说明

**`sys_user`**
- `role`: `admin` / `agent` / `user`
- `agent_id`: NULL 表示平台直营用户
- `subscription_type`: `balance`（按量）/ `unlimited`（无限套餐）/ `quota`（限额套餐）

**`channel`**
- `protocol_type`: `openai` / `anthropic`
- `provider_variant`: `default` / `google-official` / `google-vertex-image`
- `auth_header_type`: `x-api-key` / `anthropic-api-key` / `x-goog-api-key` / `authorization`
- `health_score`: 0-100，低于阈值触发熔断
- `circuit_breaker_until`: 熔断恢复时间

**`request_log`**
- `billing_type`: `token` / `subscription` / `image_credit` / `free`
- `cache_status`: 请求体缓存状态
- `upstream_prompt_cache_status`: Anthropic Prompt Cache 状态
- `compression_mode`: 会话历史压缩模式

---

## 服务层架构

```
services/
├── proxy_service.py              # 核心转发引擎（最大文件，约 423KB）
├── auth_service.py               # 注册/登录/用户管理
├── balance_service.py            # 余额查询/充值/扣减
├── channel_service.py            # 渠道 CRUD
├── model_service.py              # 模型 CRUD、覆盖规则
├── health_service.py             # 渠道健康检查
├── log_service.py                # 日志查询与统计
├── agent_service.py              # 代理商租户解析与管理
├── agent_asset_service.py        # 代理商资产（余额/图片积分）
├── agent_settlement_service.py   # 代理商结算
├── subscription_service.py       # 套餐管理与配额检查
├── redemption_service.py         # 兑换码
├── image_credit_service.py       # 图片积分计费
├── google_vertex_image_service.py # Google Vertex 图片生成
├── api_key_service.py            # API Key 管理
├── cache_service.py              # Redis 缓存读写
├── cache_stats_service.py        # 缓存统计
├── cache_key_generator.py        # 缓存键生成（消息标准化+哈希）
├── conversation_session_service.py # 会话状态持久化（MySQL + Redis）
├── conversation_match_service.py   # 会话匹配
├── conversation_shadow_service.py  # 会话影子状态
├── history_compaction_service.py   # 历史压缩
├── compression_guard_service.py    # 压缩保护
├── upstream_session_strategy_service.py # 上游会话策略
├── anthropic_prompt_cache_service.py    # Anthropic Prompt Cache 处理
├── request_body_cache_analyzer.py       # 请求体缓存分析
├── request_body_cache_service.py        # 请求体缓存服务
└── request_cache_summary_service.py     # 缓存摘要写入
```

### 代理转发核心流程（`proxy_service.py`）

```
请求进入
  │
  ├─ 1. 验证 API Key（verify_api_key）
  ├─ 2. 刷新订阅状态（SubscriptionService.refresh_user_subscription_state）
  ├─ 3. 余额/配额预检（_assert_text_request_allowed）
  ├─ 4. 模型解析（ModelService：别名重写 → 统一模型 → 渠道映射）
  ├─ 5. 注入模型身份 system prompt（_inject_model_identity）
  ├─ 6. 选择渠道（ChannelService：优先级 + 健康分 + 熔断过滤）
  ├─ 7. 会话匹配（ConversationMatchService，可选）
  ├─ 8. 发起上游请求（httpx，超时 120s，图片 300s）
  │     ├─ 流式：SSE 逐块转发 + 心跳
  │     └─ 非流式：等待完整响应
  ├─ 9. 提取 token 用量
  ├─ 10. 计费扣款（余额 / 套餐配额）
  ├─ 11. 写 request_log + consumption_record
  └─ 12. 更新渠道健康分
```

**故障转移**：上游返回 `{408,409,425,429,500,502,503,504}` 时，标记渠道失败并重试下一个渠道，最多 3 次。

---

## 安全机制

- **JWT**：HS256，24h 有效期，`sub` 字段存 user_id。
- **API Key**：`sk-` 前缀 + 48 位随机 hex，SHA256 哈希存储，明文仅在创建时返回一次。
- **密码**：bcrypt 哈希。
- **多租户隔离**：每次请求通过 `AgentService.assert_user_matches_site()` 校验用户与站点归属，防止跨租户访问。
- **余额并发**：`SELECT ... FOR UPDATE` 防止超扣。
- **CORS**：白名单 + 正则（支持 `*.xiaoleai.team` 和本地开发域名）。

---

## 测试与质量

当前仓库不再保留 `app/test/` 测试目录。

后端变更默认使用以下方式做基础验证：

```bash
python -m py_compile <changed-python-files>
```

涉及真实模型、支付、渠道或线上数据的问题，结合对应本地/线上环境做针对性手动验证。

---

## 常见问题 (FAQ)

**Q: 如何新增一个上游渠道？**
在 `channel` 表插入记录，设置 `base_url`、`api_key`（加密存储）、`protocol_type`（openai/anthropic）、`provider_variant`，然后在 `model_channel_mapping` 绑定模型。

**Q: 如何新增一个统一模型？**
在 `unified_model` 表插入记录，设置 `model_name`（用户请求时使用的名称）、`protocol_type`、`input_price_per_million`、`output_price_per_million`，再在 `model_channel_mapping` 绑定渠道和实际模型名。

**Q: 代理商如何隔离用户？**
`sys_user.agent_id` 关联 `agent.id`，每次登录/API 请求都会通过 `AgentService.assert_user_matches_site()` 校验请求 Host 与用户归属是否匹配。

**Q: 套餐与按量计费如何切换？**
`sys_user.subscription_type` 字段控制。`SubscriptionService.refresh_user_subscription_state()` 在每次 API 请求时自动检查套餐是否过期并更新该字段。

**Q: proxy_service.py 太大怎么读？**
使用 `offset` + `limit` 分页读取，或用 Grep 搜索特定方法名。核心方法：`handle_openai_request`、`handle_anthropic_request`、`handle_image_request`、`handle_responses_request`。

---

## 相关文件清单

```
backend/
├── run.py
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── public/site.py
│   │   ├── proxy/openai_proxy.py
│   │   ├── proxy/anthropic_proxy.py
│   │   ├── proxy/image_proxy.py
│   │   ├── admin/{channel,model,user,agent,log,health,system,redemption,subscription}.py
│   │   ├── user/{api_key,balance,profile,models,stats,redemption}.py
│   │   └── agent/{user,log,stats,system,subscription,redemption}.py
│   ├── services/
│   │   ├── proxy_service.py          # 核心（最大）
│   │   ├── auth_service.py
│   │   ├── agent_service.py
│   │   ├── subscription_service.py
│   │   └── ...（共 29 个服务文件）
│   ├── models/
│   │   ├── __init__.py               # 导出所有 ORM 类
│   │   ├── user.py
│   │   ├── channel.py
│   │   ├── model.py
│   │   ├── agent.py
│   │   ├── log.py
│   │   ├── redemption.py
│   │   └── cache_log.py
│   ├── core/
│   │   ├── security.py               # JWT + bcrypt + API Key 生成
│   │   ├── dependencies.py           # FastAPI 依赖注入（认证/授权）
│   │   ├── exceptions.py             # ServiceException + 全局 handler
│   │   ├── middleware.py             # RequestLoggingMiddleware
│   │   └── redis_client.py           # Redis 连接池封装
│   ├── middleware/
│   │   ├── cache_middleware.py       # 非流式透传包装器
│   │   └── stream_cache_middleware.py
│   └── tasks/
│       ├── __init__.py               # APScheduler 启动
│       └── health_check.py           # 健康检查任务
```

---

## 变更记录 (Changelog)

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-12 | v1.0 | 初始模块文档生成 |
