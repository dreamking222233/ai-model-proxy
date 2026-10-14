结论：**发现 1 项 P1，复核不通过。**

- **P1：缓存全命中时重复计费，提前触发每日限额。** [channel_passthrough_service.py:535](/Volumes/project/modelInvocationSystem/backend/app/services/channel_passthrough_service.py:535) 保留的补计分支把合法为零的普通输入桶补成 `logical_input_tokens`，同时仍单独计费缓存桶。错误金额随后进入[每日累计](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:12876)。沿真实 `_finalize` 路径用 SQLite 内存复现：100 个缓存输入、2 个输出，按测试夹具价格应计 **$0.0012**，实际计 **$0.0072**，使 **$0.005** 的日限额提前触发。OpenAI、Responses、Anthropic 三种透传均可复现。

验证依据：264 项离线后端回归通过；两个 Vue 页面的模板、脚本和 LESS 内存检查通过，但现有回归未覆盖上述真实补计路径。其余指定准入、资金计数、北京时间日界、独立重置、WS 逐轮校验及视频创建 Key 归属未见同步遗漏。

全程只读，未联网或访问真实上游、生产服务。