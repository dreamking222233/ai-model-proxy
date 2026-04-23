## 用户原始需求

当前系统有很多页面的时间显示有问题，比如 `admin/users` 页面的最后登录时间、`admin/subscription` 页面的套餐开始和结束时间，都不是北京时间，需要统一修复。

## 技术方案设计

当前前端对后端返回的时间字符串主要使用 `new Date(value)` 直接解析；而后端大量返回的是 `datetime.utcnow().isoformat()` 生成的无时区 UTC 字符串。浏览器会将这类字符串按本地时间解析，导致展示时间与真实北京时间相差 8 小时。

本次采用前端统一修复方案：

1. 在 `frontend/src/utils/index.js` 新增统一时间解析函数。
2. 约定：后端返回的“无时区 datetime 字符串”一律按 UTC 解析，再转换为浏览器本地时区显示。
3. 统一改造公共 `formatDate`，让已使用该工具的页面自动生效。
4. 补齐若干页面内部手写的 `new Date()` / `toLocaleString()` 时间格式化逻辑，改为调用统一解析函数。
5. 同步修复依赖时间计算的逻辑，例如套餐剩余天数判断，避免展示修复后逻辑仍偏差。

## 涉及文件清单

- `frontend/src/utils/index.js`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/admin/SubscriptionManage.vue`（通过公共工具间接受益，必要时验证）
- `frontend/src/views/admin/RedemptionManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`
- `frontend/src/views/user/ApiKeyManage.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Redemption.vue`
- `frontend/src/views/user/UsageLog.vue`

## 实施步骤概要

1. 新增统一的服务端时间解析函数，兼容：
   - ISO 字符串带时区
   - ISO 字符串不带时区
   - `YYYY-MM-DD HH:mm:ss`
   - `YYYY-MM-DD`
2. 改造公共 `formatDate`，让管理页和已有公共格式化页面自动修复。
3. 替换页面内散落的手写时间解析和格式化逻辑。
4. 修复套餐到期时间相关的剩余天数计算。
5. 执行前端构建验证，确认无编译错误。
