# 端午节抽奖功能说明

## 活动时间

所有活动时间均按北京时间（Asia/Shanghai）处理。

- 报名开始：2026-06-19 00:00:00
- 报名结束：2026-06-21 20:00:00
- 抽奖开始：2026-06-21 23:00:00

## 奖励规则

- 第一名：300 美元
- 第二名：200 美元
- 第三名：100 美元
- 第 4-10 名：50 美元

系统只记录中奖名单和奖励金额，不会自动给用户充值。管理员需要在用户管理中手动给中奖用户加余额。

## 报名资格

用户满足任一条件即可报名：

- 历史开通过日卡及以上套餐，即套餐记录 `duration_days >= 1`。
- 余额累计充值大于 100 美元。
- 真实模型请求消费累计大于 100 美元。

累计充值取 `user_balance.total_recharged`，覆盖管理端手动充值、代理端通过系统能力加额度、用户支付宝/微信在线充值等已进入余额系统的充值。累计消费按 `consumption_record.total_cost` 统计真实模型请求消费，仅计入 `total_cost > 0` 且 `request_id`、`model_name` 非空的记录，不计入管理端扣款、代理余额回收等人工资金调整。

## 数据表

活动使用 `dragon_boat_lottery_entry` 表保存报名和中奖结果。

关键字段：

- `user_id`：唯一，保证每个用户只能报名一次。
- `qualification_type` / `qualification_detail`：报名资格来源和说明。
- `total_recharged_snapshot` / `total_consumed_snapshot`：报名时累计充值和真实模型消费快照。
- `prize_rank` / `prize_amount`：中奖名次和奖金。
- `drawn_by_user_id` / `drawn_at`：抽奖管理员和开奖时间。

## 用户端接口

- `GET /api/user/dragon-boat-lottery/status`
  - 返回活动状态、资格检测结果和当前用户报名记录。
- `POST /api/user/dragon-boat-lottery/register`
  - 在报名时间内检测资格并报名。
  - 已报名时幂等返回已有报名记录。

## 管理端接口

- `GET /api/admin/dragon-boat-lottery/summary`
  - 返回报名人数、中奖人数、活动状态和中奖名单。
- `GET /api/admin/dragon-boat-lottery/entries`
  - 分页查询报名用户，支持按用户 ID、用户名、邮箱搜索。
- `POST /api/admin/dragon-boat-lottery/draw`
  - 2026-06-21 23:00:00 后可执行。
  - 如果已经存在中奖名单，直接返回已有名单，不重新抽奖。

## 并发保护

抽奖在事务内使用 `SELECT ... FOR UPDATE` 锁定报名记录，并在锁定后再次检查是否已有中奖名单。数据库层对 `prize_rank` 设置唯一约束，避免并发情况下同一名次重复写入。

## 前端入口

- 用户端：`/user/dragon-boat-lottery`
- 管理端：`/admin/dragon-boat-lottery`
