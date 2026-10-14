**结论：v1 暂不能进入实施。** 总体方向符合需求，但鉴权边界、异步视频消费归属和 WebSocket 拒绝流程仍有阻塞项，需要先修订为 v2。

本次仅做只读静态核对，未修改文件、运行数据库测试或构建，未调用外部模型或子代理。

1. **阻塞：公共结算入口写错，需明确金额取值位置。**
   [方案第 10 行](/Volumes/project/modelInvocationSystem/md/plan-API密钥-每日限额-20261014.md:10)中的 `_log_success_request` 在当前代码中不存在。实际公共事务入口是 [ProxyService._deduct_balance_and_log_once](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:12277)，其中先锁定 Key，再完成赠送额度、套餐、余额和账单处理。

   金额口径基本正确：应累计**每次实际用量及现有价格规则算出的请求美元消费价值**，对应 `ConsumptionRecord.total_cost` 和 Key 的 `total_cost` 增量。不能取赠送额度扣减后的 `total_cost_decimal`，也不能直接相加套餐 `quota_consumed_amount` 与余额扣款——套餐可能按官方美元价值或 Token 计量。建议在资金来源拆分前保留明确的美元金额变量，并在现有事务内累计一次。

2. **阻塞：统一鉴权无条件检查，会阻断已提交视频任务。**
   [video_proxy.py](/Volumes/project/modelInvocationSystem/backend/app/api/proxy/video_proxy.py:80)的任务查询、内容下载同样调用 `verify_api_key`。而 [handle_video_retrieve](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:17521)还会在任务完成时触发补结算。若 Key 因其他请求达额，原视频将无法查询、结算或下载，与“允许在途请求正常完成”冲突。

   应保留统一身份鉴权，将每日限额作为**新生成请求的准入检查**。既有任务查询、取回和补结算继续执行，并保留现有身份及任务所有权校验。模型列表、`count_tokens` 是否受限也应在方案中明确。

3. **阻塞：异步视频可能计入取回结果的 Key，而非创建任务的 Key。**
   [_bill_video_route_if_needed](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:16800)直接把当前传入的 `api_key_record` 交给美元按次结算；[VideoTaskBillingSnapshot](/Volumes/project/modelInvocationSystem/backend/app/models/log.py:387)只记录用户，没有创建 Key。

   因而同一用户用 Key A 创建任务、Key B 查询完成结果时，消费可能累计到 B，A 的每日统计失真。需要保存并使用创建任务的 Key ID，覆盖内存路由、持久化快照、重启恢复及补结算；同时明确存量未结算任务缺少 Key ID 的处理方式。这会扩大当前文件和升级 SQL 清单。

4. **阻塞：WebSocket 的检查点和错误处理尚未具体化。**
   “每轮独立读取最新 Key”方向正确，但当前存在三个需要落地说明的位置：

   - [普通 WS](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:6234)：每次生成轮次进入上游前检查。
   - [原生 WS](/Volumes/project/modelInvocationSystem/backend/app/services/channel_passthrough_service.py:1096)：首轮及后续 `response.create`／`response.append` 均检查，覆盖文本帧、二进制 JSON 和普通渠道回退。不能依赖连接中保存的 Key 快照。
   - [握手入口](/Volumes/project/modelInvocationSystem/backend/app/api/proxy/openai_proxy.py:170)：当前仅关闭连接；普通错误事件也没有业务 `code`，原生中途异常会被转换为通用 1011 关闭。

   v2 应明确握手与已连接会话的错误契约，保证中文提示和 `API_KEY_DAILY_LIMIT_EXCEEDED` 可识别；将本地限额拒绝视为终止错误，避免切换渠道或记录渠道故障。检查只针对新生成轮次，不能因达额取消正在接收结果的轮次。影响文件应补上 `openai_proxy.py`。

其余核对与建议如下：

- **时区：方案可行。** 使用显式 UTC 转 UTC+8，并以北京时间 `DATE` 保存日期即可。建议明确跨日请求按结算时归属，且在取得写锁后采样日期，避免锁等待跨零点后写回旧日期。列表、准入、重置、结算共用日期规则；前端直接使用服务端日期，不用浏览器本地日期判定“今天”。

- **事务与竞态：现有结构能够承载。** [session_scope](/Volumes/project/modelInvocationSystem/backend/app/database.py:51)负责统一提交和回滚，美元结算已有独立会话和 Key 行锁。每日累计 helper 不应自行提交，也不能在结算时因达限抛错，否则会回滚在途请求账务。设置、重置使用相同行锁，并明确：重置后才结算的在途请求仍会计入重置后的用量。独立新会话读取适合 WS，单纯重复查询或 `refresh` 不足以保证摆脱旧事务快照。允许在途超额，因此无需预占额度或持锁等待上游。

- **精度：需要补充舍入规则。** 现有结算中存在 Decimal 转 float 的过程。应规定每日增量与账单采用相同的六位小数量化规则，尤其覆盖半微美元边界；只写“使用 Decimal”还不足以保证对账一致。图片积分及积分视频没有美元汇率，排除美元累计正确；仅发生积分消费的 Key 不会因这些消费触发美元限额。

- **升级：可实施，但需定义启用边界。** 根目录 `sql/initData.sql` 是 README 指定的初始化入口，方案选择正确。升级应逐字段幂等，重复执行不得清零已有统计，并提供数据库默认值。需说明先升级结构、再切换全部后端进程的顺序，以及旧进程在途结算的处理；否则混合版本期间会漏计。首次上线当日只统计启用后的消费，应明确展示这一限制。视频归属修复还需额外迁移。

- **前端：现有 Vue 2／Ant Design Vue 页面可增量实现。** [ApiKeyManage.vue](/Volumes/project/modelInvocationSystem/frontend/src/views/user/ApiKeyManage.vue:437)已有创建、分组编辑和统计重置模式可复用。建议明确空值为不限额、零值非法、六位精度及金额上限；若支持完整 `DECIMAL(20,6)` 范围，应避免用 JavaScript Number 往返金额。每日受限状态应独立于 `active/disabled`，两个重置操作分别说明。页面目前没有持续刷新机制，需补充手动刷新、定期刷新或明确快照时间，避免跨日仍显示旧状态。现有未提交页面改动应保留。

- **验证：当前测试基础不足以证明并发正确。** [现有 Key 测试](/Volumes/project/modelInvocationSystem/backend/test_api_key_usage.py:14)使用 SQLite，透传测试大量模拟结算，不能验证 MySQL 行锁与事务隔离。实施验收应增加 MySQL 双会话并发累计、设置／重置竞态、回滚重试；覆盖余额、赠送、套餐及混合资金来源，普通／透传 HTTP、两条 WS、异步视频跨 Key 取回、UTC 16:00 跨日，以及“已准入请求继续完成、后续生成被拒绝”。

**进入实施的条件：先修正上述四项阻塞，并在 v2 补齐结算入口、请求分类、视频 Key 归属、WS 错误契约和对应文件／方法级 To-Do。当前无需引入额度预占机制。**
