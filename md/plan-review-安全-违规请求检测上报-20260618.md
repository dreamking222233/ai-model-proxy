# 安全-违规请求检测上报 Plan 评估

## 评估结论

当前方案总体方向可行，技术路线与现有系统架构基本匹配：代理层统一接入、独立风控表保存短期快照、复用现有系统配置、管理端新增审计页面，这些设计是合理的。

但该任务已经属于大型任务，且会触达代理主链路、流式转发、计费记录、敏感数据留存和管理端权限。当前 Plan 不建议直接进入编码，需要修订为 v2 后再实施。核心原因是：主链路失败降级策略、敏感内容访问审计、流式输出检测边界、事务隔离和请求覆盖范围还不够明确。

建议结论：**Plan 需要修订后通过**。

## 1. 方案完整性

### 已覆盖内容

- 覆盖了 OpenAI Chat、OpenAI Responses、Anthropic、图片、视频等主要代理入口。
- 明确了“短期快照 + 风险事件”两张独立表，避免污染普通 `request_log`。
- 明确了无风险请求短期保存、过期清理；风险请求延长保留。
- 说明了输入侧检测、模型提示词兜底、输出侧检测、管理端查看的完整闭环。
- 列出了后端、前端、SQL、定时任务和测试验证清单。

### 需要补充的问题

1. **缺少 Responses WebSocket 链路覆盖**

   现有 `ProxyService` 中存在 `handle_responses_websocket`，当前 Plan 只明确了 `handle_responses_request`，但 WebSocket 也是用户请求入口。若不接入，会留下绕过路径。

   建议补充：
   - `handle_responses_websocket` 创建 snapshot。
   - 每个 turn 的输入检测、模型提示注入和输出检测策略。
   - WebSocket 中风险事件与 turn `request_id` 的绑定规则。

2. **管理端页面设计提到统计，但 API 未定义统计接口**

   前端页面能力中有“待处理、高风险、今日风险、已清理快照数量”，但管理端 API 只定义了 `/events`、详情、review 和 purge。

   建议新增：
   - `GET /api/admin/security/stats`
   - 返回 `open_count`、`high_count`、`today_count`、`purged_snapshot_count` 等字段。

3. **缺少敏感请求体查看的审计记录**

   管理员详情页可以查看完整请求体，这是高敏操作。当前方案只限制平台管理员可见，但没有记录“谁在什么时候查看了哪条敏感请求”。

   建议补充：
   - 管理员查看事件详情时写入 `operation_log`。
   - 操作类型如 `security_risk_event_view`、`security_snapshot_view`。
   - 记录 `event_id`、`snapshot_id`、管理员 ID、IP。

4. **缺少快照失败时的主链路策略**

   当前方案要求每次请求先创建 snapshot，但没有说明风控数据库写入失败时请求是放行、阻断还是降级。

   建议明确：
   - `security_snapshot_enabled=false` 时不创建快照。
   - 风控服务异常时默认 fail-open 还是 fail-closed，需要配置项控制。
   - 建议新增 `security_fail_closed_enabled`，默认 `false`，避免风控表或清理任务异常导致全站代理不可用。

5. **缺少敏感字段脱敏和大小限制细节**

   完整请求体可能包含 API key、图片 base64、文件内容、用户隐私。Plan 只写了 `request_preview` 脱敏，未明确 `request_body_json` 是否脱敏。

   建议补充：
   - 入库前移除或掩码 `Authorization`、`api_key`、`key`、`token`、`password` 等字段。
   - 图片编辑、base64、文件字段只保存摘要和尺寸，不保存完整二进制。
   - 新增 `security_snapshot_max_body_bytes`，超过后截断并记录 `truncated=1`。
   - 表字段增加 `is_truncated`、`body_size_bytes`。

6. **缺少索引和查询性能细节**

   风险事件列表会按时间、状态、风险等级、分类、用户查询。当前字段说明里只有部分 index。

   建议补充组合索引：
   - `security_risk_event(status, created_at)`
   - `security_risk_event(risk_level, created_at)`
   - `security_risk_event(category, created_at)`
   - `security_risk_event(user_id, created_at)`
   - `security_request_snapshot(retention_status, expires_at)`

## 2. 技术选型

### 合理部分

- 第一版使用本地规则，不引入额外模型审核调用，符合当前成本和延迟约束。
- 不让模型直接调用后端上报接口是正确的。当前系统是代理转发，不是工具调用编排框架，模型“主动上报 HTTP”不可靠。
- 复用 `_inject_model_identity` 的提示词注入点合理，避免在 OpenAI、Anthropic、Responses 中复制多套注入逻辑。
- 使用 `ServiceException` 做业务阻断符合项目现有异常规范。

### 需要调整的技术点

1. **模型固定标记只能作为弱信号**

   `[MIS_RISK_REPORT ...]` 可以用于辅助捕获模型拒绝，但不能作为强证据。用户也可以在 prompt 中伪造该标记，模型也可能照抄。

   建议：
   - 输入侧规则命中才作为主要阻断依据。
   - 模型标记只作为 `event_source=model_report` 的风险信号。
   - 输出侧捕获标记后仍应结合上下文、输出内容或输入快照记录 matched rule。

2. **流式输出检测不宜第一版强制中断**

   现有 `ProxyService` 有多条 SSE generator 路径，OpenAI、Anthropic、Responses、兼容流、重试流都有各自处理。强制中断容易破坏 SSE 协议、计费统计和缓存逻辑。

   建议第一版范围改为：
   - 流式仅捕获并清洗 `[MIS_RISK_REPORT ...]`。
   - 记录高风险片段，但不主动终止已有流。
   - “流式中途替换为拒绝文案”放到第二阶段。

