**通过。无阻塞项。**

- `_finalize`（[channel_passthrough_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/channel_passthrough_service.py:535)）以归一化后的 `logical_input_tokens` 判断是否补计；缓存读/写输入存在时保持普通桶为零，不再使用请求估算。仅逻辑输入为零且有输出时保留补计。
- 三协议解析器均提供上游实际逻辑输入；公共结算只调用一次每日累计（[proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:12876)）。
- 新增 30 项回归覆盖三协议、JSON/SSE、全读/全写/混合缓存及缺失/显式零输入，并经真实 SQLite 账务路径核对精确消费、逐笔累计和限额触发。P1 已修复，既有补计行为保留。

无可复现问题，无阻塞项。已有验证记录为新增 30 项、相关 286 项通过；本轮复跑因环境无可用临时目录未启动。