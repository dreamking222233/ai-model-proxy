# 大模型调用中转平台 - 实施文档

**日期**: 2026-03-14
**状态**: 已完成

## 一、项目概览

搭建完成了一个大模型调用中转平台，支持 OpenAI 和 Anthropic 双协议，具备优先级故障转移、统一模型映射、健康监测、计费等核心能力。

### 技术栈
- **后端**: FastAPI (Python 3.9, conda: ai-invoke-service) 端口 8085
- **前端**: Vue 2.7 + Ant Design Vue 1.7 + Vuex + Vue Router
- **数据库**: MySQL `modelinvoke`

---

## 二、数据库 (12 张表)

| 表名 | 用途 |
|------|------|
| sys_user | 系统用户 |
| user_api_key | 用户 API Key (SHA256 哈希存储) |
| channel | 渠道(模型提供商) |
| unified_model | 统一模型定义 + 定价 |
| model_channel_mapping | 模型-渠道映射 |
| model_override_rule | 模型覆盖规则 |
| health_check_log | 健康检查记录 |
| request_log | 请求日志 |
| system_config | 系统配置 |
| operation_log | 操作日志 |
| user_balance | 用户余额 |
| consumption_record | 消费记录 |

初始化脚本: `backend/sql/init.sql`
默认管理员: admin / admin123

---

## 三、后端 API

### 认证
- `POST /api/auth/register` - 注册
- `POST /api/auth/login` - 登录 (返回 JWT)

### 管理员接口 (需 admin 角色)
- `/api/admin/channels` - 渠道 CRUD
- `/api/admin/models` - 统一模型 + 映射 + 覆盖规则
- `/api/admin/users` - 用户管理 + 充值
- `/api/admin/logs` - 请求日志 / 消费记录
- `/api/admin/health` - 健康监控 / 手动检查
- `/api/admin/system` - 系统配置 / 仪表盘

### 用户接口
- `/api/user/api-keys` - API Key 管理
- `/api/user/balance` - 余额 / 消费记录
- `/api/user/profile` - 个人信息 / 修改密码

### 代理转发 (API Key 认证)
- `POST /v1/chat/completions` - OpenAI 协议
- `POST /v1/messages` - Anthropic 协议
- `GET /v1/models` - 模型列表

认证方式: `Authorization: Bearer sk-xxx` 或 `X-API-Key: sk-xxx`

---

## 四、核心转发流程

```
请求 → API Key 验证 → 余额检查
  → 模型覆盖规则匹配 → 统一模型解析
  → 获取可用渠道(按优先级排序,过滤健康+未熔断)
  → 尝试转发(失败则切换下一渠道)
  → 成功: 提取 Token 用量 → 计算费用 → 扣减余额 → 记录日志
  → 全部失败: 返回 503
```

### 流式支持
- OpenAI: SSE `data: {...}` 逐块转发, `stream_options.include_usage` 获取 token
- Anthropic: SSE `event: xxx\ndata: {...}` 转发, 从 `message_start/message_delta` 提取 token

### 健康保障
- 定时健康检查 (默认 300 秒)
- 启动预检
- 熔断器模式 (连续失败 >= 阈值 → 熔断, 定时探测恢复)
- 健康分数 (0-100)
- 请求级实时故障转移

---

## 五、前端页面

### 管理后台
- Dashboard: 统计概览
- ChannelManage: 渠道 CRUD + 健康状态
- ModelManage: 统一模型 + 映射 + 覆盖规则 (三 Tab)
- UserManage: 用户列表 + 充值
- HealthMonitor: 健康监控面板 + 日志
- RequestLog: 请求日志 (多条件筛选)
- SystemConfig: 系统配置编辑

### 用户端
- Dashboard: 余额 + 用量概览
- ApiKeyManage: Key 管理 (创建后仅展示一次)
- BalanceLog: 余额 + 消费记录
- UsageLog: 使用记录

---

## 六、启动方式

