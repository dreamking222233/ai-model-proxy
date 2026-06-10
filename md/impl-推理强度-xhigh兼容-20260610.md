# 推理强度-xhigh兼容 Impl

## 任务概述

针对部分上游渠道不支持 `xhigh` 思考强度的问题，在代理转发前统一把推理强度字段中的 `xhigh` 降级为 `high`，覆盖 OpenAI Chat Completions、OpenAI Responses、Responses WebSocket、Anthropic Messages 以及 Anthropic 转 Responses 桥接链路。

## 文件变更清单

- `backend/app/services/proxy_service.py`
  - 新增 `_normalize_unsupported_reasoning_level` 和 `_normalize_request_reasoning_levels`，处理 `reasoning_effort`、`reasoning.effort`、`thinking.effort`。
  - 新增 `_downgrade_unsupported_reasoning_effort`，用于 reasoning effort 推导结果降级。
  - OpenAI/Anthropic channel 准备函数返回归一化后的请求副本。
  - Responses HTTP 和 WebSocket 入口先归一化用户请求。
  - OpenAI Chat 和 Anthropic Messages 入口先归一化用户请求。
  - `_prepare_responses_request_body` 兜底归一化，覆盖直接 Responses、websocket、桥接以及映射默认值。
  - `_apply_responses_mapping_default_reasoning_effort` 将映射默认 `xhigh` 写出为 `high`。
  - `_resolve_anthropic_bridge_reasoning_effort` 对显式和默认 `xhigh` 返回 `high`。
- `backend/test_reasoning_effort_normalization.py`
  - 新增单元测试覆盖推理强度字段归一化、OpenAI、Anthropic、Responses、Responses WebSocket、映射默认值和 Anthropic->Responses 桥接。
- `md/plan-推理强度-xhigh兼容-20260610.md`
  - 记录实施方案。

## 核心代码说明

归一化逻辑按推理强度字段处理：

- `reasoning_effort` 去空白并转小写后等于 `xhigh`，替换为 `high`。
- `reasoning.effort` 去空白并转小写后等于 `xhigh`，替换为 `high`。
- `thinking.effort` 去空白并转小写后等于 `xhigh`，替换为 `high`。
- 用户消息正文、工具参数、metadata 等非推理强度字段保持原样。
- 方法返回新对象，不原地修改调用方传入的原始请求体。

执行位置采用入口和上游准备双层兜底：

- 入口归一化保证日志、计费预检、缓存 key 和实际上游请求一致。
- 上游准备归一化保证协议桥接、websocket 和后续新增转发路径不容易漏掉。
- Responses 可转发推理强度枚举保持为 `minimal/low/medium/high`，`xhigh` 作为输入兼容别名归一化为 `high`。

## 测试验证

已执行：

```bash
pytest -q backend/test_reasoning_effort_normalization.py backend/test_proxy_retry_error_sanitization.py backend/test_image_proxy_optimization.py
```

结果：

```text
37 passed, 1 warning in 0.54s
```

警告为现有 Pydantic v2 class-based config deprecation，不属于本次变更。
