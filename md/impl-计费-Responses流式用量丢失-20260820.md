# 计费-Responses流式用量丢失实施记录

## 任务概述

修复 Responses 流式请求在客户端收到 `response.completed` 后立即关闭连接时，普通输入与输出 token 以 0 进入请求日志和消费记录的问题。缓存读取 usage 原本已正确保存，本次调整使全部 usage 字段采用同一完成事件的快照。

## 文件变更清单

- `backend/app/services/proxy_service.py`：在输出终止事件前更新计费 token 快照，并在输出完成事件后停止读取上游流。
- `backend/test_responses_stream_usage_billing.py`：覆盖真实 ASGI 断连与完成事件后的上游尾部异常场景。
- `md/plan-计费-Responses流式用量丢失-20260820.md`：实施方案与进度。
- `md/impl-计费-Responses流式用量丢失-20260820.md`：实施记录。

## 核心代码说明

Responses 上游的 `response.completed` 包含最终 input、output 与 cached token。旧代码先将缓存摘要写入 `collected_usage`，随后向客户端输出完成事件，直到生成器完全结束才执行 `billing_callback`。客户端在完成事件后关闭流会跳过该回调，但外层清算仍执行，因此普通 input/output 使用默认 0，而缓存字段有值。

新代码在解析 usage 并构造缓存摘要后立即执行 `billing_callback`，之后才输出完成事件，并将该事件作为上游终止边界。该回调只更新当前请求函数内的计费快照，不直接创建消费记录或扣款。

## 测试验证

- `test_responses_stream_usage_billing.py`：2 项通过。真实 ASGI 断流后最终计费参数为 input=2752、output=946，缓存读取=77568；完成事件后的伪上游异常不再覆盖成功计费。
- `test_stream_text_buffering.py`：通过。
- Python 编译检查：通过。
- Responses 重试相关 3 项定向测试通过。
- 扩展测试发现仓库现有失败：3 项 WebSocket 用例调用参数未跟随当前方法签名，2 项长上下文用例的 `FakeDb` 缺少 `query`；均不在本次 Responses HTTP 流式改动路径。

## 待验证项

- 部署后检查 8085 健康状态。
- 等待一条新的 `sub2api-codex` Responses 请求，确认 `request_log` 与 `consumption_record` 的普通输入、输出和缓存读取字段均非异常 0，费用包含对应分项。
