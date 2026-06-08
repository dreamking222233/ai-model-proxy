# 用户端资产来源说明

用户端新增“资产来源”页面，用于展示用户余额增加/减少记录的来源、备注、变动金额、变动前后余额和时间。

## 页面入口

- 用户端菜单：`资产来源`
- 前端路由：`/user/asset-source`

页面顶部展示当前余额，下方提供变动方向筛选。

## 接口

```http
GET /api/user/balance/asset-records
```

查询参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `page` | `1` | 页码，最小 1 |
| `page_size` | `20` | 每页数量，1-100 |
| `direction` | `all` | `all`、`increase`、`decrease` |

返回字段：

| 字段 | 说明 |
|------|------|
| `record_key` | 前端表格唯一键，格式为 `balance-{id}` |
| `asset_type` | 固定为 `balance` |
| `asset_type_text` | 资产类型中文名 |
| `direction` | `increase` 或 `decrease` |
| `amount` | 变动绝对值 |
| `source` | 来源文案 |
| `remark` | 用户可见备注 |
| `request_id` | 关联请求或订单号 |
| `model_name` | 关联线上充值渠道文案或空 |
| `action_type` | 统一归类动作 |
| `billing_mode` | 余额计费模式 |
| `balance_before` | 变动前余额 |
| `balance_after` | 变动后余额 |
| `created_at` | 创建时间 |

## 来源规则

来源按以下优先级判定：

1. 已支付线上充值订单：显示 `线上充值`，备注显示 `支付宝` 或 `微信支付`。
2. 代理端操作：显示 `代理端`，备注显示代理填写内容。
3. 管理端操作：显示 `管理端`，备注显示管理员填写内容。
4. 历史增额记录：显示 `历史充值`。
5. 其他减少记录：显示 `系统扣减`。

模型调用产生的余额扣费记录不在该页面展示，仍在用户端消费明细页面查看。

## 管理与代理备注

管理端和代理端在用户余额充值或扣除弹窗中可填写备注。备注会写入余额流水，用户端资产来源页直接展示该备注。

## 数据库升级

已有环境需要执行：

```sql
source backend/sql/upgrade_user_asset_source_records_20260608.sql;
```

该脚本为 `consumption_record` 补充：

- `operator_id`
- `remark`
- `idx_consumption_operator_id`
- `idx_consumption_user_created_id`
- `request_id` 索引兼容检查

## 注意事项

- 历史余额人工充值因旧表没有备注，只能展示为 `历史充值` 或空备注。
- 线上充值只识别 `payment_recharge_order.status = paid` 且 `recharge_type = balance` 的记录，避免未支付订单或图片积分订单被误判。
