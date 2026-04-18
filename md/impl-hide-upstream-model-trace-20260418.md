## 任务概述

本次处理聚焦“模型映射留痕”问题。系统仍然保留 `admin/models` 配置的渠道模型映射能力，并继续在内部把用户请求模型映射为真实上游模型；但对外返回给客户端的响应体、SSE 事件以及用户侧调用记录不再暴露映射后的上游模型名。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/api/user/profile.py`
- `backend/app/test/test_proxy_model_alias_rewrite.py`
- `md/plan-hide-upstream-model-trace-20260418.md`

## 核心代码说明

### 1. 代理层新增对外模型别名改写

在 `ProxyService` 中新增：

- `_rewrite_openai_payload_model`
- `_rewrite_anthropic_payload_model`

这两个方法只用于“返回给客户端”的 payload 改写，把上游返回中的 `model` 字段统一还原为用户原始请求的 `requested_model`，不会改变真实发往上游的内部请求体。

### 2. 覆盖了所有容易泄露的对外响应链路

已处理的链路包括：

- OpenAI 原生协议流式 SSE
- OpenAI 原生协议非流式 JSON
- OpenAI 请求桥接到 Anthropic 上游时的流式 SSE
- OpenAI 请求桥接到 Anthropic 上游时的非流式 JSON
- Anthropic 原生协议流式 SSE
- Anthropic 原生协议非流式 JSON（含 prompt cache / 会话压缩路径）

结果是：

- 内部仍然会把 `request_data["model"]` 改成映射后的上游模型名用于真实转发
- 但返回给用户 SDK / 客户端日志里的 `model` 字段改回用户请求模型名

### 3. 用户侧调用记录不再返回 `actual_model`

`/api/user/profile/usage-logs` 现在会在返回前把每条记录的 `actual_model` 置空，避免用户通过调用记录接口直接看到映射后的真实上游模型名。

管理员侧请求日志仍保留 `actual_model`，用于系统内部排障。

## 测试验证

已完成：

- `python -m py_compile backend/app/services/proxy_service.py backend/app/api/user/profile.py backend/app/test/test_proxy_model_alias_rewrite.py`
- `python -m unittest app.test.test_proxy_model_alias_rewrite`

说明：

- 单元测试验证了 OpenAI payload、Anthropic `message_start` payload、Anthropic `message` payload 的模型字段改写行为
- 测试运行时出现 Redis 初始化失败告警，但不影响本次纯函数测试结果，测试最终通过
