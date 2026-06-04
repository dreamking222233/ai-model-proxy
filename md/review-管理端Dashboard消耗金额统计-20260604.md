**Findings**
- 未发现阻塞性问题。`admin/dashboard` 当前页面只渲染“请求次数 / 使用 Token / 使用金额”三类数据，旧的成功率、成功次数、失败统计、模型占比均已从页面结构、表格列和图表系列中移除，见 [Dashboard.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/Dashboard.vue:147)、[Dashboard.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/Dashboard.vue:177)、[Dashboard.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/Dashboard.vue:317)。
- 低优先级优化：后端接口仍在计算并返回已不再需要的旧统计字段。`/api/admin/system/dashboard` 还会查询并返回 `today_errors`、`model_usage_ratio`，见 [system.py](/Volumes/project/modelInvocationSystem/backend/app/api/admin/system.py:95)；`/api/admin/logs/requests/stats` 仍持续聚合 `success_requests`、`failed_requests`，见 [log_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py:522)、[log_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py:577)、[log_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py:641)。这不影响当前页面显示，但接口契约和最新需求不完全一致，且有额外查询成本，建议清理。

**结论**
当前实现符合你给出的最新页面要求。前端 Dashboard 只展示三项卡片、三项趋势和三项明细，没有发现成功率、成功次数、失败统计或模型占比的残留展示逻辑，见 [Dashboard.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/Dashboard.vue:30)、[Dashboard.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/Dashboard.vue:147)、[Dashboard.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/Dashboard.vue:335)。

后端金额统计口径也基本正确，当前只统计真实请求流水：
- 聚合时统一限定 `total_cost > 0`、`request_id is not null`、`model_name is not null`，见 [system.py](/Volumes/project/modelInvocationSystem/backend/app/api/admin/system.py:98) 和 [log_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/log_service.py:538)。
- 真正的请求扣费记录由代理请求链路写入，且会带 `request_id` 和 `model_name`，见 [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:9345)。
- 人工充值/扣款这类非请求流水，要么 `request_id/model_name` 为空，要么金额为负数，因此会被排除，见 [balance_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/balance_service.py:73)、[balance_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/balance_service.py:135)、[payment_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/payment_service.py:877)。

**说明**
本次是静态代码审查，未重新跑前端页面和接口联调。一个需要产品口径确认的边界是：图片积分请求走 `ImageCreditRecord`，不会进入这套 USD 金额统计，见 [proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:11803)。如果“使用金额”未来要折算图片积分价值，当前实现还不覆盖这部分。
