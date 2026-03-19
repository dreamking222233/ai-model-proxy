# OpenClaw 兼容修复自审记录

## 审查方式

- 依据文档：
  - `./md/plan-openclaw-support-20260319.md`
  - `./md/impl-openclaw-support-20260319.md`
- 审查方式：
  - 使用 `codex exec` 基于最新工作区进行自审
  - 主执行者补充逐文件复核关键代码路径

## 审查结论

- 未发现阻塞性问题。
- 当前实现已经覆盖本次需求中的主要兼容缺口：
  - OpenClaw -> 中转入口的多认证头兼容
  - 中转 -> 上游的认证头兼容补发
  - Anthropic 请求补齐 `anthropic-version`
  - `User-Agent` 与少量关键附加头透传
  - 管理端默认值与接入文档同步纠偏

## 本轮审查中发现并已修复的问题

### 1. 渠道创建 schema 默认值仍会回落到旧的 `x-api-key`

- 文件：`backend/app/schemas/channel.py`
- 问题说明：
  - 虽然 `ChannelService` 已支持按协议推导默认 `auth_header_type`，
  - 但 `ChannelCreate` 原先仍把 `auth_header_type` 默认成 `x-api-key`，
  - 这会导致绕过前端直接调用管理 API 创建 OpenAI 渠道时，重新落回旧默认值。
- 处理结果：
  - 已将 `ChannelCreate.auth_header_type` 改为可选字段，由 `ChannelService` 统一按协议兜底。

### 2. 管理端切换协议时会覆盖用户手工选择的认证头

- 文件：`frontend/src/views/admin/ChannelManage.vue`
- 问题说明：
  - 初版实现会在协议切换时直接把 `auth_header_type` 改成推荐值，
  - 这会覆盖用户为特殊上游手工指定的 `anthropic-api-key` 或其他兼容配置。
- 处理结果：
  - 已增加手动修改标记，仅在用户尚未手工调整认证头时才自动推荐默认值。

### 3. 快速开始页可能生成重复的 `/v1/v1` 示例地址

- 文件：`frontend/src/views/user/QuickStart.vue`
- 问题说明：
  - 若站点配置中的 `api_base_url` 已包含 `/v1`，OpenAI/OpenClaw OpenAI 示例继续拼接 `/v1` 会生成错误地址。
- 处理结果：
  - 已对页面使用的基础地址做归一化，分别生成带 `/v1` 与不带 `/v1` 的示例值。

## 残余风险与建议

1. 当前上游透传采用白名单策略。如果后续遇到要求私有 header 的第三方网关，仍需按实际网关补充白名单。
2. 本次完成了源码调研、静态校验和实现修复，但还没有引入自动化的 OpenClaw 端到端回归测试；建议后续补一组最小联调用例。
3. `openclaw/` 为本次调研新增源码目录，后续推送到 GitHub 前可按你的仓库策略决定保留、转为子模块，或只保留文档结论。
