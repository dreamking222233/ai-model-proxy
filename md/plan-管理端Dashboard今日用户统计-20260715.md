# 管理端Dashboard今日用户统计 Plan

## 用户原始需求

- 深度阅读当前项目及相关文档。
- 在 `admin/dashboard` 当前用户总数、模型总数、今日请求次数、今日 Token 和今日金额等统计基础上，新增“今日活跃用户”，口径为今天使用过系统的去重用户总数。
- 在“用户总数”卡片区域增加上升图标，并显示今日新增用户数量。
- 优化“请求趋势”图：请求次数、使用 Token、消耗金额不再混用单柱与折线，改为不同颜色的并列柱状展示。
- 在“详细统计”区域增加活跃用户数和新增用户数；当天按 2 小时桶展示，七天/一个月按日展示。

## 技术方案设计

- 复用管理端 Dashboard 现有接口 `/api/admin/system/dashboard`，不新增接口、不新增表或字段；仅为新增统计补充查询索引。
- 沿用 `LogService._get_timezone_day_window(1)` 的 `Asia/Shanghai` 当天起点，确保今日活跃用户、今日新增用户与现有今日请求/Token/金额口径一致。
- 今日活跃用户从 `request_log` 统计：限定当天请求记录，对 `user_id` 去重，并关联 `sys_user` 过滤 `role = user`，保证与“用户总数”的用户范围一致；同一用户当天多次请求只计 1 人，请求成功或失败均视为当天使用过系统。
- 今日新增用户从 `sys_user.created_at` 统计：限定 `role = user` 且创建时间在当天起点之后。
- Dashboard 接口新增 `today_active_users`、`today_new_users` 两个整数字段。
- 前端新增“今日活跃用户”独立统计卡片；“用户总数”卡片的描述区增加上升图标和“今日新增 N 人”，其他卡片保持现有交互与跳转。
- 请求趋势使用三组并列柱：请求次数为蓝色、使用 Token 为绿色、消耗金额为橙色。由于三者数量级差异明显，分别绑定独立数值轴，避免请求次数被 Token 数量级压缩到接近 0；Tooltip 继续展示原始格式化值。
- `/api/admin/logs/requests/stats` 的每个时间桶新增 `active_users` 和 `new_users`。活跃用户按桶内请求用户去重并过滤普通用户角色；新增用户按 `sys_user.created_at` 落桶统计。无数据时间桶补零，保持图表与表格时间序列完整。
- 详细统计桌面表格增加“活跃用户”“新增用户”两列，移动端统计列表同步增加相同指标。
- 现有卡片栅格在超宽屏为每行 3 张，新增后总数为 6 张，可形成完整的 2 行布局；移动端继续每行 2 张。

## 涉及文件清单

- `backend/app/api/admin/system.py`
- `backend/app/models/user.py`
- `backend/app/services/log_service.py`
- `backend/sql/upgrade_admin_dashboard_user_stats_20260715.sql`
- `backend/sql/initData.sql`
- `backend/sql/init.sql`
- `sql/initData.sql`
- `frontend/src/views/admin/Dashboard.vue`
- `backend/test_admin_dashboard_today_users.py`
- `md/impl-管理端Dashboard今日用户统计-20260715.md`
- `md/review-管理端Dashboard今日用户统计-20260715.md`

## 实施步骤概要

1. 为 Dashboard 接口增加今日新增用户与今日活跃用户聚合。
2. 在用户总数卡片增加今日新增提示及上升图标。
3. 增加今日活跃用户卡片并保持现有响应式布局。
4. 将请求趋势调整为三种颜色的并列柱，并处理不同数量级的独立坐标轴。
5. 为详细统计的各时间桶增加活跃用户数和新增用户数，并更新桌面/移动端展示。
6. 编写后端统计口径测试，覆盖去重、跨日、角色过滤、空用户 ID和时间桶补零。
7. 为新增用户时间范围查询补充管理端与代理端复合索引，并同步升级 SQL、初始化 SQL 和 ORM 定义。
8. 执行后端测试、Python 语法检查、前端 lint/build 与差异检查。
9. 创建 Impl 文档并按项目规范执行 Codex 自审，根据审查结果迭代。

## 实施状态

- [x] 后端新增 `today_active_users` 与 `today_new_users`
- [x] 前端新增今日活跃用户卡片
- [x] 用户总数卡片展示今日新增用户
- [x] 请求趋势使用三色并列柱状图
- [x] 详细统计展示活跃用户数与新增用户数
- [x] 自动化测试与构建验证
- [x] Impl 与 Review 文档
