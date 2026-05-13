[根目录](../CLAUDE.md) > **frontend**

# frontend — 模块文档

## 模块职责

Vue 2 前端，提供三套独立门户：

1. **管理员门户** (`/admin`)：渠道/模型/用户/代理商管理、健康监控、日志查询、系统配置、套餐与兑换码管理。
2. **用户门户** (`/user`)：API Key 管理、余额与消费记录、模型列表、用量统计、兑换码充值、AI 对话。
3. **代理商门户** (`/agent`)：旗下用户管理、请求记录、套餐发放、兑换码管理、站点配置。
4. **AI 对话** (`/user/chat`, `/admin/chat`)：内嵌 AI 聊天界面，支持 SSE 流式输出、多会话、模型切换。

---

## 入口与启动

```
frontend/
├── babel.config.js
├── package.json
└── src/
    ├── main.js          # Vue 实例入口，注册 Ant Design Vue
    ├── App.vue          # 根组件
    ├── router/index.js  # Vue Router（history 模式）
    └── store/index.js   # Vuex Store（token/user 状态）
```

启动命令：

```bash
npm install
npm run serve    # 开发服务器，默认 http://localhost:8080
npm run build    # 生产构建，输出到 dist/
```

环境变量（`.env.local`）：

```
VUE_APP_BASE_API=http://localhost:8085
```

---

## 路由结构

路由使用 history 模式，导航守卫在 `router/index.js` 中实现角色鉴权。

| 路径前缀 | 布局组件 | 角色要求 | 说明 |
|----------|----------|----------|------|
| `/login` | 无 | 游客 | 登录/注册页 |
| `/register` | 无 | 游客 | 注册页（复用 Login.vue） |
| `/agents/login` | 无 | 游客 | 代理商登录入口 |
| `/admin/*` | `AdminLayout.vue` | admin | 管理员门户 |
| `/user/*` | `UserLayout.vue` | 已登录 | 用户门户 |
| `/agent/*` | `AgentLayout.vue` | agent | 代理商门户 |
| `/user/m-chat` | 无 | 已登录 | 手机版 AI 对话 |

**导航守卫逻辑**：
- 未登录访问需认证路由 → 重定向到 `/login`（代理商路由重定向到 `/agents/login`）。
- 已登录访问游客路由 → 按角色重定向（admin→`/admin/dashboard`，agent→`/agent/workbench`，user→`/user/dashboard`）。
- 角色不匹配 → 重定向到 `/user/dashboard`。

---

## 页面清单

### 管理员页面 (`views/admin/`)

| 文件 | 路由 | 说明 |
|------|------|------|
| `Dashboard.vue` | `/admin/dashboard` | 仪表盘（今日请求/token/错误/模型占比） |
| `ChannelManage.vue` | `/admin/channels` | 渠道 CRUD、健康状态 |
| `ModelManage.vue` | `/admin/models` | 模型 CRUD、覆盖规则 |
| `UserManage.vue` | `/admin/users` | 用户管理、余额充值/扣减 |
| `AgentManage.vue` | `/admin/agents` | 代理商管理 |
| `AgentAssetManage.vue` | `/admin/agent-assets` | 代理商资产（余额/图片积分） |
| `AgentSettlementManage.vue` | `/admin/agent-settlements` | 代理商结算 |
| `RequestLog.vue` | `/admin/logs` | 请求日志查询 |
| `AgentRequestLog.vue` | `/admin/agent-logs` | 代理商请求日志 |
| `HealthMonitor.vue` | `/admin/health` | 渠道健康监控 |
| `SystemConfig.vue` | `/admin/config` | 系统配置 KV |
| `RedemptionManage.vue` | `/admin/redemption` | 兑换码管理 |
| `SubscriptionManage.vue` | `/admin/subscription` | 套餐管理 |
| `CacheManage.vue` | `/admin/cache` | 缓存管理 |

### 用户页面 (`views/user/`)

| 文件 | 路由 | 说明 |
|------|------|------|
| `Dashboard.vue` | `/user/dashboard` | 用户仪表盘 |
| `ApiKeyManage.vue` | `/user/api-keys` | API Key 管理 |
| `BalanceLog.vue` | `/user/balance` | 余额与消费记录 |
| `ModelList.vue` | `/user/models` | 可用模型列表 |
| `UsageStats.vue` | `/user/stats` | 用量统计 |
| `UsageRanking.vue` | `/user/ranking` | 使用排行 |
| `UsageLog.vue` | `/user/usage` | 使用日志 |
| `QuickStart.vue` | `/user/quickstart` | 快速开始指引 |
| `Redemption.vue` | `/user/redemption` | 兑换码充值 |
| `Profile.vue` | `/user/profile` | 个人信息 |
| `CacheStats.vue` | `/user/cache-stats` | 缓存统计 |

### 代理商页面 (`views/agent/`)

| 文件 | 路由 | 说明 |
|------|------|------|
| `Workbench.vue` | `/agent/workbench` | 工作台 |
| `Dashboard.vue` | `/agent/dashboard` | 仪表盘 |
| `UserManage.vue` | `/agent/users` | 旗下用户管理 |
| `RedemptionManage.vue` | `/agent/redemption` | 兑换码管理 |
| `SubscriptionManage.vue` | `/agent/subscription` | 套餐发放 |
| `RequestLog.vue` | `/agent/logs` | 请求记录 |
| `UsageRanking.vue` | `/agent/ranking` | 使用排行 |
| `SystemManage.vue` | `/agent/system` | 站点配置 |

