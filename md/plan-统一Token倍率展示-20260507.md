# 统一Token倍率展示

## 用户原始需求

- 保留 `token_multiplier`，但用户不需要直接看到这类系统配置。
- 管理员可以设置统一倍率，对用户请求的输入、输出 token 按倍率换算后再参与展示和计费。
- 在 `admin/logs`、`admin/agent-logs`、`agent/logs`、`user/balance` 的计费列展示更完整的计费详情。

## 技术方案设计

- 复用现有 `token_multiplier` 和 `price_multiplier` 系统配置，不新增计费规则。
- 前端在计费列中同时展示：
  - 原始 token
  - token 倍率后的计费 token
  - 单价
  - 小计
- 系统配置页将 `token_multiplier` 文案改成更明确的“统一Token倍率”，强调仅管理员可配置。
- 保持后端记账逻辑不变，只优化展示层的可读性。

## 涉及文件清单

- `frontend/src/views/admin/SystemConfig.vue`
- `frontend/src/views/admin/RequestLog.vue`
- `frontend/src/views/admin/AgentRequestLog.vue`
- `frontend/src/views/agent/RequestLog.vue`
- `frontend/src/views/user/BalanceLog.vue`

## 实施步骤概要

1. 梳理四个页面当前 token/cost 的展示结构。
2. 增加统一的倍率与原始 token 辅助方法。
3. 改写计费列文案，展示原始 token、倍率、计费 token 和费用明细。
4. 将系统配置中的 `Token倍率` 调整为 `统一Token倍率` 并补充说明。
5. 构建前端验证展示和语法正确性。
