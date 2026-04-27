# Plan: 代理账号创建与专用登录入口

**日期**: 2026-04-26
**功能**: `agent-account-login`
**任务规模**: 中型

## 一、用户原始需求

在管理端 `/admin/agents` 新增代理时，可以直接设置代理账号和密码，并为代理分配前台域名，例如：

- `test.xiaoleai.team`

代理后台需要有独立登录页面，例如：

- `http://test.xiaoleai.team/agents/login`

登录后进入该代理端后台管理页，并展示代理端菜单。

## 二、技术方案

### 后端

- 扩展 `AgentCreate` 请求体，支持 `owner_username / owner_email / owner_password`
- `AgentService.create_agent(...)` 中支持两种代理主账号来源：
  - `owner_user_id`：绑定已有用户为代理账号
  - `owner_username + owner_password`：创建新的代理账号并绑定当前代理
- 新账号角色固定为 `agent`
- 新账号 `agent_id` 固定为当前新建代理 ID
- 邮箱可选，不传时自动生成内部邮箱，避免 `sys_user.email` 非空唯一约束失败
- 所有错误信息保持中文

### 前端

- 管理端代理新增弹窗增加代理登录账号、邮箱、密码字段
- 编辑代理时不展示账号密码创建字段，避免误解为改密码
- 新增路由 `/agents/login`
- 复用现有登录页，根据路由切换为代理后台登录模式
- 代理登录页隐藏注册入口
- 代理登录页登录成功后只允许 `role=agent` 进入 `/agent/dashboard`
- 未登录访问 `/agent/*` 时跳转到 `/agents/login`

## 三、涉及文件

- `backend/app/schemas/agent.py`
- `backend/app/services/agent_service.py`
- `backend/app/test/test_agent_portal.py`
- `frontend/src/views/admin/AgentManage.vue`
- `frontend/src/views/Login.vue`
- `frontend/src/router/index.js`
- `md/impl-agent-account-login-20260426.md`

## 四、实施步骤

1. 扩展后端代理创建 schema
2. 扩展代理创建服务，支持创建代理主账号
3. 补充后端单测
4. 扩展管理端新增代理表单
5. 新增 `/agents/login` 路由和代理登录模式
6. 调整路由守卫，让代理后台未登录时进入代理专用登录页
7. 执行后端单测、Python 编译、前端构建验证
