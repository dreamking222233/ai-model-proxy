# Opus Bridge Worktree Mitigation Plan

日期：2026-04-15

## 用户原始需求

根据已知日志与问题现象，分析并修复 `claude-opus-4-6 -> GPT-5.4 / responses` 桥接渠道下，Claude Code 在调用工具和子代理时更容易出现：

- `.git/config` 锁冲突
- worktree 隔离启动失败
- `Sibling tool call errored`

目标是在不影响现有主流程的前提下，降低 bridge 场景下多 `Agent` 并发放大本地 Git/worktree 冲突的概率。

## 技术方案设计

### 根因收敛

从日志可确认：

1. `claude-opus-4-6` 实际不是直连 Anthropic，而是通过 `Anthropic Messages -> OpenAI Responses -> Anthropic` bridge。
2. 同类请求在该 bridge 中会生成多个 `Agent` 工具调用。
3. Claude Code 客户端在 worktree 隔离模式下执行多个 `Agent` 时，更容易撞 `.git/config` 锁。
4. 第一轮失败后改为非 worktree 模式，子代理就能正常执行，说明主要故障点在客户端本地并发 worktree，而不是 bridge 上游连通性。

### 修复策略

采用最小风险修复：

1. 在 `/responses` 请求准备阶段识别“高风险工具型请求”。
2. 对这类请求禁用 `parallel_tool_calls`，强制串行工具调用。
3. 增补调试日志，明确记录：
   - 是否命中高风险工具
   - 是否禁用了并行工具调用
   - 命中的风险工具名称

### 判定范围

高风险工具先聚焦以下名称：

- `Agent`
- `EnterWorktree`
- `TaskCreate`
- `TaskUpdate`
- `TaskGet`
- `TaskList`

这些工具均与子代理调度、任务拆分或 worktree 进入强相关。

### 为什么先不做更大改动

本次先不做：

- 直接改渠道路由策略
- 强制 `opus4.6` 走真实 Anthropic
- bridge 失败时自动回退其它模型
- 客户端层面的 worktree 策略修改

原因：

- 这些改动影响面更大
- 当前已有明确的低风险切入点：限制 bridge 并行工具调用

## 涉及文件清单

- `backend/app/services/proxy_service.py`
- `md/plan-opus-bridge-worktree-mitigation-20260415.md`
- `md/impl-opus-bridge-worktree-mitigation-20260415.md`

## 实施步骤概要

1. 在 `proxy_service.py` 中增加高风险工具识别辅助逻辑。
2. 在 `Responses` 请求准备逻辑中，对高风险工具型请求改写 `parallel_tool_calls=false`。
3. 增加桥接调试日志，输出风险工具命中情况与并行开关结果。
4. 进行静态检查与最小验证。
5. 补充实施记录文档。
