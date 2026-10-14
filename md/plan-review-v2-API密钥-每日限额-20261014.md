**允许实施，四个阻塞均已解决。** v2 已明确真实结算入口及金额口径、生成与查询的限额边界、视频创建 Key 的持久化归属及历史兼容、两条 WS 的逐轮检查与拒绝契约。

有一处非阻塞文档遗漏：涉及文件清单应补上 `backend/app/models/log.py`，对应已列出的 `VideoTaskBillingSnapshot.user_api_key_id` 修改。

本次仅定点只读核对，未运行测试、外部模型或子代理。