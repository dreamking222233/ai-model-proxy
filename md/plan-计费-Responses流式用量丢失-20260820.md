# 计费-Responses流式用量丢失实施方案

## 用户原始需求

- 排查最近请求中普通输入、输出 token 显示为 0，而缓存读取 token 正常的问题。
- 修复问题后提交 GitHub，并更新生产服务器项目。

## 技术方案设计

生产数据表明，Responses 流的 `response.completed` 已携带完整 usage，缓存摘要也已正确解析；但普通输入、输出计费回调位于终止事件输出之后。客户端收到完成事件后关闭连接时，生成器直接进入清算 `finally`，导致默认 0 被写入请求日志与消费记录。

修复方案：

1. 在解析 `response.completed` usage 后、向客户端输出该终止事件前，立即更新本次请求的计费 token 快照。
2. 将 `response.completed` 作为上游终止边界，避免完成事件后的连接尾部异常覆盖成功状态。
3. 增加真实 ASGI 断流和完成事件后上游尾部异常的回归测试，不调整已有缓存 token 拆分逻辑。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `backend/test_responses_stream_usage_billing.py`
- `md/plan-计费-Responses流式用量丢失-20260820.md`
- `md/impl-计费-Responses流式用量丢失-20260820.md`
- `md/review-计费-Responses流式用量丢失-20260820.md`

## 实施步骤概要

- [x] 核对生产请求日志、消费记录与缓存 usage 字段。
- [x] 定位 Responses 流式计费回调晚于终止事件的问题。
- [x] 调整计费快照更新时间。
- [x] 添加并运行回归测试。
- [x] 创建实施记录并自行 Review。
- [x] 提交并推送 GitHub。
- [x] 更新生产服务器、重启后端并验证健康状态与新请求数据。

## 风险与回滚

- 风险：重复调用计费回调。该回调只更新函数内 token 快照，不直接扣费，因此重复赋值不会重复扣款。
- 回滚：回退本次 Git 提交并按生产流程重启 8085 后端。