### 后端
```bash
cd backend
conda activate ai-invoke-service
python run.py
# 运行在 http://localhost:8085
```

### 前端
```bash
cd frontend
npm run serve
# 运行在 http://localhost:8080
```

### 数据库初始化
```bash
mysql -u root -ps1771746291 modelinvoke < backend/sql/init.sql
```

---

## 七、文件清单

### 后端核心文件
| 文件 | 用途 |
|------|------|
| `app/main.py` | FastAPI 入口 + lifespan |
| `app/config.py` | 配置 |
| `app/database.py` | SQLAlchemy 连接 |
| `app/services/proxy_service.py` | 核心转发逻辑 (807 行) |
| `app/services/health_service.py` | 健康检查 |
| `app/services/model_service.py` | 模型解析 + 可用渠道 |
| `app/tasks/__init__.py` | APScheduler 定时任务 |
| `app/core/dependencies.py` | JWT + API Key 认证 |
| `app/core/security.py` | 密码哈希 + Key 生成 |

### 前端核心文件
| 文件 | 用途 |
|------|------|
| `src/router/index.js` | 路由 + 导航守卫 |
| `src/store/index.js` | Vuex 状态管理 |
| `src/api/request.js` | Axios 拦截器 |
| `src/layout/AdminLayout.vue` | 管理后台布局 |
| `src/layout/UserLayout.vue` | 用户端布局 |

---

## 八、已修复的问题

| 问题 | 原因 | 修复 |
|------|------|------|
| Python 3.9 类型注解不兼容 | `str \| None` 语法需要 3.10+ | 所有文件添加 `from __future__ import annotations` |
| Pydantic `max_digits` 约束报错 | pydantic v2 不支持 Field 中的 `max_digits` | 移除约束 |
| Pydantic `model_` 命名空间警告 | `model_name` 等字段冲突 | 添加 `ConfigDict(protected_namespaces=())` |
| Less 4.x 与 Ant Design Vue 1.x 不兼容 | Less 4.x 语法变更 | 降级到 less@3.13.1 + less-loader@7.3.0 |
| 健康检查日志状态值不匹配 | 代码用 "failure" 但 DB 枚举是 "fail" | 修正为 "fail" |
| 请求日志状态值不匹配 | 代码用 "failed" 但 DB 枚举是 "error" | 修正为 "error" |
| JWT 密钥每次重启随机生成 | `secrets.token_urlsafe()` 在启动时执行 | 改为静态默认密钥 |
| 登录接口返回 500 | `auth.py` 调用 `login(ip=...)` 参数名错误 | 修正为 `client_ip=...` |
| 管理员密码验证失败 | init.sql 中预置的 bcrypt hash 不匹配 "admin123" | 用运行时生成的正确 hash 替换 |
| 渠道/模型创建返回 500 | 服务层返回 ORM 对象无法被 Pydantic 序列化 | 服务层统一返回 dict |
| 上游总是返回 SSE 流式响应 | api.kxaug.xyz 即使 stream=false 也返回 SSE | 新增 `_parse_sse_to_non_stream_openai/anthropic` 解析器 |
| Anthropic 流式 input_tokens 不准 | 部分代理在 message_delta 中才返回真实 input_tokens | message_delta 中也更新 input_tokens |

---

## 九、API 测试验证结果 (20/20 通过)

```
[PASS] GET /health
[PASS] POST /api/auth/login (admin)
[PASS] POST /api/auth/register
[PASS] POST /api/auth/login (user)
[PASS] GET /api/admin/system/dashboard
[PASS] GET /api/admin/system/configs
[PASS] GET /api/admin/channels
[PASS] POST /api/admin/channels
[PASS] GET /api/admin/models
[PASS] POST /api/admin/models
[PASS] POST /api/admin/models/mappings
[PASS] GET /api/admin/users
[PASS] GET /api/admin/health/status
[PASS] GET /api/admin/health/logs
[PASS] GET /api/admin/logs/requests
[PASS] GET /api/user/profile
[PASS] GET /api/user/balance
[PASS] GET /api/user/api-keys
[PASS] POST /api/user/api-keys
[PASS] GET /v1/models (API Key auth)
```

