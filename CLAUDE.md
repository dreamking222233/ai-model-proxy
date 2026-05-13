# modelInvocationSystem — 项目总览

## 变更记录 (Changelog)

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-12 | v1.0 | 初始架构文档生成，覆盖 backend + frontend 两个模块 |

---

## 项目愿景

小乐AI（xiaoleai.team）是一个多租户 AI 模型中转平台，面向个人用户、代理商（白标站点）和平台管理员提供统一的 AI 模型调用服务。核心价值：

- 对用户：通过单一 API Key 访问 Claude、GPT、Gemini 等全系列模型，无需管理多个上游账号。
- 对代理商：支持白标部署，独立域名、独立用户体系、独立余额池，可自主发放兑换码和套餐。
- 对平台：统一渠道管理、健康监控、计费审计，支持多渠道故障转移与熔断。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 2)                          │
│  Admin Portal | User Portal | Agent Portal | AI Chat        │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE / WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                   后端 (FastAPI / Python)                    │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Auth API │  │ Admin API│  │ User API │  │ Agent API │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Proxy Service (核心转发引擎)             │   │
│  │  OpenAI / Anthropic / Responses / Image / WebSocket │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │           Channel Failover + Circuit Breaker         │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────┐  ┌────────▼──────┐  ┌────────────────────┐  │
│  │  MySQL   │  │  上游 LLM API  │  │  Redis (会话/缓存)  │  │
│  └──────────┘  └───────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**技术栈**

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI 0.x + Uvicorn |
| ORM | SQLAlchemy (同步, pymysql 驱动) |
| 数据库 | MySQL 8.x |
| 缓存/会话 | Redis |
| 任务调度 | APScheduler (AsyncIOScheduler) |
| HTTP 客户端 | httpx (异步) |
| 认证 | JWT (python-jose) + bcrypt |
| 前端框架 | Vue 2 + Vuex + Vue Router |
| UI 组件库 | Ant Design Vue |
| 构建工具 | Vue CLI (webpack) |

---

## 模块结构图

```mermaid
graph TD
    ROOT["(根) modelInvocationSystem"] --> BE["backend"]
    ROOT --> FE["frontend"]

    BE --> BE_APP["app (FastAPI 应用)"]
    BE_APP --> BE_API["api (路由层)"]
    BE_APP --> BE_SVC["services (业务层)"]
    BE_APP --> BE_MDL["models (ORM 模型)"]
    BE_APP --> BE_SCH["schemas (Pydantic)"]
    BE_APP --> BE_CORE["core (安全/依赖/异常)"]
    BE_APP --> BE_MW["middleware (缓存/流)"]
    BE_APP --> BE_TASK["tasks (定时任务)"]
    BE_APP --> BE_TEST["test (测试)"]

    BE_API --> BE_API_PROXY["proxy (OpenAI/Anthropic/Image)"]
    BE_API --> BE_API_ADMIN["admin (管理员接口)"]
    BE_API --> BE_API_USER["user (用户接口)"]
    BE_API --> BE_API_AGENT["agent (代理商接口)"]
    BE_API --> BE_API_PUB["public (公开接口)"]

    FE --> FE_SRC["src"]
    FE_SRC --> FE_VIEWS["views (页面)"]
    FE_SRC --> FE_COMP["components (组件)"]
    FE_SRC --> FE_API["api (请求封装)"]
    FE_SRC --> FE_STORE["store (Vuex)"]
    FE_SRC --> FE_ROUTER["router"]
    FE_SRC --> FE_UTILS["utils"]

    click BE_API_PROXY "./backend/CLAUDE.md" "查看 backend 文档"
    click BE_SVC "./backend/CLAUDE.md" "查看 backend 文档"
    click FE_VIEWS "./frontend/CLAUDE.md" "查看 frontend 文档"
```

---

## 模块索引

| 模块路径 | 语言 | 职责 | 文档 |
|----------|------|------|------|
| `backend/` | Python | FastAPI 后端：代理转发、计费、用户/代理/管理员 API | [CLAUDE.md](./backend/CLAUDE.md) |
| `frontend/` | JavaScript/Vue | Vue 2 前端：管理员/用户/代理商三套门户 + AI 对话 | [CLAUDE.md](./frontend/CLAUDE.md) |

---

## 运行与开发

### 后端启动

```bash
cd backend
# 安装依赖（建议 Python 3.11+）
pip install -r requirements.txt   # 或 pyproject.toml

# 配置环境变量（复制并修改）
cp .env.example .env

# 启动开发服务器（端口 8085）
python run.py
```

关键环境变量（`.env`）：

```
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/modelinvoke
REDIS_HOST=localhost
REDIS_PORT=6379
JWT_SECRET_KEY=<自定义密钥>
SERVER_PORT=8085
```

### 前端启动

```bash
cd frontend
npm install
npm run serve        # 开发模式，默认 8080
npm run build        # 生产构建
```

前端通过 `VUE_APP_BASE_API` 环境变量指定后端地址，默认 `http://localhost:8085`。

---

## 测试策略

- 测试文件位于 `backend/app/test/`，使用 Python 标准 `unittest` 或直接脚本运行。
- 测试分类：
  - `test_auth_service.py` — 认证逻辑
  - `test_channel_health_*.py` — 渠道健康监控
  - `test_proxy_*.py` — 代理转发与故障转移
  - `test_image_billing.py` — 图片计费
  - `test_subscription_compatibility.py` — 套餐兼容性
  - `cache/` — 缓存相关（单轮/多轮/生命周期/Anthropic）
  - `createImg/` — 图片生成集成测试脚本
- 无前端自动化测试配置（仅手动测试）。

---

## 编码规范

- 后端异常统一使用 `ServiceException(status_code, detail, error_code)`，由全局 handler 处理。
- Controller 层（API 路由）不做 try-catch，业务逻辑在 Service 层。
- 余额操作使用 `SELECT ... FOR UPDATE` 防止并发竞争。
- 所有 API 响应统一包装为 `ResponseModel(code, message, data)`。
- 前端 axios 拦截器统一处理 JWT 注入与错误响应。
- 文档放 `./md/`（计划/实现/评审），功能文档放 `./docs/`。

---

## AI 使用指引

- 代理转发核心逻辑在 `backend/app/services/proxy_service.py`（约 423KB，需分页读取）。
- 新增模型：在 `unified_model` 表添加记录，在 `model_channel_mapping` 绑定渠道。
- 新增渠道：在 `channel` 表添加，配置 `protocol_type`（openai/anthropic）和 `provider_variant`。
- 多租户隔离：通过 `AgentService.assert_user_matches_site()` 在每次请求时校验用户与站点归属。
- 计费流程：请求完成后由 `proxy_service` 根据 token 用量和模型定价扣减 `user_balance`，同时写 `consumption_record`。