### 公共页面

| 文件 | 路由 | 说明 |
|------|------|------|
| `views/Login.vue` | `/login`, `/register` | 登录/注册 |
| `views/Register.vue` | `/register` | 注册（独立） |
| `views/common/AiChat.vue` | `/user/chat`, `/admin/chat` | AI 对话（桌面版） |
| `views/common/MobileChat.vue` | `/user/m-chat` | AI 对话（手机版） |

---

## 组件清单

```
components/
└── chat/
    ├── ChatMessage.vue    # 单条消息渲染（支持 Markdown/代码高亮）
    ├── ModelSelector.vue  # 模型选择器
    └── SessionList.vue    # 会话列表
```

---

## API 请求封装

```
api/
├── auth.js          # 登录/注册
├── user.js          # 用户信息/余额
├── channel.js       # 渠道管理
├── model.js         # 模型管理
├── agent.js         # 代理商管理
├── chat.js          # AI 对话（SSE）
├── redemption.js    # 兑换码
├── subscription.js  # 套餐
├── system.js        # 系统配置
├── public.js        # 公开接口（站点配置）
└── request.js       # axios 实例（备用）
```

`utils/request.js` 是主 axios 实例：
- `baseURL`：`VUE_APP_BASE_API`（默认 `http://localhost:8085`）
- 请求拦截：自动注入 `Authorization: Bearer <token>`
- 响应拦截：统一处理错误，`code !== 200` 时 reject

`utils/sse.js` 封装 SSE 流式请求（用于 AI 对话）。

---

## 状态管理（Vuex）

`store/index.js` 管理全局认证状态：

| State | 说明 |
|-------|------|
| `token` | JWT Token（持久化到 localStorage） |
| `user` | 当前用户信息（id/username/email/role/avatar） |

| Getter | 说明 |
|--------|------|
| `isLoggedIn` | 是否已登录 |
| `isAdmin` | 是否管理员 |
| `isAgent` | 是否代理商 |
| `currentUser` | 当前用户对象 |

| Action | 说明 |
|--------|------|
| `login` | 调用登录 API，提交 token 和 user |
| `register` | 调用注册 API |
| `logout` | 清除 token/user，调用 `clearSiteClientCache()` |

---

## 工具函数

```
utils/
├── auth.js          # token/user 的 localStorage 读写、clearSiteClientCache
├── request.js       # axios 实例
├── sse.js           # SSE 流式请求封装
├── chatStorage.js   # 聊天记录本地存储
└── index.js         # 通用工具函数
```

---

## 关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| `vue` | 2.x | 前端框架 |
| `vuex` | 3.x | 状态管理 |
| `vue-router` | 3.x | 路由 |
| `ant-design-vue` | 1.x | UI 组件库 |
| `axios` | - | HTTP 请求 |
| `@vue/cli-*` | - | 构建工具 |

---

## 测试与质量

- 无自动化测试配置（无 Jest/Cypress 等）。
- 代码质量依赖 ESLint（通过 Vue CLI 集成）。
- 手动测试为主。

---

## 常见问题 (FAQ)

**Q: 如何新增一个管理员页面？**
1. 在 `views/admin/` 创建 Vue 文件。
2. 在 `router/index.js` 的 `/admin` 子路由中添加路由记录。
3. 在 `layout/AdminLayout.vue` 的侧边菜单中添加菜单项。
4. 在 `api/` 中添加对应的 API 请求函数。

**Q: AI 对话如何实现流式输出？**
通过 `utils/sse.js` 封装的 SSE 客户端，调用后端 `/v1/chat/completions`（stream: true），逐块解析 `data:` 事件并更新消息内容。

**Q: 多租户站点如何区分？**
前端通过 `api/public.js` 调用 `/api/public/site/config` 获取当前站点配置（名称/公告/是否允许注册），根据返回的 `site_scope`（platform/agent）和 `agent_id` 区分平台站点与代理商站点。

**Q: 登录后如何跳转到正确门户？**
`router/index.js` 的导航守卫根据 `user.role` 判断：`admin` → `/admin/dashboard`，`agent` → `/agent/workbench`，`user` → `/user/dashboard`。

---

## 相关文件清单

```
frontend/src/
├── main.js
├── App.vue
├── router/index.js
├── store/index.js
├── api/
│   ├── auth.js, user.js, channel.js, model.js
│   ├── agent.js, chat.js, redemption.js
│   ├── subscription.js, system.js, public.js, request.js
├── utils/
│   ├── auth.js, request.js, sse.js
│   ├── chatStorage.js, index.js
├── layout/
│   ├── AdminLayout.vue
│   ├── UserLayout.vue
│   └── AgentLayout.vue
├── views/
│   ├── Login.vue, Register.vue
│   ├── admin/（14 个页面）
│   ├── user/（11 个页面）
│   ├── agent/（8 个页面）
│   └── common/AiChat.vue, MobileChat.vue
└── components/
    └── chat/ChatMessage.vue, ModelSelector.vue, SessionList.vue
```

---

## 变更记录 (Changelog)

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-12 | v1.0 | 初始模块文档生成 |
