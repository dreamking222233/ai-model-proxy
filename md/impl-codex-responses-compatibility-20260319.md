# Codex Responses 兼容修复实施记录

## 任务概述

本次修复针对本地中转系统的 `v1/responses` 接口与 Codex CLI 不兼容问题。

核心问题是当前系统只有 `POST /v1/responses`，缺少 Codex CLI 实际使用的 `GET /v1/responses` websocket 入口；同时原有 Responses 逻辑并未真正转发到上游 `/responses`，而是转换成 `/chat/completions`，这会破坏 Codex 多轮上下文和事件语义。

本次实现将 Responses 接口改为以原生 `/responses` 为主，并补齐 websocket 多轮兼容。

## 文件变更清单

- `backend/app/core/dependencies.py`
- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/services/proxy_service.py`
- `md/plan-codex-responses-compatibility-20260319.md`
- `md/impl-codex-responses-compatibility-20260319.md`
- `md/review-codex-responses-compatibility-20260319.md`

本次联调过程中还修正了本机 Codex CLI 的运行配置：

- `~/.codex/config.toml`
- `~/.codex/config.json`
- `~/.codex/auth.json`
- `~/.bash_profile`
- `/opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js`

## 核心代码说明

### 1. 增加 websocket 鉴权能力

在 `dependencies.py` 中抽取了基于 header 值的 API Key 校验逻辑：

- 新增 `_extract_api_key_value`
- 新增 `verify_api_key_from_headers`
- 原有 `verify_api_key(Request, db)` 改为复用该公共逻辑

这样 HTTP 与 websocket 可以共用同一套 API Key 校验规则。

### 2. 增加 `GET /v1/responses` websocket 路由

在 `openai_proxy.py` 中新增：

- `@router.websocket("/v1/responses")`
- `@router.websocket("/responses")`

并增加 `_handle_codex_responses_websocket` 公共入口：

- 先从 websocket headers 校验 API Key
- 鉴权通过后 `accept()`
- 将连接交给 `ProxyService.handle_responses_websocket`

### 3. Responses HTTP 请求改为原生转发上游 `/responses`

在 `proxy_service.py` 中，`handle_responses_request` 改为：

- 解析并保留客户端 Responses 请求结构
- 继续使用现有模型解析、渠道优先级、故障转移与计费逻辑
- 每个候选渠道都转发到 `${base_url}/responses`
- 流式时返回原生 `response.*` SSE
- 非流式时解析上游返回体，产出标准 Responses JSON

### 4. 新增 Codex websocket 多轮状态管理

新增 `handle_responses_websocket` 处理下游 websocket 会话：

- 维护 `last_request`
- 维护 `last_response_output`
- 识别并处理 `response.create`
- 识别并处理 `response.append`
- 将多轮上下文合并为新的 Responses 请求后再发往上游

合并策略参考 CLIProxyAPI：

- 首轮 `response.create` 直接作为起始请求
- 后续请求把 `last_request.input + last_response_output + next_input` 合并
- 自动继承 `model`
- 自动继承 `instructions`
- 删除 `previous_response_id`

### 5. 增加 websocket 预热空轮次支持

新增 `_build_responses_prewarm_payloads`：

- 当首个 `response.create` 带 `generate=false` 时
- 本地直接回写一组空的 `response.created` / `response.completed`
- 不访问上游

### 6. 增加 Codex 请求兼容清洗

新增 `_prepare_responses_request_body`，对 Codex 模型做兼容处理：

- 统一把 `input` 规范成 item 数组
- 默认补 `store=false`
- 默认补 `parallel_tool_calls=true`
- Codex 模型默认补 `include=["reasoning.encrypted_content"]`
- 对 Codex 模型移除常见不兼容字段：
  - `max_output_tokens`
  - `max_completion_tokens`
  - `temperature`
  - `top_p`
  - `truncation`
  - `user`
  - `context_management`
- 将 `system` role 转成 `developer`

### 7. 增加 Responses 事件解析与回写

新增一组辅助方法：

- `_iter_responses_upstream_payloads`
- `_parse_responses_payload_line`
- `_parse_non_stream_responses_payload`
- `_parse_non_stream_responses_body`
- `_payload_to_sse`
- `_extract_responses_usage`
- `_extract_responses_output`
- `_build_responses_error_payload`
- `_rewrite_response_model`

作用：

- 从上游 SSE 中解析 `response.*` JSON
- websocket 下直接回写 JSON 文本帧
- HTTP 下重新包装为标准 SSE
- 从 `response.completed` 中提取 `usage`
- 从 `response.completed.response.output` 中提取 assistant 输出，供下一轮上下文拼接
- 将上游实际模型名重写为客户端请求模型名

## 测试验证

已完成：

- `python -m py_compile backend/app/core/dependencies.py backend/app/api/proxy/openai_proxy.py backend/app/services/proxy_service.py`
- 纯本地 helper 验证脚本：
  - 校验 `response.create` 归一化
  - 校验 `response.append` 多轮拼接
  - 校验 SSE 非流式解析
  - 校验 Codex 字段清洗与 `system -> developer`

结果：

- 语法检查通过
- 本地 helper 验证通过
- 真实 `codex exec "hello"` 已成功返回文本结果

### 最终联调结论

真实联调后确认，最初 `Codex CLI -> 本地 relay` 不通并不只是一处问题，而是两层问题叠加：

1. 代码侧确实缺少完整的 `/v1/responses` 兼容实现
2. 本机 Codex CLI 运行环境也存在两个额外阻塞：
   - 系统代理开启后，Codex CLI 未正确绕过本地 relay，导致请求未到达 `127.0.0.1:8085`
   - `~/.codex/auth.json` 中保存的是错误的 `OPENAI_API_KEY`（`sk-dream`），导致即使请求到达本地 relay，也会返回 `401 Invalid API key`

最终处理如下：

- 保留并验证本次 `/v1/responses` 兼容代码修改
- 将 Codex 生效配置的 `base_url` 统一到 `http://127.0.0.1:8085/v1`
- 将 `~/.codex/auth.json` 中的 `OPENAI_API_KEY` 同步为本地 relay 实际可用的 API key
- 在 `~/.bash_profile` 中增加：
  - `NO_PROXY=localhost,127.0.0.1,::1`
  - `no_proxy=localhost,127.0.0.1,::1`
