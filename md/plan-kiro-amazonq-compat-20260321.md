# Kiro AmazonQ Compatibility Fix Plan

## 用户原始需求

当前中转在调用 claude 模型的时候，请求上游渠道 `43.156.153.12-kiro` 有时会报错：

`Upstream returned HTTP 500: {"error":{"message":"HTTP 400 from AmazonQ: {\"message\":\"Improperly formed request.\",\"reason\":null}","type":"api_error"},"type":"error"}`

参考文档：`/Users/dream/Downloads/amazon_q_error_analysis.md`

要求：修复当前系统，确保不会再因为这类 Amazon Q / Kiro 请求格式问题导致调用失败。

## 技术方案设计

### 问题判断

当前 `backend/app/services/proxy_service.py` 对 `chat/completions` 请求基本采用直接透传模式。  
实测发现 `43.156.153.12:8080` 这类 Kiro / Amazon Q Claude 渠道能接受顶层 `tools`，但会在历史消息里出现新版 OpenAI 工具调用结构时失败：

- `assistant.tool_calls`
- `tool` 角色消息

该类请求会稳定触发上游：

`HTTP 400 from AmazonQ: {"message":"Improperly formed request.","reason":null}`

### 修复思路

1. 为 Kiro / AmazonQ 类 Claude 渠道增加专用请求兼容层
2. 保持当前渠道不变，不走后备渠道
3. 仅重写历史工具调用 transcript，将新版 OpenAI 工具消息等价转换为该上游可接受的旧版结构
4. 保留顶层 `tools` / `tool_choice` 能力，避免把当前渠道功能整体降级

### 兼容策略

- 识别 Kiro / AmazonQ 渠道：基于 `channel.name`、`channel.base_url`、`channel.description`、错误文本等特征
- 渠道识别：
  - 基于 `channel.name`、`channel.base_url`、`channel.description`
  - 兼容显式 `kiro` / `amazonq` 标识
  - 对 `43.156.153.12` 上的 Claude 模型也启用兼容逻辑
- OpenAI 请求：
  - 将 `assistant.tool_calls` 转为旧版 `assistant.function_call`
  - 将 `tool` 角色消息转为旧版 `function` 角色消息
  - 为 `function` / `tool` 内容做字符串化，兼容 JSON 结果和富文本数组
  - 顶层 `tools` 保持不变，确保模型仍可返回 `tool_calls`

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `md/impl-kiro-amazonq-compat-20260321.md`

如需补充验证脚本或测试，再按实际修改增加文件。

## 实施步骤概要

1. 梳理 Claude 请求在 OpenAI 转发路径的进入点
2. 复现当前渠道的 AmazonQ 400
3. 识别失败模式是否集中在新版工具调用历史消息
4. 在当前渠道发送前做等价结构转换
5. 验证转换后的请求可以在同一上游返回 200
6. 产出 impl 文档
7. 执行自审并根据结果修正
