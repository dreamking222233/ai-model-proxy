# 代理请求日志页升级计划

## 用户原始需求

优化 `agent/logs` 页面，参考 `admin/logs` 页面，但不显示“实际模型”列。

## 技术方案

1. 后端新增代理范围内的用户汇总接口，确保代理只能查看自己下游用户的日志汇总。
2. 前端代理 API 新增用户汇总方法。
3. 代理端 `RequestLog.vue` 升级为管理端同等级别的筛选、表格、详情弹窗和用量展示。
4. 移除代理端中的“实际模型”列和详情项，其余展示能力尽量与管理端一致。

## 涉及文件

- `backend/app/services/log_service.py`
- `backend/app/api/agent/log.py`
- `frontend/src/api/agent.js`
- `frontend/src/views/agent/RequestLog.vue`

## 实施步骤

1. 新增代理用户汇总服务与接口。
2. 增加前端 API 封装。
3. 重写代理日志页 UI 和交互。
4. 执行后端语法检查与前端构建验证。
