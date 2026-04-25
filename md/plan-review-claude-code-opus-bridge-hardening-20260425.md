# Claude Code Opus Bridge Hardening Plan Review

## 评审结论

当前方案方向基本正确，但还不适合直接进入实施。

主要原因不是问题判断错了，而是几个关键修复点还没有收敛到“可直接编码”的粒度，尤其是：

- 高风险工具约束准备怎么做，缺少明确拦截点
- `_prepare_responses_request_body()` 在本方案里的实际收益被高估
- “桥接问题”与“Claude Code 本地执行器问题”的分界实验还不够具体
- 自动化测试与回滚策略不足

建议先修订为 Plan v2，再进入编码。

## 主要问题

### 1. 高风险工具收敛策略没有落到明确实现边界

严重级别：高

问题：

- 方案在 `md/plan-claude-code-opus-bridge-hardening-20260425.md:93-95` 提到要对 `Agent` / `EnterWorktree` / `TaskCreate` / `TaskUpdate` 做更严格约束，但没有说明约束发生在“请求侧工具暴露”“提示词侧行为引导”还是“响应侧 tool_use 裁剪/串行化”。
- 当前实现里真正存在的约束只有请求侧 `parallel_tool_calls=false`，而且它只基于工具名单判断，见 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:2973)。
- 这类约束并不能直接阻止模型选择 `Agent` / `EnterWorktree`，只能影响并发倾向。

影响：

- 方案最关键的目标“减少不必要的 Agent / Worktree 创建”目前还没有可执行设计。
- 如果直接编码，极大概率会变成多轮试错，而不是按方案落地。

建议：

- 在 Plan v2 中明确一条主策略和一条兜底策略。
- 推荐主策略：alias 级请求侧收敛，按 `claude-opus-4-6` 单独改写桥接请求。
- 推荐兜底策略：响应侧检测到同轮多个高风险 `function_call` 时，只允许一个进入 Anthropic `tool_use` 输出，其余记录日志并中止该轮。
- 同时明确不会全局影响所有 Anthropic 请求。

### 2. 方案高估了统一走 `_prepare_responses_request_body()` 的修复价值

严重级别：高

问题：

- 方案在 `md/plan-claude-code-opus-bridge-hardening-20260425.md:88-91` 把“统一走 `_prepare_responses_request_body()`”作为核心修复项。
- 但当前 Anthropic 桥接路径已经在 `_convert_anthropic_request_to_responses()` 中自行构建了 `input`、`tools`、`tool_choice`、`store` 和 `parallel_tool_calls`，见 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:1547)。
- `_prepare_responses_request_body()` 里真正额外有价值的逻辑，主要是 Responses 原生请求标准化，以及对“模型名包含 `codex`”的特殊裁剪，见 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:3001)。
- 当前桥接 alias 的上游模型是 `gpt-5.4`，不是包含 `codex` 的模型名，所以这里的 Codex 专项逻辑不会自然生效。

影响：

- 如果把“复用 `_prepare_responses_request_body()`”当作主修复动作，实际收益可能很小。
- 容易造成修复后行为变化不明显，但时间已经花在结构性重用上。

建议：

- 不要把“复用现有 helper”当成目标本身。
- 在 Plan v2 中把这里拆成两个动作：
- 动作 1：补齐 Anthropic bridge 自己缺失的标准化字段。
- 动作 2：新增一个仅供 Anthropic->Responses 桥接使用的 hardening helper，不混入 Codex CLI 的兼容逻辑。
- 只在需要复用的地方复用，不要为了统一入口而统一。

### 3. 已识别“本地执行器问题”风险，但缺少可证伪的对照实验

严重级别：中

问题：

- 方案在 `md/plan-claude-code-opus-bridge-hardening-20260425.md:61-67` 已经正确提出“问题不全在协议层”的假设。
- 但 To-Do `3-8` 仍然是笼统的联调与日志分析，缺少最小复现实验矩阵。
- 当前已知现象里，原生 Claude 也会出现 `Sibling tool call errored`，而 `worktree` 报错更像 Claude Code 本地执行阶段问题，这意味着必须先拆分“桥接放大了问题”与“桥接制造了问题”。

影响：

- 如果没有标准对照矩阵，日志再多也很难形成可下结论的证据。
- 方案容易在协议层和本地执行器之间来回摇摆。

建议：

- 在 Plan v2 增加固定实验矩阵，至少覆盖：
- 同一 prompt 下：原生 Claude vs 桥接模型
- 同一模型下：只给基础工具 vs 给高风险工具全集
- 同一模型下：stream 模式 vs non-stream 模式
- 同一模型下：只读场景 vs 会触发 worktree 的场景
- 每组实验固定采集：工具序列、同轮 tool 数、stop_reason、错误类型、后端 request_id、Claude Code 本地错误。

### 4. 测试方案还不够“回归保护”导向

严重级别：中

