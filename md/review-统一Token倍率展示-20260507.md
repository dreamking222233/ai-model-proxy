# 统一Token倍率展示 Review

## 结论

- 本次实现符合需求，没有发现阻塞问题。
- 现有改动仅调整展示层，不改变后端真实记账口径。

## 已确认项

- `token_multiplier` 仍由管理员在系统配置页统一设置。
- 后端返回的 `raw_*`、`billable_*`、`token_multiplier_snapshot`、`price_multiplier_snapshot` 字段已被前端正确复用。
- `admin/logs`、`admin/agent-logs`、`agent/logs` 保留完整倍率明细。
- `user/balance` 不直接展示倍率名称和值，仅展示原始 token、计费 token、单价和费用结果。
- 前端 `npm run build` 通过，只有既有体积 warning。

## 建议

- 如果后续还要把倍率影响扩展到更多页面，例如排行榜、用户汇总卡片、导出报表，建议统一抽一个 token/cost 展示工具方法，避免四处复制格式。