3. **安全提示词需要控制长度和注入位置**

   现有身份提示词已经会增加上下文，继续追加安全提示可能影响成本和模型行为。

   建议：
   - 安全提示词保持短文本。
   - 与身份提示词拼接时使用明确分隔。
   - 配置项 `security_model_prompt_enabled=false` 时完全不注入。
   - Responses 的 `instructions`、Anthropic 顶层 `system`、OpenAI `messages[0].system` 要保持现有格式兼容。

4. **规则来源需要结构化**

   `md/违禁词筛选-破限黄色-20260618.md` 是说明文档，不适合作为运行时规则源。

   建议：
   - 在 `security_detection_service.py` 内先定义结构化规则常量。
   - 后续如需运营配置，再拆到数据库或 JSON 配置。
   - 不在运行时读取 `md/` 文档。

## 3. 实施可行性

整体可实施，但建议拆成两阶段，否则一次性改动过大。

### 建议第一阶段

目标：先完成输入侧阻断、短期快照、管理端审计、过期清理。

范围：
1. SQL、ORM、系统配置。
2. `SecurityDetectionService`：文本提取、规则扫描、快照、事件、清理。
3. 代理入口输入侧检测：OpenAI Chat、Anthropic、Responses、图片、视频、Responses WebSocket。
4. 高风险输入请求阻断，抛出 `ServiceException(403, security_block_message, "SECURITY_RISK_BLOCKED")`。
5. 管理端事件列表、详情、审核、手动清理、统计。
6. 定时清理过期 snapshot。

### 建议第二阶段

目标：模型提示词兜底和输出侧检测。

范围：
1. 安全提示词注入。
2. 非流式输出检测。
3. 流式风险标记捕获和清洗。
4. 根据实际效果再评估是否做流式中途阻断。

### 实施注意点

- 快照写入和普通请求日志、计费扣费应尽量解耦，避免风控写入异常影响已成功的上游请求结算。
- 创建 snapshot 后要立即 `commit` 或使用独立 session，否则后续释放连接、流式 generator、异步重试路径可能拿不到稳定的 snapshot。
- 风险事件记录也建议独立事务，避免与上游调用、日志落库互相回滚。
- `request_id` 应继续使用现有 `ProxyService` 生成的 UUID，不能由前端传入。
- 管理端详情查询必须只允许 `require_admin`，代理和普通用户不能访问。

## 4. 潜在风险

1. **隐私与合规风险高**

   保存完整请求体会保存大量敏感内容。必须有 TTL、脱敏、查看审计、管理员权限控制和最大体积限制。

2. **误杀风险**

   黄色、破解、安全研究类词汇存在大量正常语境。单关键词直接阻断容易误伤医学、法律、安全防护、CTF、靶场、代码审计等请求。

   建议：
   - 高风险单词只保留极少数明确非法词。
   - 大部分词走组合规则。
   - 中风险默认 `review/allow`，不直接阻断。

3. **主链路稳定性风险**

   代理服务已经承担渠道路由、重试、计费、缓存、流式输出。新增每次请求 DB 写入和扫描会增加延迟与失败面。

   建议：
   - 快照和检测代码必须轻量。
   - 规则扫描限制最大文本长度。
   - 风控异常需要有明确降级配置。

4. **流式检测协议风险**

   SSE chunk 可能跨片段包含 JSON 字符串、模型文本、工具调用字段。简单字符串替换可能破坏 JSON 或漏检。

   建议第一版只在已解析文本 delta 层处理，不直接改原始字节流。

5. **存储膨胀风险**

   每次请求保存完整 JSON，图片和多轮上下文会快速扩大表体积。

   建议：
   - 增加最大保存体积。
   - base64/文件字段不保存原文。
   - 清理任务支持 limit，并记录清理数量。
   - 给 purge 接口加保护，避免一次性全表扫描。

6. **安全提示词被绕过或泄露风险**

   提示词只能提升模型拒绝概率，不能替代后端规则。不要把内部策略、分类、后台机制写得过细，以免成为规避提示。

## 必须修改建议

1. Plan v2 中补充 `handle_responses_websocket` 的检测和上报链路。
2. 补充风控写入失败时的降级策略，建议新增 `security_fail_closed_enabled`。
3. 补充请求体脱敏、最大体积、base64/文件字段处理规则，并在表中增加 `is_truncated`、`body_size_bytes`。
4. 补充管理员查看完整请求体的操作审计。
5. 补充管理端统计 API。
6. 将流式输出“强制终止/替换拒绝文案”调整为第二阶段增强。
7. 明确第一阶段先做输入侧检测和审计闭环，第二阶段再做提示词和输出侧检测。
8. 补充组合索引设计，避免管理端列表查询慢。

## 可选优化建议

1. `security_risk_event` 可增加 `snapshot_db_id` bigint，保留 `snapshot_id` 字符串给外部展示，数据库关联更高效。
2. `risk_categories_json`、`matched_rules_json` 如继续使用 MySQL，可考虑 JSON 类型；若保持兼容 SQLite 测试，则继续 Text。
3. `request_preview` 建议统一限制 500-1000 字。
4. `extracted_text` 可只保存输入文本，不保存系统提示词，避免把内部 prompt 长期留存。
5. 测试清单中增加“风控关闭配置”“快照失败降级”“超大请求截断”“管理员详情查看审计”。

## 最终评估

方案架构合理，技术上可以落地，但当前版本仍缺少几个关键工程边界。建议先按上述必须修改项修订为 Plan v2，通过后再编码。实施时建议分两阶段推进，先保证输入侧检测、快照留存、后台审计和清理策略稳定，再逐步加入模型提示词和输出侧检测。
