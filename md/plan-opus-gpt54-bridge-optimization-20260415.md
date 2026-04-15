# Opus 4.6 转 GPT-5.4 渠道优化记录

日期：2026-04-15

## 背景

当前系统中，`claude-opus-4-6` 存在一条桥接渠道：

- 用户请求入口：`/v1/messages`
- 当前统一模型：`claude-opus-4-6`
- 当前渠道：`43.156.153.12-codex转claude`
- 当前上游实际目标：`responses:gpt-5.4`

即当前并非原生 Anthropic Opus 直连，而是通过 Anthropic Messages 协议请求，转换后发送到 OpenAI Responses 风格上游，再转换回 Anthropic SSE/响应格式返回给 Claude Code。

## 本轮排查结论

### 1. 本系统后端本身未执行 `git rev-parse`

本轮检查中，后端代理代码未发现直接调用本地 Git 命令的逻辑。`HEAD` 相关报错不属于本系统代理层直接触发。

### 2. Claude Code 子代理失败的直接原因是本地 worktree 并发创建冲突

Claude Code 实际报错中已出现：

`Failed to create worktree: ... could not lock config file .git/config: File exists`

这说明在多子代理并行初始化时，本地仓库 worktree 创建过程发生了 Git 配置锁冲突。随后同批工具调用被归并为：

`Sibling tool call errored`

因此：

- `Sibling tool call errored` 不是首因
- 首因是 worktree 创建失败
- `Failed to resolve base branch "HEAD"` 很可能是 worktree 创建/初始化失败后的派生错误

### 3. `claude-opus-4-6` 桥接链路确实会触发多子代理并发

实时日志中已捕获到：

- 请求模型：`claude-opus-4-6`
- 请求工具包含：`Agent`、`TaskCreate`、`Bash`、`Read`、`Edit`、`WebSearch` 等
- 后端已将该请求分发到 `gpt-5.4 / responses`
- 上游返回中一次生成多个工具调用，包含多个 `Agent`

这与 Claude Code 界面中同时启动多个分析/探索子代理的现象一致。

## 当前桥接实现中的主要风险点

### 风险点 1：默认允许并行工具调用

代码位置：

- `backend/app/services/proxy_service.py`
- `_prepare_responses_request_body(...)`

当前逻辑：

- `prepared.setdefault("parallel_tool_calls", True)`

风险：

- 对 Claude Code 场景，这会放大 `Agent` 并发启动
- 多个子代理同时进入本地 worktree 创建流程，更容易撞 `.git/config` 锁
- 容易导致 `Sibling tool call errored`

### 风险点 2：Opus 请求统一桥接到 GPT-5.4，不区分重工具场景

当前 `claude-opus-4-6` 已配置为桥接到 `responses:gpt-5.4`。

风险：

- 普通文本问答问题不大
- 但 Claude Code 属于重工具、多轮、强工作区依赖场景
- 这类场景对协议语义、工具链行为、会话连续性要求更高
- 使用 bridge 替代真实 Anthropic Opus，兼容风险更大

### 风险点 3：流式完成态对 `response.completed` 依赖较强

当前桥接流式处理里，如果上游流提前结束且未收到 `response.completed`，可能记录：

- `stream closed before response.completed`

风险：

- 某些情况下其实上游已返回足够多的工具事件或正文
- 但系统仍按错误处理，影响稳定性统计和用户感知

### 风险点 4：Anthropic -> Responses 的语义映射存在损耗

当前桥接中：

- Anthropic `thinking` 输入块不会完整保留到 Responses 输入
- 工具选择策略只做基础转换
- Anthropic 特有的上下文/工具语义，在 bridge 上无法完全等价

风险：

- 对普通聊天影响有限
- 对 Claude Code 这种工具型工作流影响更明显

### 风险点 5：当前渠道选择策略过于静态

当前渠道排序主要基于：

- 映射可用
- 渠道启用
- 健康状态
- 优先级

但未区分：

- 请求是否包含 `Agent`
- 工具数量是否过多
- 是否为高风险桥接请求
- 最近是否频繁出现 worktree / stream 异常

## 建议优化项

## 一级优先级

### 优化 1：对桥接请求禁用并行工具调用

建议：

- 对 `claude-opus-4-6 -> gpt-5.4 / responses` 强制写入 `parallel_tool_calls = false`
- 或者只要检测到工具集中包含 `Agent`、`EnterWorktree`、`TaskCreate` 等高风险工具，就自动改为串行

预期收益：

- 显著降低并发 worktree 创建概率
- 降低 `Sibling tool call errored`
- 降低 `.git/config` 锁冲突

### 优化 2：对重工具请求不要优先走 bridge

