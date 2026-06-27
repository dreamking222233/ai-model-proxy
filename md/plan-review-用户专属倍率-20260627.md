# 用户专属倍率实施方案评估

评估文档：`./md/plan-用户专属倍率-20260627.md`

评估结论：方案总体可行，技术路线与当前 FastAPI + SQLAlchemy + Vue 2 + Ant Design Vue 架构匹配，且已覆盖数据库、规则解析、文本计费、媒体积分、管理端页面、审计与验证。建议在实施前修订为 Plan v2，补齐数据模型、审计字段、媒体积分账本、接口约束和回归测试细节后再编码。

## 1. 方案完整性

完整性评价：基本完整，但有几个必须补齐的实现约束。

已覆盖内容：

- 明确了用户原始需求：`admin/users` 设置用户专属倍率、`admin/price-adjustments` 查看用户规则、计费链路按用户倍率执行。
- 正确识别现有全局规则入口 `PriceAdjustmentService.resolve_multiplier(db, unified_model)` 没有用户维度。
- 覆盖文本预检、文本实际扣费、图片/视频媒体积分三类关键链路。
- 规划了独立表 `user_price_adjustment_rule`，避免把用户规则混入全局规则表。
- 规划了请求日志和消费记录的新快照字段，保留旧 `price_multiplier_snapshot` 兼容现有报表。
- 前端入口、汇总展示、操作审计、初始化脚本和验证项都有安排。

需要补齐内容：

- `user_price_adjustment_rule` 表缺少 `name` 字段。现有全局规则 `model_price_adjustment_rule` 的 ORM 和服务校验要求规则名称，计划又要求“字段与全局价格规则基本一致”，但 SQL 草案没有 `name`。建议增加 `name VARCHAR(128) NOT NULL`，或者明确用户规则不需要 name，并单独调整 schema、表单与序列化。
- 媒体积分审计只覆盖了 `request_log`、`consumption_record`，但图片/视频实际余额流水在 `image_credit_record`。若要审计媒体积分是否命中用户规则，应给 `image_credit_record` 增加 `adjustment_price_multiplier_snapshot`、`price_adjustment_source_snapshot`、`price_adjustment_rule_id_snapshot`，或明确媒体积分只在 `request_log` 审计。
- 计划把 `log_service.py`、`balance_service.py`、`subscription_service.py` 列为可选增强，但新增字段如果要返回前端或保持详情展示一致，这些文件不应完全可选。至少要确认旧字段展示不破坏，新字段是否出现在接口响应中。
- 缺少自动化测试清单。仅有编译、构建和手工验证不足以覆盖计费回归，建议新增针对 `PriceAdjustmentService.resolve_adjustment`、预检倍率、扣费倍率、媒体积分倍率的单元测试或轻量集成测试。

## 2. 技术选型

技术选型评价：合理。

- 独立 `user_price_adjustment_rule` 表比复用 `sys_user` 字段或混入全局规则表更合适，能支持多系列、多计费类型、时间窗和优先级。
- “用户专属规则覆盖全局分类规则，系统全局价格倍率仍叠加”的语义清晰，符合需求示例中 `GPT x1`、`Claude x2` 的管理直觉。
- 保留 `resolve_multiplier` 兼容旧调用，同时新增结构化 `resolve_adjustment` 是低风险改造方式。
- API 拆分为 `/api/admin/users/{user_id}/price-adjustments` 和 `/api/admin/price-adjustments/user-rules` 合理，既满足用户页编辑，也避免污染现有全局规则接口。
- 不使用外键与当前项目风格一致，但必须在删除用户服务中同步清理用户规则。

建议调整：

- 结构化解析结果建议使用明确对象或 dataclass/Pydantic schema，而不是散落 dict 字段，至少在 service 内部统一键名，避免 `rule_id`、`user_rule_id`、`global_rule_id` 语义重复。
- `resolve_user_rule` 与 `resolve_global_rule` 应共享匹配逻辑，避免用户规则和全局规则在 `model_series/model_type/billing_type/priority/time window` 上出现分叉。
- 用户规则 CRUD 应复用现有 `_normalize_payload` 能力，但需要让类型注解支持 `UserPriceAdjustmentRule`，当前方法签名偏向 `ModelPriceAdjustmentRule`。
- SQL 升级脚本应沿用现有 procedure + `information_schema` 风格，并确保新增字段可重复执行。

## 3. 实施可行性

实施可行性评价：可实施，复杂度主要在计费调用点一致性和前端复用。

后端可行性：

- 现有 `PriceAdjustmentService` 已有全局规则的标准化、时间窗、优先级和有效矩阵逻辑，用户规则可以复用大部分实现。
- `proxy_service.py` 中已有明确入口：`_build_text_quota_precheck`、`_deduct_balance_and_log_once`、`_apply_media_credit_price_adjustment`，按计划传入 `user_id` 能解决主链路。
- `AuthService.delete_user()` 当前已手动清理多张用户关联表，继续加入 `UserPriceAdjustmentRule` 删除符合现有实现方式。
- `LogService.create_operation_log()` 已可直接写操作日志，不需要新增基础设施。