---

## 十、渠道接入配置

### 渠道清单 (5 个渠道)

| 渠道 | base_url | 优先级 | 模型类型 | 状态 |
|------|----------|--------|----------|------|
| api.kxaug.xyz-Claude | https://api.kxaug.xyz/v1 | 1 (主力) | Claude | 正常 |
| api.kxaug.xyz-GPT | https://api.kxaug.xyz/v1 | 1 (主力) | GPT/Codex | 上游异常 |
| pay.kxaug.xyz-Claude | https://pay.kxaug.xyz/v1 | 2 (备用) | Claude | 上游异常 |
| pay.kxaug.xyz-GPT | https://pay.kxaug.xyz/v1 | 2 (备用) | GPT/Codex | 上游异常 |
| mmaqq.top | https://mmaqq.top/v1 | 3 (保底) | 全模型 | 正常 |

### 统一模型 (11 个)

| 模型名 | 输入价格($/M) | 输出价格($/M) | 可用渠道 |
|--------|-------------|-------------|---------|
| claude-haiku-4-5-20251001 | 1.00 | 5.00 | Ch1→Ch3→Ch5 |
| claude-sonnet-4-5-20250929 | 3.00 | 15.00 | Ch1→Ch3 |
| claude-haiku-4-5 | 1.00 | 5.00 | Ch5 |
| claude-sonnet-4-6 | 3.00 | 15.00 | Ch5 |
| gpt-5.1 | 2.00 | 8.00 | Ch2 |
| gpt-5.2 | 3.00 | 12.00 | Ch2→Ch4 |
| gpt-5.1-codex | 3.00 | 12.00 | Ch2 |
| gpt-5.2-codex | 5.00 | 20.00 | Ch2→Ch4 |
| gpt-5.3-codex | 5.00 | 20.00 | Ch4 |
| gpt-5.4 | 5.00 | 20.00 | Ch4 |
| gemini-2.5-flash | 0.15 | 0.60 | Ch5 |

### Token 提取方式

| 协议 | 非流式 | 流式 |
|------|--------|------|
| OpenAI | `usage.prompt_tokens` / `completion_tokens` | 最后一个 chunk 的 `usage` 字段 |
| Anthropic | `usage.input_tokens` / `output_tokens` | `message_start` + `message_delta` 中提取 |

### 已知上游问题

1. **api.kxaug.xyz**: 无论 `stream:true/false` 总是返回 SSE 流式响应 → 已通过 SSE 解析器处理
2. **api.kxaug.xyz GPT/Codex**: 所有 GPT/Codex 模型返回 "upstream error: do request failed"
3. **pay.kxaug.xyz**: 所有模型返回 "没有可用的 adal 账户" (服务端配置问题)
4. **mmaqq.top Gemini streaming**: httpx 库获取的 SSE 响应缺少内容块，非流式模式工作正常

### 代理转发验证 (9/9 成功)

```
[PASS] claude-haiku-4-5-20251001 via OpenAI (stream:false) → api.kxaug.xyz
[PASS] claude-haiku-4-5-20251001 via OpenAI (stream:true)  → api.kxaug.xyz
[PASS] claude-haiku-4-5-20251001 via Anthropic (stream:false) → api.kxaug.xyz
[PASS] claude-haiku-4-5-20251001 via Anthropic (stream:true)  → api.kxaug.xyz
[PASS] gemini-2.5-flash via OpenAI (stream:false) → mmaqq.top
[PASS] claude-sonnet-4-6 via Anthropic (stream:false) → mmaqq.top
[PASS] Token 计数正确 (OpenAI: prompt_tokens/completion_tokens)
[PASS] Token 计数正确 (Anthropic: input_tokens/output_tokens)
[PASS] 余额扣减正确 ($100 → $99.99, consumed $0.0097)
```
