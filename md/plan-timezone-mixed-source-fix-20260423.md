## 用户原始需求

当前反馈 `admin/logs` 页面原本时间正常，最近修复后整体多了 8 小时，需要修复该回归问题。

## 技术方案设计

已确认系统内时间字段并非统一来源：

- 一部分字段来自数据库 `server_default=func.now()`，本身就是数据库本地时间
- 另一部分字段来自应用层 `datetime.utcnow()`，序列化时又未携带时区，属于“无时区 UTC 时间”

此前把所有无时区时间都统一按 UTC 解析，导致原本正常的日志类页面被额外加了 8 小时。

本次修复方案：

1. 将公共 `formatDate` 恢复为本地时间直解析，避免影响原本正常页面。
2. 新增 `parseUtcDate` / `formatUtcDate`，只用于明确由 `utcnow()` 写入的字段。
3. 将前一次变更中过度使用 UTC 解析的页面改为“按字段精确处理”。

## 涉及文件清单

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

## 实施步骤概要

1. 在工具层拆分“本地时间格式化”和“UTC 时间格式化”。
2. 恢复日志、账单、请求明细等数据库本地时间字段的原始显示逻辑。
3. 保留登录时间、套餐开始结束时间、兑换码使用时间等 UTC 字段的北京时间修正。
4. 构建验证，确保没有新的编译错误。
