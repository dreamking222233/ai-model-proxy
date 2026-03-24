## 用户原始需求

当前的上游渠道 `43.156.153.12-Claude` 现在按 OpenAI 协议请求上游，希望优化为使用 Claude API，请求地址为 `http://43.156.153.12:8080/v1/messages`。

## 技术方案设计

### 目标

1. 将 `43.156.153.12-Claude` 渠道的上游协议切换为 Anthropic / Claude Messages API。
2. 不影响现有客户端调用我方 OpenAI 接口的兼容性。
3. 让初始化数据和升级脚本都落到新协议，避免新部署或老库升级后再次回到 OpenAI 协议。

### 方案

1. 保留现有 `/v1/messages` -> Anthropic 上游直通逻辑。
2. 在 `ProxyService.handle_openai_request` 分支中，针对 `channel.protocol_type == "anthropic"` 的渠道，增加 OpenAI 请求到 Anthropic 上游的协议转换：
   - OpenAI `messages/system/tools/tool_choice/max_tokens/...` 转成 Anthropic Messages API 结构。
   - Anthropic 非流式响应转回 OpenAI Chat Completions 响应。
   - Anthropic SSE 流式事件转回 OpenAI SSE chunk。
3. 将 `sql/init.sql` 中 `43.156.153.12-Claude` 渠道默认协议改为 `anthropic`。
4. 新增升级 SQL，修正现有数据库中该渠道的 `protocol_type/auth_header_type/base_url`。

### 风险点

1. OpenAI 与 Anthropic 的工具调用数据结构不同，需要显式转换。
2. OpenAI 流式 chunk 与 Anthropic SSE 事件结构不同，需要自行桥接并保持计费统计不变。
3. 不能影响当前已经修好的“不要改写原始 Claude 请求参数”的约束，因此只在 OpenAI 客户端转 Anthropic 上游时做协议层转换，不对 Anthropic 客户端请求做兼容性改写。

## 涉及文件清单

1. `backend/app/services/proxy_service.py`
2. `sql/init.sql`
3. `sql/add_thinking_models_20260321.sql`
4. `sql/upgrade_claude_channel_to_anthropic_20260324.sql`

## 实施步骤概要

1. 在代理层增加 OpenAI -> Anthropic 请求转换与响应转换辅助方法。
2. 在 OpenAI 请求处理流程里，按渠道 `protocol_type` 选择 OpenAI 上游直连或 Anthropic 上游转换。
3. 更新初始化 SQL 中 `43.156.153.12-Claude` 渠道默认协议。
4. 补充升级 SQL 修正线上已有渠道配置。
5. 运行语法校验和定向 grep，确认 `43.156` 渠道默认协议已经变成 Anthropic，且 OpenAI 入口对 Anthropic 渠道有明确处理分支。
