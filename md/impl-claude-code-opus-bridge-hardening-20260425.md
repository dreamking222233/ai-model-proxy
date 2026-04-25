# Claude Code Opus Bridge Hardening Impl

## 任务概述

本次任务针对 `claude-opus-4-6 -> 43.156.153.12-codex转claude -> responses:gpt-5.4` 这条桥接通道做 Claude Code 兼容性修复，目标是在不削弱工具能力的前提下，让 bridge 模型在 Claude Code 中尽量接近原生 Claude 的工具调用行为。

重点解决的问题：

- 容易在 plan/explore 场景下直接输出多个 `Agent(isolation=worktree)` 工具调用
- 进而触发 `Failed to create worktree: could not lock config file .git/config: File exists`
- 伴随出现 `Sibling tool call errored`
- 早期轮次还会出现无效 `Read.pages=""`、错误 `Grep.path` 参数等工具参数偏差

## 文件变更清单

- `backend/app/services/proxy_service.py`
- `backend/app/test/test_anthropic_bridge_claude_code_guidance.py`
- `md/plan-claude-code-opus-bridge-hardening-20260425.md`
- `md/plan-review-claude-code-opus-bridge-hardening-20260425.md`

## 核心实现

### 1. 去掉 bridge alias 的强制高推理

移除了 `claude-opus-4-6` 在 `Anthropic -> Responses` 转换时被强制注入 `reasoning.effort=high` 的逻辑。

原因：

- Anthropic Messages 请求本身并没有表达“强制高推理”
- 该额外注入会放大 gpt-5.4 的过度规划倾向
- 在 Claude Code 中更容易诱发 plan mode + 多 agent + worktree 路线

### 2. 为 Claude Code bridge 请求注入兼容指导

新增桥接 guidance，用于让上游 gpt-5.4 更贴近 Claude Code 原生工具行为。

指导内容包括：

- 先用 `Read/Glob/Grep/Bash` 做仓库探索
- 并行探索优先使用 `Agent(run_in_background=true)`
- 只读分析避免 `worktree` 隔离
- 不要多次同时发起 `worktree` 型 agent
- `Read` 不传空 `pages`
- 不要凭空假设 `~/.claude/projects/.../memory` 路径存在

### 3. 统一 Anthropic bridge 路径的 Responses 标准化

让 `_stream_anthropic_via_responses_request()` 和 `_non_stream_anthropic_via_responses_request()` 统一调用 `_prepare_responses_request_body()`。

收益：

- 不再让 bridge 路径绕过通用 Responses 预处理
- 输入规范化、默认字段与后续兼容处理保持一致

### 4. 增加 Claude Code 工具参数归一化

新增 bridge 工具参数归一化逻辑：

- `Read`:
  - 删除空 `pages`
- `Grep`:
  - 若把 `*.py` 这类通配符错误塞进 `path`，自动拆分为
    - `path=/.../dir`
    - `glob=*.py`
- `Agent`:
  - 只读探索场景下，将
    - `run_in_background=false` 纠正为 `true`
    - `isolation=worktree` 去掉

这些修正不减少工具集合，只把 gpt-5.4 生成的偏差参数拉回到 Claude Code 能稳定执行的语义。

### 5. 对部分工具采用“延迟 delta、一次性发最终参数”

对 bridge 下的 `Agent` / `Read` / `Grep` 工具，流式阶段先缓存参数，不立即把原始 delta 推给 Claude Code，等最终参数就绪后再发一份归一化后的 `input_json_delta`。

原因：

- 如果一边流式发原始错误参数，一边在结尾再改，会让客户端拿到拼接后的坏 JSON
- 延迟到最终一次性发出，才能保证客户端只看到正确参数

## 测试与验证

### 自动化测试

执行：

```bash
env PYTHONPATH=/Volumes/project/modelInvocationSystem/backend \
  /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python \
  -m pytest /Volumes/project/modelInvocationSystem/backend/app/test/test_anthropic_bridge_claude_code_guidance.py -q

env PYTHONPATH=/Volumes/project/modelInvocationSystem/backend \
  /Volumes/environment/Python/anaconda3/envs/ai-invoke-service/bin/python \
  -m pytest /Volumes/project/modelInvocationSystem/backend/app/test/test_proxy_model_alias_rewrite.py -q
```

结果：

- `test_anthropic_bridge_claude_code_guidance.py`: `5 passed`
- `test_proxy_model_alias_rewrite.py`: `7 passed`

### Claude Code 实测

#### 修复前失败样本

- 会话 `57f36346-ffbe-457d-9e92-1158dab0d7b3`
- 典型问题：
  - 同轮 3 个 `Agent(... isolation=worktree ...)`
  - `Failed to create worktree`
  - `Sibling tool call errored`

#### 修复后稳定样本

- 会话 `1cf403b4-fdd6-4bd5-878a-cb8f71f2669b`
- 检查规则：
  - `tool_use_error`
  - `Invalid pages parameter`
  - `Failed to create worktree`
  - `Sibling tool call errored`
  - `File does not exist`
  - `Path does not exist`

结果：

- 上述错误标记计数为 `0`

观测到的工具行为：

- 首轮不再误读虚构 memory 文件
- 进入计划/分析阶段后优先使用 `TodoWrite`、`Glob`、`Grep`、`Read`、`Bash`
- 未再触发导致 `.git/config.lock` 冲突的多 `worktree` agent 路径

## 结论

本轮修复没有通过黑名单禁用工具，而是通过：

- 去除不忠实的高推理注入
- 增加 Claude Code 行为指导
- 对 bridge 下的工具参数做语义归一化
- 统一 Responses 预处理链路

把 `claude-opus-4-6` 在 Claude Code 中的行为从“容易直接炸到 worktree 冲突”拉回到“能稳定走正常仓库探索工具链”的状态。

## 残留说明

- Claude Code 本地会话仍然可能因为模型本身策略不同而选择不同的探索路径，但桥接层已不再稳定地产生那类最致命的错误模式
- 当前未修改渠道、模型或数据库结构，只做了桥接层和测试层修正
