## 任务概述

修复前端多个页面的时间展示偏差问题。根因是后端大量返回无时区的 UTC 时间字符串，前端直接使用 `new Date()` 解析，浏览器将其当作本地时间，导致北京时间展示错误。

本次改造统一在前端增加服务端时间解析规则，并补齐若干页面内散落的自定义格式化逻辑。

## 文件变更清单

- `frontend/src/utils/index.js`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/admin/RedemptionManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`
- `frontend/src/views/user/ApiKeyManage.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Redemption.vue`
- `frontend/src/views/user/UsageLog.vue`
- `md/plan-timezone-display-fix-20260423.md`

## 核心代码说明

### 1. 统一服务端时间解析

在 `frontend/src/utils/index.js` 中新增 `parseServerDate`：

- 对带时区的 ISO 时间直接解析
- 对 `YYYY-MM-DD HH:mm:ss` / `YYYY-MM-DDTHH:mm:ss` 这类“无时区 datetime”自动补 `Z`，按 UTC 解析
- 对 `YYYY-MM-DD` 保持日期语义，补 `T00:00:00`
- 对超出 3 位的小数秒做裁剪，避免浏览器兼容问题

同时将公共 `formatDate` 改为基于 `parseServerDate`，使已使用该工具的页面自动修复。

### 2. 修复套餐剩余时间判断

在以下页面中，套餐到期时间的比较逻辑改为使用 `parseServerDate`：

- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/user/Dashboard.vue`

这样不仅展示时间正确，`今天到期` / `剩余 N 天` / `已过期` 的判断也与真实时间一致。

### 3. 修复散落页面的手写时间格式化

以下页面原先使用局部 `new Date()` / `toLocaleString()`，已改为统一工具：

- `frontend/src/views/admin/RedemptionManage.vue`
- `frontend/src/views/user/Profile.vue`
- `frontend/src/views/user/ApiKeyManage.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Redemption.vue`
- `frontend/src/views/user/UsageLog.vue`

## 测试验证

执行命令：

```bash
cd frontend
npm run build
```

结果：

- 构建成功
- 仅存在仓库原有告警：
  - `frontend/src/store/index.js` 的未使用变量 eslint warning
  - 前端产物体积告警
- 未引入新的编译错误

## 待优化项

- 后端当前仍在大量返回无时区的 UTC 时间字符串；若后续需要统一对外 API 语义，可继续在后端序列化层补全明确时区标记。
- 前端仍有少量日期相关业务逻辑直接使用本地 `new Date()` 处理“当前时间”，目前不影响服务端时间展示，但后续可以继续统一到时间工具层。
