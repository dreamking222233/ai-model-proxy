当前：审查对象是已暂存变更与两份计费文档；先核对 staged diff、文档和测试改动，再按原问题、尾部异常、重复最终化及文档一致性给出 findings 与结论。
 # 计费-Responses流式用量丢失复审

## 审查结论

通过，可合入并按部署流程发布。

## Findings

- 原问题已覆盖：`response.completed` usage 在终止事件输出前写入局部计费快照，客户端在完成事件后断开时，最终清算仍取得普通输入、输出 token；缓存读取摘要保持不变。
- 完成后尾部异常已处理：终止事件已经转发后立即 `break`，不再继续消费上游迭代器，因此不会把已完成请求改写为失败日志。回归测试覆盖完成事件后伪上游异常。
- 重复最终化风险未由本次变更扩大：`billing_callback` 只更新两个局部变量，实际扣费仍集中在一次 `finally` 成功分支；`RequestLog.request_id` 的唯一约束和事务回滚提供现有去重保护。数据库集成级的重复最终化测试仍是后续增强项，但不阻塞本次修复。
- 测试已纳入暂存变更，且使用真实 `StreamingResponse`/ASGI disconnect 路径；另有 Responses 流重试、流文本处理和 Python 编译检查通过。
- 方案、实施记录与实现已同步描述“完成事件为终止边界”，未执行数据库结构变更。

## Verification

- `test_responses_stream_usage_billing.py`：2 项通过。
- `test_stream_text_buffering.py`：13 项通过。
- Responses 重试定向测试：3 项通过。
- `py_compile` 与 `git diff --cached --check`：通过。

## Residual Risk

仓库已有的 WebSocket 签名测试和部分 FakeDb 测试存在基线失败，与本次原生 Responses HTTP 流修复无关；部署后应观察一条新 `sub2api-codex` 请求的请求日志与消费记录字段。
