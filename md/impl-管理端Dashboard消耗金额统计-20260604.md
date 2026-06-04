# 管理端Dashboard消耗金额统计 Impl

## 任务概述

在管理端 Dashboard 增加 USD 消耗金额统计，并按最新要求将页面精简为只展示请求次数、使用 Token、使用金额三类指标；不再展示成功率、成功次数、失败统计和模型占比。

## 文件变更清单

- `backend/app/api/admin/system.py`
  - `/api/admin/system/dashboard` 返回 `today_cost`。
- `backend/app/services/log_service.py`
  - `get_request_stats()` 按当天 2 小时桶、近 7 天/30 天日期桶聚合 `total_cost`。
- `frontend/src/views/admin/Dashboard.vue`
  - 首页指标卡仅保留“今日请求次数 / 今日使用 Token / 今日使用金额”。
  - 详细统计表仅保留“请求次数 / 使用 Token / 消耗金额”。
  - 请求趋势图仅保留“请求次数 / 使用 Token / 消耗金额”。
  - 移除成功率、成功次数、今日错误、失败列、失败序列、模型使用比率区域。

## 核心代码说明

- 金额来源使用 `consumption_record.total_cost`，并过滤 `total_cost > 0`、`request_id is not null` 与 `model_name is not null`，避免充值、调账等非请求消费记录进入统计。
- Dashboard 今日金额使用本地时区当天窗口起点，与现有今日请求和今日 Token 口径保持一致。
- 请求趋势保留请求次数、使用 Token、消耗金额，金额使用独立右侧坐标轴，避免金额和数量级不同导致图形不可读。
- 金额展示使用 `$` 前缀和 6 位小数，避免低额调用被展示为 `$0.00`。

## 测试验证

- `python -m py_compile backend/app/api/admin/system.py backend/app/services/log_service.py`
- `npm run lint`（frontend）
- `git diff --check`