建议：

- 对 Claude Code 场景中的重工具请求优先走真实 Anthropic 渠道
- bridge 仅作为普通问答或轻工具场景的备选渠道

建议判定条件可包括：

- `tools_count` 超过阈值
- 工具名中包含 `Agent`
- 工具名中包含 `EnterWorktree`
- 请求中出现明显的代码分析/子代理场景

预期收益：

- 降低协议语义失真
- 降低工具链不稳定
- 降低复杂会话场景的异常率

### 优化 3：增强 bridge 调试日志

建议新增记录：

- 是否开启并行工具调用
- 请求工具总数
- 是否包含 `Agent`
- 实际生成的 tool call 数
- 是否出现 worktree 风险工具
- 是否发生提前断流
- 是否收到 `response.completed`

预期收益：

- 可更快判断是本地 Git/worktree 问题、桥接语义问题，还是上游响应问题

## 二级优先级

### 优化 4：提高 `response.completed` 缺失时的容错能力

建议：

- 若已收到完整的工具调用闭合事件，允许合成一个桥接完成态
- 对“已有有效输出但末尾缺完成事件”的情况做降级处理，而非直接记为失败

预期收益：

- 降低 `stream closed before response.completed`
- 提升桥接稳定性

### 优化 5：做桥接专用的健康和路由策略

建议：

- 为 bridge 渠道增加独立成功率统计
- 针对包含高风险工具的请求降低该渠道优先级
- 对近期频繁异常的 bridge 渠道缩短熔断恢复窗口或增加保护

预期收益：

- 渠道选择更智能
- 降低高风险请求误入 bridge 的概率

## 三级优先级

### 优化 6：探索上游会话态能力

当前上游会话策略仍为 `stateless`。

建议：

- 若 `43.156.153.12:8317` 支持等价的 Responses 会话续传能力，则考虑引入真正的会话态复用
- 减少每轮完整历史重放

预期收益：

- 降低 token 消耗
- 降低延迟
- 降低长会话漂移和桥接误差

## 推荐实施顺序

建议先做最小风险、最高收益的三项：

1. 对 bridge 强制 `parallel_tool_calls = false`
2. 对包含 `Agent` / `EnterWorktree` 的请求降低或禁止走 bridge
3. 补充 bridge 专用调试日志

第二阶段再做：

4. `response.completed` 缺失容错
5. 渠道路由优化

第三阶段再评估：

6. 上游会话态复用

## 本轮测试观察记录

本轮已确认：

- `claude-opus-4-6` 请求会通过本系统进入 `gpt-5.4 / responses`
- `claude-sonnet-4-5`、`claude-haiku-4-5` 目前主要仍走 Anthropic passthrough
- `claude-opus-4-6` 这条桥接链路总体可用，但稳定性弱于直通 Anthropic
- 近期请求日志中已经出现过 `stream closed before response.completed`

## 2026-04-15 对比测试补充记录

### 测试 1：`claude-sonnet-4-5`

用户输入：

- `深度分析当前目录下的项目 可以开启多个agent和Explore 代理进行分析`

后端观测结果：

- 请求入口仍为 `POST /v1/messages?beta=true`
- 请求协议为原生 Anthropic Messages
- 头部包含：
  - `anthropic-version: 2023-06-01`
  - `anthropic-beta: claude-code-20250219,...`
- 首轮请求中：
  - `requested_model=claude-sonnet-4-5`
  - `tools_count=28`
  - 工具中已包含 `Agent`、`TaskOutput`、`ExitPlanMode`、`Read`、`Edit`、`Write`、`WebSearch`
- 实际分发：
  - `upstream_api=anthropic_messages`
  - `upstream_model=claude-sonnet-4.5`
  - 渠道：`43.156.153.12-Claude`
- 流式结果：
  - 多轮返回 `tool_use`
  - 存在文本后再返回 `tool_use`
  - 整体表现为原生 passthrough

本轮未在后端日志中看到：

- `git rev-parse`
- `HEAD`
- worktree 创建失败

说明：

- 对 `claude-sonnet-4-5` 而言，中转层目前未显式暴露异常
- 即使请求中包含 `Agent` 工具，后端侧仍然表现为稳定的原生 Anthropic passthrough

### 测试 2：`claude-opus-4-6`

用户输入：

- `深度分析当前目录下的项目 可以开启多个agent和Explore 代理进行分析`

后端观测结果：

- 请求入口同样为 `POST /v1/messages?beta=true`
- 首轮请求中：
  - `requested_model=claude-opus-4-6`
  - `tools_count=28`
  - 工具中同样包含 `Agent`