- 在 Codex 全局启动器 `/opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js` 中补充本地 relay 代理绕过：
  - 启动时自动合并 `NO_PROXY/no_proxy`
  - 确保即使当前 shell 未显式 `source ~/.bash_profile`，直接运行 `codex` / `codex exec` 也能绕过本机 `7897` 代理访问本地 relay

联调验证结果：

- 在显式 `source ~/.bash_profile` 的 shell 中执行 `codex exec "hello"`，已成功通过本地 relay 返回：
  - `hello, what do you need help with?`
- 在未手工注入环境变量的普通 shell 中直接执行 `codex exec "hello"`，也已成功返回：
  - `hello`
- 交互态 `codex` 已验证会向本地 `POST /v1/responses` 发起正常请求
- 2026-03-19 14:27 直接请求本地 relay：
  - `curl --http1.1 http://127.0.0.1:8085/v1/responses ...`
  - 本地返回 `HTTP/1.1 200 OK`
  - 返回体包含完整 `response.created -> response.completed -> [DONE]` 事件流
  - 后端日志同时确认：
    - `POST /v1/responses -> 200`
    - `POST http://43.156.153.12:8317/v1/responses -> HTTP/1.1 200 OK`

### 与 CLIProxyAPI 的对照结论

对照 `https://github.com/router-for-me/CLIProxyAPI` 后，当前本地 relay 已覆盖 Codex 兼容所需的关键点：

- `POST /v1/responses` 原生转发到上游 `/responses`
- `GET /v1/responses` websocket 入口
- `response.create` / `response.append` 归一化
- `generate=false` 预热空轮次
- SSE `response.*` 事件透传与错误事件兼容
- 将上游返回模型名重写为客户端请求模型名

因此，当前“直连你服务器上的 CLIProxyAPI 正常、走本地系统异常”的差异，已经被收敛到本地 relay 与本机 Codex 运行环境两层，并已完成修复与验证。

未完成：

- 未补自动化测试用例覆盖真实大请求体（Codex 请求体约 43KB）场景

## 待优化项

- 如果后续发现部分非 Codex OpenAI 渠道不支持 `/responses`，可以补一个“原生 `/responses` 失败后回退 `/chat/completions`”的兼容分支
- 可以补正式自动化测试，覆盖 websocket 多轮状态与错误分支
- 如果希望 `codex` 在所有新终端中立即生效，需要用户重新打开终端，或手动执行一次 `source ~/.bash_profile`
