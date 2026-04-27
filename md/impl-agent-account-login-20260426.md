# Impl: 代理账号创建与专用登录入口

**日期**: 2026-04-26
**功能**: `agent-account-login`
**状态**: 已完成实现与验证

## 一、任务概述

本次实现解决两个问题：

1. 平台管理员在 `/admin/agents` 新增代理时，可以直接设置代理登录账号和密码
2. 代理可以通过独立路由 `/agents/login` 登录代理后台

示例访问方式：

- 代理前台域名：`test.xiaoleai.team`
- 代理后台登录页：`https://test.xiaoleai.team/agents/login`
- 登录成功后进入：`/agent/dashboard`

## 二、后端改动

### 2.1 请求体扩展

文件：

- `backend/app/schemas/agent.py`

`AgentCreate` 新增字段：

- `owner_username`
- `owner_email`
- `owner_password`

其中 `owner_email` 可选，不传时后端会自动生成内部邮箱。

### 2.2 创建代理时创建代理账号

文件：

- `backend/app/services/agent_service.py`

`AgentService.create_agent(...)` 当前支持两种模式：

1. `owner_user_id`
- 绑定已有用户为代理账号

2. `owner_username + owner_password`
- 创建新的代理账号
- `role = agent`
- `agent_id = 当前新建代理ID`
- `source_domain = agent.frontend_domain`

同时补充了中文错误：

- 不能同时绑定已有代理账号和创建新代理账号
- 代理登录账号不能为空
- 代理登录密码不能为空
- 代理登录账号已存在
- 代理登录邮箱已被使用

## 三、前端改动

### 3.1 管理端代理创建表单

文件：

- `frontend/src/views/admin/AgentManage.vue`

新增代理时显示：

- 登录账号
- 登录邮箱（可选）
- 登录密码

编辑代理时不显示这些字段，避免误认为可以在代理编辑页直接改密码。

### 3.2 代理专用登录路由

文件：

- `frontend/src/router/index.js`

新增：

- `/agents/login`

未登录访问 `/agent/*` 时，会跳转到：

- `/agents/login`

### 3.3 登录页代理模式

文件：

- `frontend/src/views/Login.vue`

`/agents/login` 复用现有登录页，但有单独行为：

- 标题显示为代理后台登录
- 隐藏注册入口
- 登录成功后只允许 `role=agent` 的账号进入 `/agent/dashboard`
- 非代理账号会被退出并提示“当前账号不是代理账号”

## 四、验证结果

已执行：

```bash
python -m py_compile backend/app/schemas/agent.py backend/app/services/agent_service.py backend/app/test/test_agent_portal.py
```

结果：通过。

已执行：

```bash
env PYTHONPATH=backend /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python -m unittest backend.app.test.test_agent_portal
```

结果：

- `Ran 9 tests`
- `OK`

已执行：

```bash
npm run build
```

结果：

- 构建成功
- 仍有原有 bundle 体积告警，不影响本次功能

## 五、使用方式

平台管理员操作：

1. 打开 `/admin/agents`
2. 点击新增代理
3. 填写代理编码、代理名称、前台域名
4. 填写代理登录账号和密码
5. 保存

代理操作：

1. 打开 `https://test.xiaoleai.team/agents/login`
2. 输入平台创建代理时设置的账号和密码
3. 登录后进入代理后台菜单
