# Kiro AmazonQ Compatibility Fix Impl

## 任务概述

本次修复针对 Claude 请求经过 `43.156.153.12-kiro` / Amazon Q 兼容上游时，偶发出现：

`HTTP 400 from AmazonQ: {"message":"Improperly formed request.","reason":null}`

经实际探测，问题并不在顶层 `tools` 能力，而在历史消息里的新版 OpenAI 工具调用 transcript：

- `assistant.tool_calls`
- `tool` 角色消息

当前上游可以接受：

- 顶层 `tools`
- 旧版 `assistant.function_call`
- 旧版 `function` 角色消息

因此修复方案是在当前渠道转发前，对历史消息做等价转换，不走后备渠道。

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `md/plan-kiro-amazonq-compat-20260321.md`

## 核心代码说明

### 1. Kiro / AmazonQ 渠道识别

在 `ProxyService` 中新增渠道识别逻辑：

- 优先识别 `kiro` / `amazonq` 关键词
- 兼容识别 `43.156.153.12` 上的 Claude 模型渠道
- 避免误伤同机上的 GPT / Codex 渠道

### 2. 新版工具消息转旧版结构

新增 OpenAI 请求兼容转换：

- `assistant.tool_calls` -> `assistant.function_call`
- `tool` -> `function`
- `tool_call_id` -> 通过前序 `tool_calls.id` 反查函数名并写入 `function.name`
- `tool` / `function` 的复杂内容转为字符串，兼容 JSON 结果与数组内容

这样可以让当前 Kiro / AmazonQ 渠道继续吃到等价上下文，但请求体符合其兼容层要求。

### 3. 仅处理历史 transcript，不降级顶层 tools

顶层：

- `tools`
- `tool_choice`
- `parallel_tool_calls`

保持原样透传。  
实测当前渠道对这些顶层字段可正常响应，问题集中在历史消息结构，因此没有做整体降级。

### 4. 接入 OpenAI 转发入口

在 `handle_openai_request()` 内，映射真实模型名后、发往上游前执行：

- `_prepare_openai_request_for_channel(channel, request_data_copy)`

这样流式和非流式都能共享同一份兼容处理结果。

## 测试验证

### 本地语法验证

执行：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/services/health_service.py
```

结果：通过

### 上游实测

使用当前渠道 `http://43.156.153.12:8080/v1/chat/completions` 实测：

1. 基础请求：`200`
2. 顶层 `tools` / `tool_choice`：`200`
3. 历史消息包含 `assistant.tool_calls + tool`：`500`
4. 将同一历史消息改写为 `assistant.function_call + function`：`200`
5. 改写后同时保留顶层 `tools`：`200`

### 关键结论

根因不是“Claude 当前渠道完全不支持工具”，而是“AmazonQ 兼容层不接受新版 OpenAI 工具历史消息结构”。

## 待优化项

- 如果后续还有其他 Amazon Q 兼容渠道，可以把这套识别逻辑抽成可配置渠道能力，而不是仅基于名称/地址特征判断。
- 如需兼容更多旧式 / 新式函数调用响应差异，可继续补充 response 方向的格式归一化。
