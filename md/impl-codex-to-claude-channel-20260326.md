# Codex To Claude Channel 实施记录

## 任务概述

本次实现把 `claude-opus-4-6` 从“直接映射到 `43.156.153.12-codex`”调整为“挂到独立的 Anthropic 入口渠道”：

- 新渠道：`43.156.153.12-codex转claude`
- 对外协议：`Anthropic`
- 实际上游：`43.156.153.12-codex`
- 实际模型：`gpt-5.4`
- 实际上游接口：`/v1/responses`

同时补了 Claude Code 兼容所需的 Anthropic tool streaming 桥接，使 `tool_use` 不再只在结束时一次性回放。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/services/health_service.py`
- `sql/init.sql`
- `sql/add_codex_channel.sql`
- `sql/add_claude_opus_codex_bridge_20260326.sql`
- `sql/add_codex_to_claude_channel_20260326.sql`
- `md/plan-codex-to-claude-channel-20260326.md`
- `md/impl-codex-to-claude-channel-20260326.md`

## 核心代码说明

### 1. 新增 Anthropic-facing / Responses-backed 渠道方案

沿用现有 `responses:` 映射指令，不新增表结构：

- 渠道协议仍可声明为 `anthropic`
- 模型映射用 `actual_model_name = responses:gpt-5.4`

这样在 Anthropic `/v1/messages` 入口下，仍然可以把实际上游切到 OpenAI Responses。

### 2. `claude-opus-4-6` 切换到新渠道

SQL 层完成了以下变更：

- 新增渠道 `43.156.153.12-codex转claude`
- `claude-opus-4-6` 的 `unified_model.protocol_type` 改为 `anthropic`
- 旧映射 `claude-opus-4-6 -> 43.156.153.12-codex` 置为禁用
- 新映射 `claude-opus-4-6 -> 43.156.153.12-codex转claude -> responses:gpt-5.4` 置为启用
- 增量 SQL 自动复制旧 codex 渠道的 `api_key` 和 `base_url`
- 旧脚本 `sql/add_claude_opus_codex_bridge_20260326.sql` 已同步到最终语义，避免误执行后回退到旧渠道

### 3. Claude Code tool streaming 兼容补强

在 `proxy_service.py` 中补了 Responses -> Anthropic 的函数调用流式桥接：

- 跟踪 `call_id / item_id / id` 的别名关系，避免同一个 tool block 被重复开启
- 处理 `response.output_item.added`
- 处理 `response.function_call_arguments.delta`
- 处理 `response.function_call_arguments.done`
- 将参数增量回放为 Anthropic `input_json_delta`
- 在 `response.completed` 阶段仅做兜底补齐，不重复输出已关闭的 tool block

### 4. health check 兼容修正

`health_service.py` 现在按“实际上游 API”而不是仅按 `channel.protocol_type` 选择 header 语义：

- 如果映射目标是 `responses:*`
- 即使渠道本身是 `anthropic`
- 探活也会按 OpenAI/Responses 方式构造 header

这解决了 `Anthropic` 外观渠道探活 `/responses` 时 header 选错的问题。

### 5. thinking 文本归一化

补了 Responses reasoning 内容的统一提取逻辑，避免 Anthropic thinking 块直接出现 Python 列表字符串。

## 数据库执行结果

已执行：

- `sql/add_codex_to_claude_channel_20260326.sql`

执行后确认：

- 新渠道 ID：`12`
- `43.156.153.12-codex转claude.protocol_type = anthropic`
- 新渠道与旧 `43.156.153.12-codex` 的 `api_key`、`base_url` 一致
- `claude-opus-4-6` 的有效映射已切到新渠道

## 测试验证

已完成：

- `python -m py_compile backend/app/services/proxy_service.py backend/app/services/health_service.py`
- 伪造 Responses 事件流回放测试：
  - 验证 `function_call` 可正确转为单个 Anthropic `tool_use` block
  - 验证 `response.function_call_arguments.delta` 可正确回放为 `input_json_delta`
  - 验证最终 `stop_reason = tool_use`
- 本地数据库迁移验证：
  - 验证 `claude-opus-4-6` 新旧映射启停状态
  - 验证新渠道与旧 codex 渠道共享同一上游 key / base_url
- 本地后端重启验证：
  - 8085 端口已重启
  - `GET /health` 返回 `{"status":"ok"}`

## 当前状态

- 后端已按新代码重启
- `claude-opus-4-6` 已挂到 `43.156.153.12-codex转claude`
- 对外协议已改为 `Anthropic`
- 实际调用仍为 `gpt-5.4 /responses`

## 剩余风险

- 这次补齐了 Claude Code 需要的基础 tool streaming 序列，但未完整模拟所有 Anthropic thinking signature 细节
- 若后续还要对齐更复杂的 Claude Code 行为，建议补正式自动化回归测试，覆盖多 tool、多轮 tool_result、reasoning 混合输出
