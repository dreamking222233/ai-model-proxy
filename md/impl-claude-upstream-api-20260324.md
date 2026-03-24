## 任务概述

将 `43.156.153.12-Claude` 渠道从 OpenAI 上游转发方式切换为 Claude Messages API，并补上 OpenAI 客户端访问该渠道时的协议转换，避免客户端仍走 `/chat/completions` 直连上游。

## 文件变更清单

1. `backend/app/services/proxy_service.py`
2. `sql/init.sql`
3. `sql/upgrade_claude_channel_to_anthropic_20260324.sql`
4. `md/plan-claude-upstream-api-20260324.md`

## 核心代码说明

### 1. OpenAI 请求转 Anthropic 上游

在 `ProxyService` 中新增以下能力：

1. OpenAI 请求体转 Anthropic Messages API 请求体
2. Anthropic 非流式响应转 OpenAI chat completions 响应
3. Anthropic SSE 流转 OpenAI SSE chunk
4. 工具调用、`system/developer` 消息、`thinking` 内容的基础映射

处理策略：

1. 只有当目标渠道 `channel.protocol_type == "anthropic"` 时，`handle_openai_request` 才走新的转换分支
2. 现有 Anthropic 客户端入口 `/v1/messages` 不做额外兼容性改写，继续按原始 Claude 请求透传
3. 计费、日志、失败重试逻辑沿用原有主流程

### 2. 43.156 Claude 渠道默认协议切换

更新了 `sql/init.sql` 中的预置渠道：

1. `43.156.153.12-Claude` 的 `protocol_type` 从 `openai` 改为 `anthropic`
2. 保持 `base_url` 为 `http://43.156.153.12:8080/v1`
3. 上游实际目标路径因此会变成 `http://43.156.153.12:8080/v1/messages`

### 3. 现网升级脚本

新增 `sql/upgrade_claude_channel_to_anthropic_20260324.sql`：

1. 将已有数据库中的渠道 `id=9 / name=43.156.153.12-Claude` 修正为 `protocol_type=anthropic`
2. 显式设置 `auth_header_type=x-api-key`
3. 保留验证查询，方便执行后核对结果

## 测试验证

已完成：

1. `python -m py_compile backend/app/services/proxy_service.py`
2. 最小功能自检：直接调用新增转换方法，验证 OpenAI 请求可以转换为 Anthropic 请求结构
3. 最小功能自检：验证 Anthropic 响应可以转换回 OpenAI 响应结构
4. 最小功能自检：验证“Anthropic 非流式请求但上游强制返回 SSE”时，回拼后的响应仍保留 `thinking`、`tool_use`、`text`
5. 定向检查：确认 `sql/init.sql` 中 `43.156.153.12-Claude` 默认协议已改为 `anthropic`

未完成：

1. 未对真实上游 `http://43.156.153.12:8080/v1/messages` 发起联调请求
2. 未跑完整端到端自动化测试

## 当前结论

本次改造后：

1. `43.156.153.12-Claude` 在渠道元数据和健康检查层面会被识别为 Anthropic 渠道
2. OpenAI 客户端访问命中该渠道时，不再强行请求上游 `/chat/completions`，而是转成 Claude API `/messages`
3. Anthropic 客户端访问该渠道时，继续保持原始 Claude 请求直通，不引入额外参数改写
