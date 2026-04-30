# 代理端结算系统代码审查

## 审查结论

结论：通过本地复核。

说明：首次自动代码审查发现 6 个需要修复的问题，已逐项修复。二次外部审查因上游返回 `INSUFFICIENT_BALANCE` 中断，未产出最终审查结论；本文件记录本地复核结果。

## 已修复问题

1. 套餐数量整数语义
   - 问题：套餐每日授信额度、套餐结算数量允许小数。
   - 修复：`AgentDailyLimitUpsert`、`AgentSettlementSettleRequest` 增加套餐整数校验；`AgentSettlementService` 在服务层再次强制套餐数量为整数；前端输入框对套餐场景设置整数精度。

2. 旧套餐资产池展示口径
   - 问题：管理端结算汇总中每条套餐销售行展示的是代理全部套餐库存，而不是当前套餐库存。
   - 修复：`list_admin_settlement_summary` 对套餐行按 `plan_id` 过滤库存，并返回 `asset_subscription_remaining` 与 `asset_subscription_used`。

3. 结算汇总资源筛选
   - 问题：前端传入 `resource_type`，后端 summary 接口未接收也未过滤。
   - 修复：`GET /api/admin/agents/settlements/summary` 增加 `resource_type` 查询参数，服务层增加过滤。

4. 停用额度误显示可用
   - 问题：`disabled` 额度仍返回正的 `remaining_amount`，代理端可能误认为可发放。
   - 修复：额度序列化时仅 `active` 状态计算剩余，停用统一返回 0；代理端发放按钮同时检查 `credit_limit.status === 'active'`。

5. 每日额度批量保存事务
   - 问题：批量保存循环调用单条保存，每条单独提交，可能半成功。
   - 修复：`batch_upsert_limits` 改为整批校验、整批写入、统一提交。

6. 参数校验中文化
   - 问题：FastAPI/Pydantic 参数校验错误可能返回英文。
   - 修复：`RequestValidationError` 统一转换中文 message，错误明细 `type` 固定为中文，不再暴露英文校验类型。

## 复核范围

- 授信发放路径：余额、图片积分、套餐库存不足时使用每日授信额度并写入待结算记录。
- 结算路径：管理端按代理、资源、套餐、日期筛选待结算记录，支持部分结算。
- 管理端页面：代理资产页配置每日额度，代理结算页查看汇总/明细并执行结算。
- 代理端页面：工作台展示额度，套餐页根据库存或授信额度判断是否可发放。
- SQL：升级 SQL 与 init SQL 已包含新增结算表。

## 验证结果

已通过：

```bash
python -m py_compile backend/app/models/agent.py backend/app/models/__init__.py backend/app/schemas/agent.py backend/app/services/agent_settlement_service.py backend/app/services/agent_asset_service.py backend/app/api/admin/agent.py backend/app/api/agent/stats.py backend/app/api/agent/subscription.py backend/app/api/agent/user.py backend/app/core/exceptions.py
```

已通过：

```bash
cd frontend && npm run build
```

前端构建仅有既有资源体积 warning。

## 剩余风险

- 本轮没有执行真实数据库联调，需要在本地或服务器执行 `sql/upgrade_agent_settlement_system_20260430.sql` 后做接口级验证。
- 代理兑换码仍使用代理余额池，不纳入授信结算，这是当前方案明确保留的边界。
