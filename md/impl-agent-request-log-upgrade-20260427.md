# 代理请求日志页升级实施记录

## 任务概述

将 `agent/logs` 页面升级为接近 `admin/logs` 的体验，包括筛选区、用户汇总、调用明细、错误详情弹窗和图片请求展示，同时移除代理端不应看到的“实际模型”信息。

## 文件变更清单

- `backend/app/services/log_service.py`
  - 新增 `get_agent_user_usage_summary()`，限制代理只能查看自己下游用户的汇总。
- `backend/app/api/agent/log.py`
  - 新增 `GET /api/agent/logs/requests/user-summary`。
- `frontend/src/api/agent.js`
  - 新增 `getAgentRequestUserSummary()`。
- `frontend/src/views/agent/RequestLog.vue`
  - 重写代理请求日志页，补充筛选条件、用户汇总、明细表、状态详情弹窗。
  - 删除“实际模型”列和详情项。
- `md/plan-agent-request-log-upgrade-20260427.md`
  - 新增实施计划文档。

## 核心实现

代理日志汇总接口先校验目标用户是否属于当前代理，再复用现有的请求汇总统计逻辑，避免重复实现统计口径，同时阻断跨代理访问。

前端页面基于管理端日志页样式和交互方式适配代理端：

- 保留模型、状态、日期范围、用户 ID 筛选
- 保留 Token/图片积分复合展示
- 保留错误详情、缓存信息、会话压缩信息展示
- 移除“实际模型”列与详情项

## 测试验证

- `python -m py_compile backend/app/api/agent/log.py backend/app/services/log_service.py`：通过
- `npm run build`：通过，仅存在既有 bundle size warning