- 但实际分发已切换为 bridge：
  - `upstream_model=gpt-5.4`
  - `upstream_api=responses`
  - 渠道：`43.156.153.12-codex转claude`
  - 上游命中：`http://43.156.153.12:8317/v1/responses`
- 请求缓存格式也从 `anthropic_messages` 变为 `responses`

流式事件观测到的关键现象：

1. 首轮桥接返回 `TaskCreate`
2. 第二轮桥接返回 `TaskUpdate`
3. 后续轮次出现：
   - 先输出文本
   - 再连续输出 4 个 `Agent` 工具调用

后端桥接调试中已明确看到：

- `anthropic_via_responses`
- `response.output_item.added:function_call`
- 多个 `response.function_call_arguments.done`
- 最终在 Anthropic 侧被回写成多个 `content_block_start:tool_use:Agent`

说明：

- `opus4.6 -> GPT-5.4` 这条桥接链路不仅会触发工具调用
- 而且确实会在单轮中生成多个 `Agent`
- 这正是本地 worktree 并发冲突的高风险触发条件

### 本轮对比结论

#### `claude-sonnet-4-5`

- 原生 Anthropic passthrough
- 请求中可带 `Agent`
- 但从后端日志看，当前未直接放大为 bridge 风格的多代理并发工具链异常

#### `claude-opus-4-6`

- 实际为 Anthropic -> Responses -> Anthropic bridge
- 同样的 Claude Code 请求，在 bridge 中明确观察到：
  - `TaskCreate`
  - `TaskUpdate`
  - 单轮 4 个 `Agent`

因此本轮对比进一步支持以下判断：

- `opus4.6` 问题核心不在 `/v1/messages` 入口本身
- 而在于其后续被桥接到 `gpt-5.4 / responses`
- 该 bridge 更容易把 Claude Code 请求放大成多 `Agent` 并发工具调用
- 多 `Agent` 并发工具调用又会提升本地 worktree 冲突概率

### 测试 3：`claude-opus-4-6` 第一轮失败、第二轮恢复

用户侧现象：

- 同一条 `opus4.6` 会话中，第一轮子代理/Explore 初始启动时报错
- 随后 Claude Code 提示改用非 worktree 模式
- 第二轮开始，子代理出现真实的 `tool uses` 和 `tokens`

后端对应观测：

#### 第一阶段

时间段：

- 约 `2026-04-15 13:02:09` 到 `13:02:26`

表现：

- `claude-opus-4-6` 请求进入 bridge
- 首轮工具输出主要是：
  - `TaskCreate`
  - `TaskUpdate`
- 这一阶段后端没有看到上游 HTTP 错误
- 也没有看到 bridge 侧 `response.completed` 缺失

推断：

- 第一阶段失败点并不在本系统后端与上游 `gpt-5.4 / responses` 的通信
- 更可能发生在 Claude Code 客户端本地执行 `Agent/Explore` 时的 worktree 创建阶段
- 因此界面中会出现：
  - `0 tool uses`
  - `.git/config` 锁冲突
  - `Sibling tool call errored`

#### 第二阶段

时间段：

- 约 `2026-04-15 13:02:43` 到 `13:03:05`

表现：

- 在非 worktree 模式下，bridge 返回了更完整的工具链行为
- 后端明确捕获到：
  - 先输出文本
  - 再输出 `Read`
  - 再连续输出 4 个 `Agent`
- 后续 bridge 继续产出多轮正常响应

推断：

- 切换为非 worktree 模式后，本地 Git 锁冲突路径被绕开
- 同一条 `opus4.6 -> GPT-5.4` bridge 又恢复到可以实际调起子代理和工具
- 因此第二轮界面中会出现真实的：
  - `tool uses`
  - `tokens`

#### 本阶段结论

- “第一轮报错、第二轮恢复”与后端 bridge 自身故障不完全等价
- 更像是：
  1. bridge 首先产出任务/子代理规划
  2. 客户端尝试按 worktree 模式执行
  3. 本地 Git 锁冲突导致子代理实际执行失败
  4. 切换为非 worktree 模式后重新执行
  5. 子代理开始真正消耗 tokens 和 tools

- 这进一步说明当前 `opus4.6 -> GPT-5.4` bridge 的高风险点在于：
  - 会稳定地产生多个 `Agent`
  - 一旦客户端默认采用 worktree 隔离，就更容易踩到本地仓库锁冲突

## 下一步建议

在不改业务功能的前提下，优先对 bridge 做一版最小变更：

- 串行化工具调用
- 增强调试日志
- 对高风险工具请求做桥接降级

待用户再次进行 Claude Code 测试后，继续结合实时日志判断优化是否生效。
