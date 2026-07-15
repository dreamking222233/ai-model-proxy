# 管理端Dashboard今日用户统计 Impl

## 任务概述

管理端 `admin/dashboard` 新增今日活跃用户、今日新增用户及分时/按日用户统计，并将请求趋势中的请求次数、Token、金额统一改为不同颜色的柱状图。

## 文件变更清单

- `backend/app/api/admin/system.py`
  - Dashboard 汇总接口新增 `today_active_users`、`today_new_users`。
- `backend/app/services/log_service.py`
  - 请求详细统计的 2 小时桶和日期桶新增 `active_users`、`new_users`。
  - 请求聚合使用外连接用户表，在不改变原有请求次数口径的前提下过滤普通用户并去重。
  - 新增用户独立按注册时间聚合，无请求的时间桶也能正确返回新增人数。
- `backend/app/models/user.py`
  - 增加 `(role, created_at)` 与 `(agent_id, role, created_at)` ORM 索引定义。
- `backend/sql/upgrade_admin_dashboard_user_stats_20260715.sql`
  - 为已部署数据库幂等增加两条 Dashboard 用户统计复合索引。
- `sql/initData.sql`、`backend/sql/initData.sql`、`backend/sql/init.sql`
  - 同步初始化表结构索引；历史 `backend/sql/init.sql` 不含 `agent_id`，仅同步普通管理端索引。
- `frontend/src/views/admin/Dashboard.vue`
  - 新增“今日活跃用户”卡片。
  - “用户总数”卡片增加上升图标与今日新增人数。
  - 请求趋势改为蓝色请求次数、绿色 Token、橙色金额三组柱状图，并分别使用独立数值轴。
  - 详细统计桌面表格和移动端列表新增活跃用户、新增用户。
- `backend/test_admin_dashboard_today_users.py`
  - 新增 Dashboard 用户统计回归测试。
- `md/plan-管理端Dashboard今日用户统计-20260715.md`
  - 记录需求、方案、文件范围、实施步骤与完成状态。

## 核心代码说明

### 今日活跃用户

- 时间范围采用 `LogService._get_timezone_day_window(1)`，时区为 `Asia/Shanghai`。
- 从 `request_log` 关联 `sys_user`，限定 `sys_user.role = user` 后对 `request_log.user_id` 去重计数。
- 同一用户当天发起多次请求只计 1 人；成功与失败请求均表示当天实际使用过系统。
- 代理账号、管理员账号、空 `user_id` 请求不计入活跃用户。
- 顶部请求数、Token、金额、活跃用户与新增用户均统一使用 `[today, now]` 闭区间，排除未来时间脏数据。

### 今日新增用户

- 从 `sys_user` 按 `created_at` 统计当天注册且 `role = user` 的用户。
- 顶部卡片返回当天总数；详细统计在“当天”视图按 2 小时聚合，在“七天/一个月”视图按日聚合。
- 新增用户查询与请求查询相互独立，因此某个时间桶即使没有请求，仍会显示正确的新增用户数。

### 三色柱状趋势

- 请求次数：蓝色柱，独立“请求次数”数值轴。
- 使用 Token：绿色柱，独立“Token”数值轴。
- 消耗金额：橙色柱，独立“USD”数值轴。
- 三类数据数量级差异较大，独立数值轴避免请求次数被 Token 数量级压缩到接近 0；Tooltip 继续显示原始次数、Token 和 6 位小数 USD。
- 移动端隐藏三条数值轴标签，保留图例、三色柱与 Tooltip，避免小屏横向拥挤。
- 移动端统计卡片改用 `min-height: 152px`，为用户总数卡片的两段描述预留换行空间，避免今日新增被裁剪。

### 查询索引

- 管理端新增用户统计使用 `idx_sys_user_role_created_at (role, created_at)`。
- 代理端详细统计使用 `idx_sys_user_agent_role_created_at (agent_id, role, created_at)`。
- 升级 SQL 通过 `information_schema` 判断索引与 `agent_id` 字段是否存在，可重复执行。

## 测试验证

- `cd backend && python -m unittest test_admin_dashboard_today_users.py`
  - 7 个测试通过。
  - 覆盖同用户去重、普通用户角色过滤、空用户 ID、跨日排除、起止边界、未来请求/Token/金额排除、代理隔离、跨 2 小时桶活跃、无请求时间桶/日期新增用户补数、2 小时桶和按日桶。
- `cd backend && python -m py_compile app/api/admin/system.py app/models/user.py app/services/log_service.py test_admin_dashboard_today_users.py`
  - 通过。
- `cd frontend && npm run lint`
  - 通过，无 lint 错误。
- `cd frontend && npm run build`
  - 构建成功；仅保留项目原有 bundle 体积告警。
- `git diff --check`
  - 通过。
- 本地 MySQL 执行 `backend/sql/upgrade_admin_dashboard_user_stats_20260715.sql` 两次
  - 两次均成功，验证脚本幂等。
  - `information_schema.statistics` 确认：
    - `idx_sys_user_role_created_at = role, created_at`
    - `idx_sys_user_agent_role_created_at = agent_id, role, created_at`
- Codex Review
  - 第一轮发现 3 个中等级问题并完成修复。
  - 第二轮无严重/中等级问题，最终通过。

## 待优化项

- 当前 Dashboard 汇总仍为多条独立聚合 SQL，数据量继续增长后可结合生产慢查询与 `EXPLAIN` 评估合并查询。
- 请求活跃用户聚合当前可使用 `request_log(created_at, id)` 先缩小当天范围；如生产数据量显示去重仍有压力，再评估增加 `(created_at, user_id)`，避免无执行计划依据时继续增加写入索引成本。
