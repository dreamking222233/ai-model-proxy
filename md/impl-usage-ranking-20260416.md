# 使用排行 Impl

## 任务概述
- 新增管理员和普通用户共享的“使用排行”页面。
- 支持当天、近7天、近30天 token 排行切换，固定展示前5名。
- 在后台新增 token 排行统计接口。

## 文件变更
- backend/app/services/log_service.py
- backend/app/api/user/stats.py
- frontend/src/api/user.js
- frontend/src/views/user/UsageRanking.vue
- frontend/src/router/index.js
- frontend/src/layout/UserLayout.vue
- frontend/src/layout/AdminLayout.vue

## 核心实现
- 后端按 request_log.total_tokens 聚合用户 token 消耗，按时间窗口排序取前5名。
- 前端使用与现有统计页一致的玻璃卡片、分段按钮和统计卡样式。
- 菜单项分别加入管理员和用户侧边栏，路由复用同一页面组件。

## 验证
- `python -m py_compile backend/app/services/log_service.py backend/app/api/user/stats.py backend/app/api/admin/user.py` 通过。
- `npm run build` 通过，现有仓库 warning 保留不改动。
