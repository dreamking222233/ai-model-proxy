# Codex Responses 兼容修复方案

## 用户原始需求

当前本地项目是一个反代平台，已有 `/v1/responses` 接口，但 Codex CLI 配置当前项目反代服务后，请求会报错：

```text
Unexpected status 502 Bad Gateway: Unknown error, url: http://localhost:8085/v1/responses
```

需要深度参考 `https://github.com/router-for-me/CLIProxyAPI` 项目中 `v1/responses` 的处理方式，修复当前本地中转系统的 `v1/responses` 接口问题，使 Codex CLI 可以正常使用。

## 技术方案设计

### 问题判断

当前系统只实现了：

- `POST /v1/responses`
- `POST /responses`

但 Codex CLI 对 `v1/responses` 的核心使用方式并不只是普通 HTTP POST，还会通过 `GET /v1/responses` 发起 websocket 升级，并通过 websocket 文本帧发送：

- `response.create`
- `response.append`

当前本地服务缺少 websocket 入口，因此 Codex CLI 在建立连接时直接失败，外层表现为 502。

### 参考 CLIProxyAPI 的兼容点

参考 CLIProxyAPI，`v1/responses` 需要兼容两条链路：

1. `POST /v1/responses`
   - 标准 Responses API HTTP 接口
   - 流式时返回 SSE

2. `GET /v1/responses`
   - 用于 Codex CLI 的 websocket 接口
   - 接收 `response.create` / `response.append`
   - 将多轮上下文合并后继续请求上游
   - 将上游结果以 `response.*` JSON 文本帧写回客户端

### 本地实施思路

不直接照搬 CLIProxyAPI 的全量实现，而是按当前项目架构做最小必要兼容：

1. 为 `openai_proxy.py` 增加 `GET /v1/responses` websocket 路由
2. 为 websocket 路由补 API Key 鉴权能力
3. 在 `ProxyService` 中增加 websocket 会话处理逻辑
4. 统一 Responses 请求规范化逻辑：
   - 首次 `response.create` 要求有 `model`
   - 后续 `response.create` / `response.append` 复用上次 `model` / `instructions`
   - 维护 `last_request_input`
   - 维护 `last_response_output`
   - 将追加输入和上一轮 assistant 输出合并，转换成上游 `chat/completions`
5. 统一生成符合 Codex 预期的 `response.*` 事件
   - `response.created`
   - `response.output_item.added`
   - `response.content_part.added`
   - `response.output_text.delta`
   - `response.output_text.done`
   - `response.content_part.done`
   - `response.output_item.done`
   - `response.completed`
   - `error`
6. `response.completed` 中补齐 `response.output`，用于后续多轮请求拼装
7. 保持现有 `POST /v1/responses` SSE 接口可用，并复用同一套事件数据结构

### 风险点

- 现有项目没有 websocket 代码，需要保证不影响已有 HTTP 接口
- 当前仓库工作区存在未提交修改，变更时不能覆盖用户已有改动
- Codex CLI 的请求模式依赖多轮上下文拼接，若 `response.completed` 结构不完整，会导致后续轮次异常

## 涉及文件清单

- `backend/app/api/proxy/openai_proxy.py`
- `backend/app/services/proxy_service.py`
- `backend/app/core/dependencies.py`
- `md/plan-codex-responses-compatibility-20260319.md`
- `md/impl-codex-responses-compatibility-20260319.md`

## 实施步骤概要

1. 分析当前 `/v1/responses` 路由与服务实现
2. 对照 CLIProxyAPI 提炼 websocket 兼容要点
3. 增加 websocket API Key 鉴权入口
4. 增加 `GET /v1/responses` websocket 路由
5. 抽取并统一 Responses 事件构建逻辑
6. 实现 websocket 请求归一化与多轮状态管理
7. 复用现有渠道选择与计费逻辑打通上游调用
8. 校验 Python 语法与关键路径
9. 记录实现结果到 impl 文档
