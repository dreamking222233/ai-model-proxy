# Kiro AmazonQ Compatibility Review

## Review 输入

- `md/plan-kiro-amazonq-compatibility-20260321.md`
- `md/impl-kiro-amazonq-compatibility-20260321.md`
- `backend/app/services/proxy_service.py`

## Review 方式

- 使用 `codex exec` 对本次变更进行代码审查
- 审查过程中结合本地人工复核继续修正问题

## 审查中发现并已修复

### 1. Kiro 检测在 header 分支缺少模型名上下文

问题：

- `anthropic-beta` 头的移除逻辑依赖 `_is_kiro_amazonq_channel`
- 若仅通过 `43.156.153.12 + claude 模型名` 命中 Kiro 检测，而调用处未传模型名，头过滤可能失效

修复：

- 为 `_build_headers` 增加 `model_name` 参数
- 在 Anthropic 流式/非流式请求中显式传入模型名

### 2. Kiro 专属 400 可能过早截断 failover

问题：

- Kiro/AmazonQ 兼容分支中的请求类错误需要与真实渠道故障分离处理
- 原来的 `except ServiceException: raise` 会直接中断后续渠道尝试

修复：

- 在 Responses/OpenAI/Anthropic 三条 failover 链路中
- 对 `UPSTREAM_INVALID_REQUEST` / `CONTENT_TOO_LONG`
  这类请求错误改为记录为 `request_error` 并继续尝试其他渠道
- 仅在所有渠道都失败后返回对应 400

## 当前结论

- 已覆盖线上对话中确认的主要 Kiro/AmazonQ 兼容点
- 已避免把典型上游 400 请求错误继续误包装为 503
- 已避免将此类请求错误误计入渠道失败/熔断
- 已按最终要求取消服务端自动裁剪，改为保留原始请求并返回上游错误

## 仍然存在的验证缺口

- 未启动真实后端做端到端回归
- 未用真实 Claude Code 长对话再次验证：
  - 超大上下文自动裁剪
  - 不兼容参数过滤
  - 流式错误消息展示

## 最终判断

- 代码级别未发现新的阻断性缺陷
- 可以进入真实环境回归验证
- 若回归时仍有 AmazonQ 400，需要进一步采集实际请求体样本确认是否还有未覆盖字段
