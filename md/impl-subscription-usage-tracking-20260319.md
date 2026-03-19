## 任务概述

修复 `admin/subscription` 页面中“套餐记录不显示”的问题，并为时间套餐补充独立的使用统计能力。实现后：

- 管理端套餐列表接口可正确返回记录数组，不再出现 `total` 有值但列表为空。
- 时间套餐用户调用时不扣余额，但会将消费记录标记为套餐计费，并关联到具体套餐记录。
- 管理端可按套餐查看期间的请求数、Token 和理论金额，并查看明细。

## 文件变更清单

| 文件 | 变更说明 |
| --- | --- |
| `backend/app/api/admin/subscription.py` | 修复分页返回结构，新增套餐使用详情接口 |
| `backend/app/models/log.py` | 为 `ConsumptionRecord` 增加 `billing_mode`、`subscription_id` |
| `backend/app/services/proxy_service.py` | 套餐模式写消费记录时标记计费模式并绑定套餐 |
| `backend/app/services/subscription_service.py` | 增加套餐维度的使用汇总与明细查询 |
| `frontend/src/api/subscription.js` | 新增查询套餐使用详情 API |
| `frontend/src/views/admin/SubscriptionManage.vue` | 修复列表取值，增加套餐使用摘要与详情弹窗 |
| `sql/init.sql` | 初始化库结构补充套餐计费字段 |
| `sql/upgrade_subscription_usage_tracking_20260319.sql` | 现网增量升级 SQL |
| `md/plan-subscription-usage-tracking-20260319.md` | 方案文档 |

## 核心代码说明

### 1. 套餐列表不显示的根因与修复

- 原实现使用 `ResponseModel(data=PageResponse(items=records, ...))`。
- `PageResponse` 实际没有 `items` 字段，导致 Pydantic 丢弃该字段，最终接口只剩 `total/page/page_size`，列表数组为空。
- 现改为直接返回统一分页字典，包含 `items` 与 `list` 两套键，兼容当前页面和项目内其他分页接口风格。

### 2. 套餐模式计费行为

- 当前系统在 `subscription_type == "balance"` 时才会扣余额。
- 本次保留这一行为，不让时间套餐影响用户余额或欠费值。
- 但在 `ConsumptionRecord` 中新增：
  - `billing_mode = "subscription"`
  - `subscription_id = 当前生效套餐ID`
- 因此套餐用户即使余额为 0 或负数，也能完整记录实际消费与 Token。

### 3. 套餐期间用量统计

- 新增套餐维度汇总：
  - 请求数
  - 输入 / 输出 / 总 Token
  - 理论金额
- 新记录优先按 `subscription_id` 精确归属。
- 旧历史记录没有新字段时，按“用户 + 套餐有效期 + 空归属字段”兜底统计，保证历史数据可见。

### 4. 续费后的过期切换修正

- 自审时发现：若用户已续费形成连续套餐，旧套餐到期后，`check_and_expire_subscriptions` 不能直接把用户切回 `balance`。
- 已改为在套餐过期时重新计算用户剩余的有效套餐：
  - 若仍存在有效套餐，用户继续保持 `unlimited`，并同步 `subscription_expires_at`
  - 仅在没有剩余有效套餐时才切回 `balance`

### 5. 管理端页面增强

- 套餐记录表新增“套餐期间使用”摘要列。
- 新增“查看使用情况”操作，弹窗中展示：
  - 套餐基本信息
  - 套餐汇总指标
  - 套餐期间消费明细表

## 测试验证

### 已执行

```bash
python -m py_compile backend/app/api/admin/subscription.py backend/app/models/log.py backend/app/services/proxy_service.py backend/app/services/subscription_service.py
```

结果：通过。

```bash
cd frontend && npm run lint
```

结果：通过，存在 1 条历史 warning：

- `frontend/src/store/index.js:54` `commit` 未使用（本次改动未触达）

### 自审结果

- 自审过程中识别出“续费后旧套餐过期会误切按量计费”的边界问题。
- 该问题已在 `backend/app/services/subscription_service.py` 修复，并重新通过 Python 编译检查与前端 lint。

## 现状结论

- `admin/subscription` 页面现在可以正常获取并展示套餐记录。
- 为用户开通套餐后，调用不会扣余额；套餐期间的消费、Token 和金额会单独记录，并可在管理端按套餐查看。
- 现网数据库需执行 `sql/upgrade_subscription_usage_tracking_20260319.sql` 后，新增字段才会生效。
