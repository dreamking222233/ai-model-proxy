# 统一Token倍率展示

## 任务概述

- 保留管理员可调的 `token_multiplier`，并把它作为统一倍率作用于输入、输出、缓存读取 token 的展示与计费说明。
- 四个账单/日志页面新增更完整的计费列明细，让用户和管理员能直接看到“原始 token -> 倍率后 token -> 费用”的换算过程。

## 文件变更清单

- `frontend/src/views/admin/SystemConfig.vue`
- `frontend/src/views/admin/RequestLog.vue`
- `frontend/src/views/admin/AgentRequestLog.vue`
- `frontend/src/views/agent/RequestLog.vue`
- `frontend/src/views/user/BalanceLog.vue`

## 核心代码说明

- `SystemConfig.vue`
  - 将 `Token倍率` 调整为 `统一Token倍率`，并说明其作用于输入、输出、缓存读取 token。
- `admin/RequestLog.vue`
  - 费用列展示原始 token、Token倍率、计费 token 和小计。
  - 详情弹窗补充统一 Token 倍率和价格倍率，以及完整公式。
- `admin/AgentRequestLog.vue`
  - 同步补齐费用列与详情弹窗的倍率明细。
- `agent/RequestLog.vue`
  - 代理端账单页同步展示 token 倍率与价格倍率的完整计费过程。
- `user/BalanceLog.vue`
  - 用户侧余额/消费明细页展示原始 token、计费 token 和费用拆分，但不直接展示倍率名称和值。

## 测试验证

- `npm run build`

## 待优化项

- 当前仅优化展示层，后端记账逻辑保持不变。
- 如果后续要把价格倍率和 token 倍率进一步合并成一个“全局倍率”概念，需要额外做一次后端口径整理。
