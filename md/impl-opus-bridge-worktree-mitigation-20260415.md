# Opus Bridge Worktree Mitigation Impl

日期：2026-04-15

## 任务概述

针对 `claude-opus-4-6 -> GPT-5.4 / responses` 桥接链路，在不修改客户端的前提下，增加一层服务端缓解策略：

- 识别高风险工具请求
- 对高风险工具请求强制关闭 `parallel_tool_calls`
- 补充服务端日志，方便复测时观察是否命中缓解逻辑

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `md/plan-opus-bridge-worktree-mitigation-20260415.md`
- `md/impl-opus-bridge-worktree-mitigation-20260415.md`
- `md/plan-opus-gpt54-bridge-optimization-20260415.md`

## 核心代码说明

### 1. 新增高风险工具名单

在 `ProxyService` 中新增 `_RESPONSES_HIGH_RISK_TOOL_NAMES`，当前包含：

- `Agent`
- `EnterWorktree`
- `TaskCreate`
- `TaskUpdate`
- `TaskGet`
- `TaskList`

### 2. 新增工具提取与识别方法

新增方法：

- `_extract_responses_tool_names(request_data)`
- `_detect_responses_high_risk_tools(request_data)`

用途：

- 从 `/responses` 风格请求体中提取工具名
- 判断是否命中高风险工具

### 3. 对高风险工具请求禁用并行工具调用

修改范围：

- 原生 `/responses` 请求准备逻辑
- `Anthropic -> Responses` bridge 转换逻辑

处理方式：

- 新增统一缓解方法 `_apply_responses_parallel_tool_mitigation(...)`
- 若命中高风险工具，则强制写入：
  - `parallel_tool_calls = false`
- 若未命中，则保持原有默认：
  - `parallel_tool_calls = true`

### 4. 增加命中缓解策略日志

新增日志：

- `Responses request mitigation enabled: model=... parallel_tool_calls=false risky_tools=...`

用途：

- 用户再次用 Claude Code 复测时，可直接在后端日志中确认是否命中了缓解策略

## 测试验证

已执行：

```bash
python -m py_compile backend/app/services/proxy_service.py
```

结果：

- 通过

待进一步验证：

- 使用 Claude Code 再次以 `claude-opus-4-6` 发起包含 `Agent` / `Explore` 的请求
- 观察是否出现新的缓解日志
- 对比第一轮与第二轮是否仍出现明显的多 `Agent` 并发放大

## 当前结论

本次修改属于“低风险缓解修复”，不能直接消除客户端本地 Git/worktree 锁冲突，但能够减少 bridge 向客户端一次性放大并行工具调用的概率，是当前最小改动下最直接可验证的一步。