问题：

- 方案在 `md/plan-claude-code-opus-bridge-hardening-20260425.md:97-100` 提到补回归测试，但没有区分“自动化单测”和“联调脚本”。
- 现有 [backend/test_anthropic_responses_bridge.py](/Volumes/project/modelInvocationSystem/backend/test_anthropic_responses_bridge.py:1) 更像联调脚本，不是稳定 CI 测试：它有固定 API Key，只覆盖文本、单工具、图片三类场景，也不直接断言多高风险工具和复杂 SSE 边界。
- 当前共享桥接核心在 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:5085) 和 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:5952)，如果只补脚本，无法很好保护事件转换逻辑。

影响：

- 修复后仍然可能在 `tool_use` 开闭合、`input_json_delta` 拼接、`stop_reason` 判断上回归。
- 大量验证工作仍要依赖人工观察 Claude Code 会话。

建议：

- Plan v2 明确新增单测文件，例如：
- `backend/app/test/test_anthropic_responses_bridge_conversion.py`
- `backend/app/test/test_anthropic_responses_bridge_streaming.py`
- 单测直接覆盖：
- `_convert_anthropic_request_to_responses()`
- `_convert_responses_response_to_anthropic()`
- 多个 `function_call` 的 SSE 顺序、闭合和 `stop_reason`
- 联调脚本保留，但只作为人工验收，不作为主要回归保护。

### 5. 缺少灰度与回滚方案

严重级别：中

问题：

- 方案在 `md/plan-claude-code-opus-bridge-hardening-20260425.md:117-121` 识别了兼容性风险，但没有给出灰度范围和回滚机制。
- 当前 Anthropic->Responses 走的是共享桥接实现，见 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:5101) 和 [backend/app/services/proxy_service.py](/Volumes/project/modelInvocationSystem/backend/app/services/proxy_service.py:5959)。

影响：

- 一旦事件流转换或 tool 约束逻辑有副作用，回退成本高。

建议：

- 先把 hardening 绑定到 `requested_model == "claude-opus-4-6"`。
- 最好补一个可配置开关，允许快速关闭 alias 专项约束。
- 验证通过后再考虑是否推广到其他 Anthropic->Responses alias。

## 四维度评估

### 1. 方案完整性

评价：7/10

优点：

- 已覆盖用户诉求、现状、假设、技术方向、风险和 To-Do。
- 对现有代码的怀疑点判断基本准确。

不足：

- 关键修复点缺少文件/方法级设计。
- 缺少实验矩阵、灰度、回滚和决策门。

### 2. 技术选型

评价：7/10

优点：

- 以 Anthropic->Responses 请求标准化、SSE 事件兼容、工具并发收敛为核心方向是合理的。
- 把 `reasoning.effort=high` 视为行为放大器，而不是唯一根因，这个判断是稳妥的。

不足：

- “统一复用 `_prepare_responses_request_body()`”不是充分技术方案。
- 需要把“标准化”“行为约束”“事件流修复”拆成独立改动面。

### 3. 实施可行性

评价：8/10

结论：

- 方案可实施，且现有代码结构允许在 `proxy_service.py` 内集中落地。
- 但前提是先补足 Plan v2，把约束点和验证矩阵写清楚，否则实施阶段会反复返工。

前置条件：

- 本地 MySQL、后端服务、Claude CLI、Claude Code 会话日志都能稳定访问。
- 能拿到至少一组可重复触发问题的 prompt 和会话样本。

### 4. 潜在风险

评价：风险中高

主要风险：

- 错把 Claude Code 本地执行器缺陷当成桥接协议缺陷。
- 对高风险工具约束过强，导致任务完成率下降。
- 修改 SSE 转换后影响 Anthropic 客户端兼容。
- 没有灰度开关时，线上问题难以快速止损。

## Plan v2 修改建议

建议把原方案修订为以下结构后再实施：

1. 新增“实施边界”章节，明确本次 hardening 只作用于 `claude-opus-4-6`。
2. 新增“策略分层”章节，拆成：
   - 请求标准化
   - alias 行为约束
   - SSE 事件转换修复
3. 新增“最小复现实验矩阵”章节，固定 4 组对照实验和采集字段。
4. 新增“测试设计”章节，区分单测、联调脚本、人工验收。
5. 新增“灰度与回滚”章节，定义开关、观察指标、回退条件。
6. 把 To-Do 细化到方法级，至少列出：
   - `ProxyService._convert_anthropic_request_to_responses`
   - `ProxyService._stream_anthropic_via_responses_request`
   - `ProxyService._non_stream_anthropic_via_responses_request`
   - 新增的 bridge hardening helper

## 最终建议

可以进入 Plan v2 修订，不建议直接开始编码。

如果按当前版本直接实施，最可能发生的问题不是“做不出来”，而是“做了一轮后仍然无法证明到底修复了哪一层问题”。
