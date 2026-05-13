## 任务概述

优化 `admin/dashboard`：

- 移除渠道健康度图表
- 新增模型使用比率图表
- 请求趋势支持 `当天 / 七天 / 一个月`
- 当天范围按 2 小时粒度聚合
- 详细统计中的请求数与 Token 数值改为 tag 风格展示
- 调整模型使用比率区域的左右布局、颜色映射与等高表现

## 文件变更清单

- `backend/app/api/admin/log.py`
- `backend/app/api/admin/system.py`
- `backend/app/services/log_service.py`
- `backend/app/test/test_admin_dashboard_stats.py`
- `frontend/src/api/system.js`
- `frontend/src/views/admin/Dashboard.vue`
- `md/plan-admin-dashboard-analytics-20260430.md`

## 核心代码说明

- 后端请求统计接口支持 `range` 参数：
  - `today` 返回当天每 2 小时统计
  - `7d` 返回近 7 天按天统计
  - `30d` 返回近 30 天按天统计
- 管理员 dashboard 汇总接口新增 `model_usage_ratio` 字段，按请求量统计模型占比
- 前端 dashboard 重构了图表区域：
  - 左侧为请求趋势
  - 右侧为模型使用比率
  - 模型排名列表独立于 echarts legend 渲染
  - 排名颜色与图表颜色保持一致

## 测试验证

- `python -m py_compile backend/app/services/log_service.py backend/app/api/admin/log.py backend/app/api/admin/system.py backend/app/test/test_admin_dashboard_stats.py`
- `env PYTHONPATH=/Volumes/project/modelInvocationSystem/backend python -m unittest backend.app.test.test_admin_dashboard_stats`

## 待优化项

- 前端未执行完整构建与实际页面联调，仍建议在浏览器中做一次交互回归
- 模型使用比率当前按请求量占比统计，如后续需要也可补充按 Token 占比切换
