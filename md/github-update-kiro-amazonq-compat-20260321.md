# Kiro AmazonQ 兼容修复更新说明

## 修复背景

在 Claude 模型请求经过 `43.156.153.12` 当前渠道时，部分请求会返回如下错误：

```text
Upstream returned HTTP 500: {"error":{"message":"HTTP 400 from AmazonQ: {\"message\":\"Improperly formed request.\",\"reason\":null}","type":"api_error"},"type":"error"}
```

该问题表现为中转层看到的是 `500`，但根本原因是上游 Amazon Q 兼容层实际返回了 `400`，说明请求结构不符合其兼容要求。

## 根因分析

实测确认：

- 当前 Claude 渠道可以正常接受基础 OpenAI Chat 请求
- 当前 Claude 渠道可以接受顶层 `tools` / `tool_choice`
- 触发报错的关键场景不是顶层工具定义，而是**历史消息里的新版 OpenAI 工具调用 transcript**

具体包括：

- `assistant.tool_calls`
- `tool` 角色消息

这类结构在当前 Kiro / AmazonQ 兼容上游会触发：

```text
HTTP 400 from AmazonQ: {"message":"Improperly formed request.","reason":null}
```

## 修复方案

本次修复没有切换后备渠道，而是直接在**当前渠道**做兼容处理。

### 处理策略

在请求发往当前 Kiro / AmazonQ Claude 渠道之前，对历史工具调用消息做等价转换：

- `assistant.tool_calls` -> `assistant.function_call`
- `tool` -> `function`
- `tool_call_id` -> 反查并补充 `function.name`
- `tool` / `function` 的复杂内容统一转为字符串，兼容：
  - JSON 对象
  - 数组内容
  - 文本片段

### 保留能力

为了避免把当前渠道整体降级，本次修复**没有移除**以下顶层能力：

- `tools`
- `tool_choice`
- `parallel_tool_calls`

也就是说，这次修复的重点是兼容**历史消息结构**，而不是关闭工具调用能力。

## 代码变更

主要修改文件：

- `backend/app/services/proxy_service.py`

新增内容包括：

1. Kiro / AmazonQ Claude 渠道识别逻辑
2. 新版 OpenAI 工具历史消息转旧版结构的兼容函数
3. 在 OpenAI 请求转发前接入该兼容处理

## 修复效果

修复后：

- 同一渠道下，包含新版工具历史消息的 Claude 请求不再因为 AmazonQ 请求格式问题失败
- 顶层 `tools` 能力仍然保留
- GPT / Codex 渠道不会被这次兼容逻辑误伤

## 验证结果

### 语法检查

执行通过：

```bash
python -m py_compile backend/app/services/proxy_service.py backend/app/services/health_service.py
```

### 真实上游验证

已直接对当前上游渠道进行实测：

1. 基础 Claude 请求：`200`
2. 顶层 `tools` 请求：`200`
3. 原始新版工具历史消息：`500`
4. 转换为旧版 `function_call / function` 后：`200`
5. 转换后同时保留顶层 `tools`：`200`

结论：

本次修复已直接命中根因，并在当前渠道验证通过。

## 文档记录

本次修复对应文档：

- `md/plan-kiro-amazonq-compat-20260321.md`
- `md/impl-kiro-amazonq-compat-20260321.md`
- `md/review-kiro-amazonq-compat-20260321.md`

## 后续建议

后续如果继续接入更多 Amazon Q / Kiro 类兼容渠道，建议将“渠道兼容策略”做成显式配置项，而不是长期依赖名称、描述或地址特征判断。
