# 套餐管理用户搜索实施记录

## 任务概述

优化管理端和代理端套餐管理页的发放逻辑，支持按用户名/邮箱搜索并下拉选择用户。代理端只能选择当前代理名下的终端用户。

## 文件变更清单

- `backend/app/api/admin/user.py`
  - 管理端用户列表接口新增 `roles` 查询参数，支持按角色过滤。
- `frontend/src/views/admin/SubscriptionManage.vue`
  - 模板发放与旧版无限套餐开通由手填 `user_id` 改为远程搜索下拉。
  - 仅搜索终端用户。
  - 支持根据路由中的 `user_id` 预载用户选项。
- `frontend/src/views/agent/SubscriptionManage.vue`
  - 代理端发放套餐弹窗由手填 `user_id` 改为远程搜索下拉。
  - 仅搜索当前代理名下终端用户。
  - 支持根据路由中的 `user_id` 预载用户选项。

## 核心实现

- 管理端通过 `listUsers({ roles: 'user' })` 仅搜索终端用户，避免将代理账号或管理员账号作为套餐发放对象。
- 代理端通过 `listAgentUsers()` 搜索，后端接口天然限定为当前代理 `agent_id` 下且 `role = user` 的用户。
- 前端使用远程搜索下拉而不是本地过滤，避免大用户量下无法命中目标用户。
- 若页面通过 `user_id` 路由参数跳转进入，会自动调用详情接口将该用户补进选项列表，避免下拉中看不到预选值。

## 测试验证

- `python -m py_compile backend/app/api/admin/user.py`：通过
- `npm run build`：通过，仅存在既有 bundle size warning
