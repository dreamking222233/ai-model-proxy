# Plan 评估：价格调控

## 自动评估执行情况

按规范执行：

```bash
codex exec "请评估以下实施方案的可行性与合理性：
文档：./md/plan-价格调控-20260617.md
请检查：1.方案完整性 2.技术选型 3.实施可行性 4.潜在风险
给出修改建议" | tee ./md/plan-review-价格调控-20260617.md
```

执行结果：`codex exec` 可启动，但自定义模型服务返回 `401 Unauthorized: Invalid API key`，无法生成外部评审内容。

## 本轮自评结论

评估通过，可以进入实施。

## 完整性

方案覆盖数据库结构、ORM、Schema、Service、API、计费预检、实际扣费、图片/视频积分计费、前端模型管理、价格调控页面、路由菜单、初始化脚本和验证流程，范围完整。

## 技术选型

- 采用 `unified_model.model_series` 做模型归类，符合当前模型主数据结构。
- 采用独立 `model_price_adjustment_rule` 表承载倍率规则，避免继续堆叠 `system_config` KV。
- 规则按北京时间每日时间窗判断，适配跨天场景。
- 复用现有 `price_multiplier_snapshot` 存储全局倍率与分类倍率乘积，保持日志和账单页面兼容。

## 实施可行性

当前后端计费集中在 `proxy_service.py`，模型 CRUD 集中在 `ModelService`，前端管理端已有模型管理和系统配置模式可复用，实施路径清晰。

## 潜在风险与约束

- 图片/视频媒体积分没有单独倍率快照字段，本次通过 `image_credit_record.multiplier` 和 `request_log.image_credits_charged` 记录实际扣费结果。
- 文本日志无法区分全局倍率和分类倍率，本次保持兼容，后续如需审计明细可新增 `price_adjustment_rule_id_snapshot` 与 `price_adjustment_multiplier_snapshot`。
- 若存在大量旧模型未归类，升级 SQL 的前缀回填只能覆盖常见系列，仍需要管理员在 `admin/models` 手动校准。

## 建议

- 实施时优先保证预检与实际扣费调用同一倍率解析服务。
- 规则冲突时必须有稳定排序：`priority ASC, id DESC`。
- `schedule_type=daily_time` 必须支持 `start_time > end_time` 的跨天窗口。
