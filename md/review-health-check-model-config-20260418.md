整体上，这次实现已经把数据库字段、后端优先级选择、独立保存接口和前端编辑入口都接上了，主功能基本落地；但我这里有 2 个需要优先处理的问题。

1. 单渠道“检查”实际使用的是未保存草稿，不是已保存配置，和方案描述不一致。
[frontend/src/views/admin/HealthMonitor.vue#L498](/Volumes/project/modelInvocationSystem/frontend/src/views/admin/HealthMonitor.vue#L498) 这里把 `record._healthCheckModelDraft` 直接作为 `model_name` 发给后端；[backend/app/api/admin/health.py#L39](/Volumes/project/modelInvocationSystem/backend/app/api/admin/health.py#L39) 和 [backend/app/services/health_service.py#L171](/Volumes/project/modelInvocationSystem/backend/app/services/health_service.py#L171) 又把这个值放到最高优先级。结果是用户即使没点“保存”，单次检查和日志也会使用临时输入值，而不是渠道当前持久化配置。这和 plan 里“单独触发该渠道健康检查时使用最新保存值”不一致，也会让“检查结果”和“当前已保存配置”脱节。

2. 专用保存接口会把空 payload 静默当成“清空配置”，接口语义不够安全。
[backend/app/schemas/channel.py#L41](/Volumes/project/modelInvocationSystem/backend/app/schemas/channel.py#L41) 把 `health_check_model` 设计成可选；[backend/app/api/admin/channel.py#L56](/Volumes/project/modelInvocationSystem/backend/app/api/admin/channel.py#L56) 直接透传；[backend/app/services/channel_service.py#L143](/Volumes/project/modelInvocationSystem/backend/app/services/channel_service.py#L143) 无条件写回数据库。这样客户端如果误发 `{}`，会把 `health_check_model` 清空，而不是报参数错误。对一个“单字段更新接口”来说，这种静默清空比较危险。

补充说明：
我没有找到这次功能对应的自动化测试；目前只有 `py_compile` 和前端构建验证。这个改动涉及“模型选择优先级”和“专用保存接口”，建议至少补 3 类测试：已保存模型优先、单渠道检查是否允许临时覆盖、空 payload/空字符串的接口行为。

优化建议：
1. 先定规则：如果产品预期是“检查只用已保存值”，就去掉单渠道检查的 `model_name` override，前端检查按钮只走持久化配置。
2. 如果产品确实想保留“临时检查草稿值”，那要把 plan/impl/UI 文案都改明确，例如把按钮语义改成“临时检查”，避免用户误以为已经保存。
3. 保存接口建议要求 `health_check_model` 显式出现；清空配置也建议走明确语义，比如传空串并做显式处理，或单独加 `clear` 语义，避免 `{}` 误清空。
4. `get_health_status` 里新增的 `effective_health_check_model` 会额外做一次按渠道查映射；渠道数量多时可以考虑批量取映射，避免页面继续增加 N+1 查询。
