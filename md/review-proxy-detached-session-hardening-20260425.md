## Review 结论

未发现阻塞性问题。

本次实现与需求一致，已经覆盖：

- 文本请求主链路之外的图片计费/日志 detached ORM 风险
- detached 场景下的回归测试
- 对渠道健康策略与数据库兼容性的事实复核

## 已确认事项

- `_deduct_image_credits_and_log()` 已改为在新会话前提取 `user_id`、`api_key_id`、`channel_id`，不再依赖 detached 对象属性。
- 回归测试会在直接访问 `id/name/protocol_type` 抛错的情况下运行，能够证明当前实现确实依赖安全快照，而不是偶然通过。
- 相关单测已通过，没有引入文本订阅路径的回归。

## 后续建议

1. 渠道健康问题建议单独开任务，不要与计费/日志稳定性修复混在同一次发布里。
2. 若后续继续收敛 detached 风险，可考虑把 `channel_name/protocol_type` 这类快照读取抽成统一 helper，减少分散写法。
3. `datetime.utcnow()` 的弃用告警后续可统一替换为 timezone-aware UTC，但不属于本次阻塞项。
