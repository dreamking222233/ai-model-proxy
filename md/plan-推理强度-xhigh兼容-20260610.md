# 推理强度-xhigh兼容 Plan

## 用户原始需求

当前项目是模型中转站，接受用户请求后转发给上游渠道。部分上游渠道不支持 `xhigh` 思考强度，会返回：

```text
Upstream returned HTTP 400: {"error":{"message":"level \"xhigh\" not supported, valid levels: low, medium, high","type":"invalid_request_error"}}
```

需要在处理用户请求时，把请求体中关于 `xhigh` 都转为 `high`，无论是 OpenAI 协议还是 Anthropic 协议。

## 技术方案设计

在后端代理核心 `ProxyService` 中新增请求体归一化能力：

- 仅处理推理强度字段：`reasoning_effort`、`reasoning.effort`、`thinking.effort`。
- 将这些字段中大小写归一后等于 `xhigh` 的内容改为 `high`。
- 用户消息正文、工具参数、metadata 等非推理强度字段保持原样。
- 在 OpenAI Chat、OpenAI Responses、Responses WebSocket、Anthropic Messages 的入口或上游准备阶段调用。
- Anthropic 转 Responses 桥接逻辑继续走现有 `reasoning.effort` 推导，但其输入和输出都会被归一化，避免显式字段或映射默认值带出 `xhigh`。

## 涉及文件清单

- `backend/app/services/proxy_service.py`
  - 新增 `xhigh` 到 `high` 的推理强度字段归一化方法。
  - 在 OpenAI/Responses/Anthropic 转发链路调用。
- `backend/test_reasoning_effort_normalization.py`
  - 新增覆盖 OpenAI、Responses、Anthropic、Anthropic->Responses 桥接、映射默认值的单元测试。
- `md/impl-推理强度-xhigh兼容-20260610.md`
  - 实施完成后记录变更与验证。

## 实施步骤概要

1. 梳理代理链路中请求体进入上游前的处理点。
2. 新增推理强度字段归一化方法，确保不破坏原始输入对象。
3. OpenAI Chat 请求进入处理时归一化。
4. Responses HTTP 和 WebSocket 请求归一化。
5. Anthropic Messages 请求进入处理时归一化。
6. Responses 请求体准备阶段兜底归一化，覆盖桥接和默认映射。
7. 增加单元测试覆盖关键协议和转换路径。
8. 运行相关 pytest 验证。
9. 创建 impl 文档并执行自行 review。
