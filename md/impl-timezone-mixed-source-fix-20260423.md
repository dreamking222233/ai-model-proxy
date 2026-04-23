## 任务概述

修复“时间展示修复引入回归”的问题。核心原因是系统内时间字段存在两类来源：

- 数据库 `server_default=func.now()` 生成的本地时间
- 应用层 `datetime.utcnow()` 写入的 UTC 时间

此前把所有无时区时间都统一按 UTC 解析，导致 `admin/logs`、请求明细、账单明细等原本正常的页面额外增加了 8 小时。

## 文件变更清单

- `frontend/src/utils/index.js`
- `frontend/src/views/admin/RequestLog.vue`
- `frontend/src/views/admin/UserManage.vue`
- `frontend/src/views/admin/SubscriptionManage.vue`
- `frontend/src/views/admin/RedemptionManage.vue`
- `frontend/src/views/user/Dashboard.vue`
- `frontend/src/views/user/Profile.vue`
- `frontend/src/views/user/ApiKeyManage.vue`
- `frontend/src/views/user/BalanceLog.vue`
- `frontend/src/views/user/Redemption.vue`
- `frontend/src/views/user/UsageLog.vue`
- `md/plan-timezone-mixed-source-fix-20260423.md`

## 核心代码说明

### 1. 工具层拆分两套格式化逻辑

在 `frontend/src/utils/index.js` 中：

- `formatDate` 恢复为本地时间直解析
- 新增 `parseUtcDate`
- 新增 `formatUtcDate`

这样可以避免全局 UTC 解析误伤日志类页面。

### 2. 只对明确 UTC 来源字段做北京时间转换

使用 `formatUtcDate` / `parseUtcDate` 的字段包括：

- 用户最后登录时间
- 套餐开始/结束/到期时间
- API Key 最后使用时间
- 兑换码使用时间、过期时间

### 3. 恢复日志类页面的原本时间显示

以下页面恢复使用本地时间格式化：

- `admin/RequestLog.vue` 中的请求时间、最近请求时间
- `user/UsageLog.vue` 中的请求时间
- `user/BalanceLog.vue` 中的请求时间
- `admin/RedemptionManage.vue` 中的创建时间

## 测试验证

执行：

```bash
cd frontend
npm run build
```

结果：

- 构建成功
- 仅存在仓库原有 eslint warning 和打包体积 warning
- 无新增编译错误
