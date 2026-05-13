## Plan Review

对 `plan-request-audit-hardening-20260425.md` 的评估结论如下：

### 通过项

1. 方向正确
- 当前 `/user/balance` 账单与明细页实际走的是 `/api/user/profile/usage-logs`，底层依赖 `RequestLog`。
- 因此把“请求必记录”的第一优先级放在 `RequestLog` 完整性上是正确的。

2. 风险识别基本完整
- 已识别：
  - 本地记账异常被吞
  - 套餐周期并发创建冲突
  - 流式请求难以回滚已输出内容
  - fallback 日志可能与 `request_id` 唯一约束冲突

3. 实施路径可落地
- `proxy_service.py` 是主要切入点；
- `subscription_service.py` 负责周期冲突修复；
- 用户端无需大改页面，只要日志链路稳定即可覆盖主要可见性诉求。

### 修订建议

1. 将 plan 聚焦到 `RequestLog`，不要把 `ConsumptionRecord` 当作用户页面主依赖。
2. 增加“fallback 失败日志最小落库”设计，避免详细日志写入失败时整条请求不可见。
3. 将 Responses websocket 明确纳入修复范围，因为它同样调用 `_deduct_balance_and_log(...)`。
4. 非流式主链路尽量对齐图片链路：上游成功但本地记账失败时，应中断成功返回。

### 评审结论

方案可行，按上述修订后可进入实施。
