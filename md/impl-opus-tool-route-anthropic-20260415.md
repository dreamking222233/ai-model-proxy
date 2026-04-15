# Opus Tool Route To Anthropic Impl

日期：2026-04-15

## 任务概述

为 `claude-opus-4-6` 增加“工具请求优先改走真实 Anthropic 渠道”的路由能力：

- 当 Anthropic 请求中携带 `tools`
- 且请求模型为 `claude-opus-4-6`
- 则优先路由到 `claude-sonnet-4-5` 的真实 Anthropic passthrough 渠道
- 若没有可用真实 Anthropic 渠道，则继续回退到原本的 `gpt-5.4 / responses` bridge

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `md/plan-opus-tool-route-anthropic-20260415.md`
- `md/impl-opus-tool-route-anthropic-20260415.md`

## 核心代码说明

### 1. 新增工具请求改路由映射

在 `ProxyService` 中新增：

- `_ANTHROPIC_TOOL_ROUTE_MODEL_MAP`

当前配置：

- `claude-opus-4-6 -> claude-sonnet-4-5`

### 2. 新增 Anthropic 工具请求判断

新增：

- `_has_anthropic_tools(request_data)`

用于判断当前 Anthropic 请求是否存在顶层 `tools` 定义。

### 3. 新增真实 Anthropic passthrough 渠道筛选

新增：

- `_resolve_anthropic_passthrough_channels_for_model(...)`

作用：

- 解析目标模型
- 读取其渠道映射
- 只保留真实 `anthropic_messages` 渠道

### 4. 新增工具请求优先改路由逻辑

新增：

- `_select_tool_routed_anthropic_channels(...)`

作用：

- 若请求为 `claude-opus-4-6` 且存在工具定义
- 则尝试切换到 `claude-sonnet-4-5`
- 若该模型存在真实 Anthropic passthrough 渠道，则返回新的路由结果
- 否则回退默认渠道集合

### 5. 在 Anthropic 入口中接入改路由

在 `handle_anthropic_request(...)` 中新增：

- 读取默认模型与默认渠道后
- 先尝试进行工具请求改路由
- 命中后替换 `channels` 和 `unified_model`
- 输出日志：
  - `Anthropic tool request rerouted: requested_model=... route_model=...`

### 6. 保留已有 bridge 缓解逻辑

此前已做的：

- `/responses` 请求命中高风险工具时强制 `parallel_tool_calls=false`

本次未移除，继续保留为 fallback bridge 的第二层防护。

## 测试验证

已执行：

```bash
python -m py_compile backend/app/services/proxy_service.py
```

结果：

- 通过

待复测关注日志：

- `Anthropic tool request rerouted: requested_model=claude-opus-4-6 route_model=claude-sonnet-4-5`
- 若命中该日志，则说明工具请求已不再优先进入 `gpt-5.4 / responses`

## 当前结论

现在的修复策略已升级为两层：

1. 优先把 `opus4.6` 的工具请求改路由到真实 Anthropic `sonnet4.5`
2. 若未能命中真实 Anthropic passthrough，再回退到 `gpt-5.4 / responses` bridge，并继续套用 `parallel_tool_calls=false` 缓解
