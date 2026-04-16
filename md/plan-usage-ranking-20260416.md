# 使用排行 Plan

## 用户需求
- 新增一个管理员和普通用户都能访问的“使用排行”页面。
- 页面展示当天、近7天、近30天内的 token 使用排行榜。
- 仅展示前5名。
- UI/UX 参考当前系统已有页面风格。

## 技术方案
- 后端新增一个统计接口，按时间范围汇总 request_log.total_tokens 并按用户聚合，返回前5名。
- 前端新增共享页面组件，使用现有的卡片、分段按钮、排行榜列表和表格风格。
- 在 admin/user 两侧路由与侧边栏菜单中分别挂载同一页面。

## 涉及文件
- backend/app/services/log_service.py
- backend/app/api/user/stats.py
- frontend/src/api/user.js
- frontend/src/views/user/UsageRanking.vue
- frontend/src/router/index.js
- frontend/src/layout/UserLayout.vue
- frontend/src/layout/AdminLayout.vue

## 实施步骤
1. 增加后端 token 排行统计方法与接口。
2. 增加前端 API 封装。
3. 创建共享排行榜页面，接入 1/7/30 天切换与 Top 5 展示。
4. 在 admin/user 路由与菜单中添加入口。
5. 运行语法与构建验证。