前端可行性：

- `frontend/src/api/user.js` 与 `frontend/src/api/priceAdjustment.js` 扩展成本低。
- `UserManage.vue` 增加抽屉入口、`PriceAdjustmentManage.vue` 增加 Tab 展示符合现有管理端形态。
- 如果抽取 `UserPriceAdjustmentDrawer.vue`，可以降低用户页和价格调控页重复实现风险。

实施前建议明确：

- `_build_text_quota_precheck` 当前签名没有 user 参数，所有调用点都要更新，不能只改函数内部。
- 实际扣费使用 `fresh_user.id` 解析用户规则是正确的，但预检也必须用同一个业务用户 ID，否则余额预检和最终扣费可能不一致。
- 异步视频是否已保存“调整后的积分成本”需要在实现前确认。若完成扣费阶段重新解析规则，会出现创建任务后规则变化导致扣费漂移。

## 4. 潜在风险

1. 数据模型不一致风险
   SQL 草案没有 `name` 字段，但现有全局规则和前端表单有规则名称概念。若实施时直接复用全局表单，会出现字段缺失或校验失败。

2. 审计不完整风险
   只给 `request_log` 和 `consumption_record` 加字段，可能无法完整解释媒体积分流水。图片/视频主要扣减记录在 `image_credit_record`，需要同步考虑。

3. 规则覆盖语义的运营风险
   “用户规则覆盖全局分类规则”合理，但需要在页面和接口文档中明确：用户 GPT x1 是覆盖全局 GPT 倍率，不是与全局 GPT 倍率相乘；系统全局倍率仍然叠加。

4. 预检与扣费不一致风险
   方案已识别该风险，但实际落地时最容易漏改调用点。特别是 OpenAI、Anthropic、Responses 入口都可能调用 `_build_text_quota_precheck`。

5. 异步媒体任务漂移风险
   视频任务创建和完成之间如果跨越规则修改，完成时重新解析倍率会导致账单和创建时展示/预检不一致。

6. 查询性能风险
   用户规则列表若 join `sys_user` 并支持 keyword 搜索，需确认用户名、邮箱筛选方式和分页顺序。索引只覆盖规则匹配，不覆盖 keyword 模糊搜索。

7. 历史数据兼容风险
   新字段默认值为 1 / default 可以兼容旧数据，但前端如果展示“默认规则”可能误导老账单。建议老数据 source 为空时显示“历史未记录”或不展示来源。

## 5. 修改建议

建议 Plan v2 必须调整：

1. 在 `user_price_adjustment_rule` 中增加 `name VARCHAR(128) NOT NULL`，或明确用户规则不需要名称并重写相关 schema、表单和服务校验。
2. 明确 `image_credit_record` 是否增加倍率来源快照字段；若不增加，要说明媒体积分审计以 `request_log` 为准。
3. 将 `log_service.py`、`balance_service.py`、`subscription_service.py` 从“可选增强”改为“按响应字段兼容性检查后决定是否修改”，避免新增字段不可见或详情展示不一致。
4. 增加自动化测试项：
   - 用户规则命中优先于全局规则。
   - 用户规则禁用/时间窗未命中时回退全局规则。
   - `resolve_multiplier` 旧签名不传 user 时保持全局行为。
   - 文本预检与实际扣费使用同一倍率。
   - 图片/视频媒体积分传入 user 后命中用户规则。
5. 明确异步视频任务的倍率快照存储位置，创建任务时冻结调整后积分成本或冻结规则解析结果。
6. 用户规则接口更新和删除时校验 `rule.user_id == path user_id`，防止通过 URL 修改其他用户规则。
7. 用户规则汇总列表建议 left join 用户，已删除用户显示“用户已删除”，并提供 user_id 保底展示。
8. `price_adjustment_source_snapshot` 建议允许 `legacy` 或空值，避免老数据被误判为 `default`。
9. 操作日志建议在 API 层统一写入，并包含管理员 ID、目标用户 ID、规则 ID、旧值/新值摘要；更新操作至少记录修改后的系列、类型、计费类型、倍率和启用状态。
10. 前端建议第一版抽取 `UserPriceAdjustmentDrawer.vue`，价格调控页只读汇总可以复用打开同一抽屉，避免重复维护表单。

## 6. 是否通过

评估结果：有条件通过。

该方案方向正确、可落地，但建议先按以上修改建议形成 Plan v2，尤其补齐 `name` 字段、媒体积分流水审计、异步视频倍率冻结、接口归属校验和自动化测试后，再进入实施阶段。
