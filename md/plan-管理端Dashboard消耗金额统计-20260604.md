# 管理端Dashboard消耗金额统计 Plan

## 用户原始需求

在 admin/dashboard 页面添加消耗金额统计，例如今天总计消耗了多少美刀、每天消耗美刀数量等。随后补充要求：页面不再显示成功率、成功次数、失败统计、模型占比，只保留请求次数、使用 Token、使用金额。

## 技术方案设计

- 后端复用现有 `consumption_record.total_cost`，不新增计费逻辑、不新增表结构。
- `/api/admin/system/dashboard` 增加 `today_cost`，用于首页今日消耗金额卡片。
- `/api/admin/logs/requests/stats` 的分时/按日统计补齐 `total_cost` 字段，用于趋势图和详细统计表。
- 前端 `Dashboard.vue` 精简为三类指标：请求次数、使用 Token、使用金额；增加今日消耗金额卡片、趋势图金额序列、详细统计金额列，并移除成功/失败/模型占比展示。
- 金额统一按 USD 展示，保留 6 位小数，低金额不被四舍五入成 0。

## 涉及文件清单

- `backend/app/api/admin/system.py`
- `backend/app/services/log_service.py`
- `frontend/src/views/admin/Dashboard.vue`
- `md/impl-管理端Dashboard消耗金额统计-20260604.md`
- `md/review-管理端Dashboard消耗金额统计-20260604.md`

## 实施步骤概要

1. 增加 Dashboard 今日金额聚合。
2. 增加请求统计分时/按日金额聚合。
3. 前端添加金额格式化、今日金额卡片、详细统计金额列。
4. 前端趋势图添加消耗金额折线和右侧 USD 坐标轴。
5. 移除成功率、成功次数、失败统计和模型占比展示。
6. 执行语法检查和自审。
