# Claude Code Opus Bridge Hardening Plan

## 用户原始需求

用户反馈当前渠道 `43.156.153.12-codex转claude` 上暴露的模型 `claude-opus-4.6` 实际是 `gpt-5.4` 通过 Responses 协议转 Anthropic Messages 协议提供给 Claude Code 使用，但在 Claude Code 中适配性不好，表现为：

- 深度分析项目时文件读取、编辑等工具能力不稳定
- 会出现 `Sibling tool call errored`
- 会出现 `Failed to create worktree: could not lock config file .git/config: File exists`
- 与同环境下正常可用的原生 Claude 渠道 `43.156.153.12-kiro` / `claude-sonnet-4.5` 体验存在明显差异

用户要求：

- 深度分析当前项目与桥接实现
- 通过本地数据库获取可用 API Key，自行联调
- 使用本机 `claude` CLI 分别测试桥接模型和原生 Claude 模型
- 读取 Claude Code 本地聊天记录、后端日志等数据做差异分析
- 修复桥接实现，确保 `codex转opus` 渠道可在 Claude Code 中稳定使用

## 当前已确认现状

### 项目结构

- Anthropic 入口在 `backend/app/api/proxy/anthropic_proxy.py`
- 代理核心在 `backend/app/services/proxy_service.py`
- `claude-opus-4-6 -> 43.156.153.12-codex转claude -> responses:gpt-5.4` 的映射由 SQL 脚本维护
- 已有桥接自测脚本 `backend/test_anthropic_responses_bridge.py`

### 本地 Claude 会话取证结论

- 本机 Claude Code 会话日志位于 `~/.claude/projects/-Volumes-project-modelInvocationSystem/*.jsonl`
- `claude-sonnet-4-5` 在某些会话中也出现过 `Sibling tool call errored`
- `claude-opus-4-6` 会明显更积极地触发 `TaskCreate`、`TaskUpdate`、`Agent` 等高风险工具
- `Failed to create worktree: could not lock config file .git/config: File exists` 是 Claude Code 在创建 worktree 过程中失败，不是单纯的 HTTP 400/500

### 代码层已发现的可疑点

1. `Anthropic -> Responses` 桥接在 `_convert_anthropic_request_to_responses()` 中只做了基础转换和高风险工具并发缓解，但未统一走 `_prepare_responses_request_body()` 的完整标准化流程
2. 高风险工具的并发缓解目前依赖 `_RESPONSES_HIGH_RISK_TOOL_NAMES` 黑名单，范围可能不够，无法完整约束 Claude Code 的复杂工具编排
3. `claude-opus-4-6` 这个 alias 会额外强制 `reasoning.effort=high`，可能增强了模型主动规划、任务拆分、子代理/工作树使用倾向
4. 当前缺少针对 Claude Code 工具场景的专项回归测试，现有桥接脚本只覆盖文本、单工具、图片三类基础场景

## 问题假设

### 假设 1：桥接层没有完整表达 Claude Code 期望的工具调用约束

可能表现为：

- 一次 assistant turn 输出多个高风险工具调用
- `parallel_tool_calls`、工具选择或事件顺序不符合 Claude Code 预期
- Responses 事件转 Anthropic SSE 时，`tool_use` / `input_json_delta` / `message_delta.stop_reason` 的组合不稳定

### 假设 2：桥接 alias 的行为策略导致比原生 Claude 更激进的任务编排

可能表现为：

- 更容易创建 Task / Agent / Worktree
- 遇到项目分析类请求时优先走多任务/子代理，而不是先做本地 Read/Bash
- 导致 `.git/config.lock` 冲突概率高于原生 Claude

### 假设 3：问题不全在协议层，部分来自 Claude Code 本地执行器

可能表现为：

- 原生 Claude 在并发工具调用时同样会出现 `Sibling tool call errored`
- worktree 失败来自本地 `.git/config.lock` 竞争，而非网关桥接
- 需要区分“本地工具执行器缺陷”和“桥接模型更容易触发该缺陷”

## 技术方案

### 方案目标

让 `claude-opus-4-6` 经过桥接后，在 Claude Code 中尽可能 1:1 接近原生 Claude 渠道的行为，重点保障：

- 文件读取稳定
- 文件编辑稳定
- Bash/Glob/Read/Write/Edit/MultiEdit/Task/Agent/Worktree 等工具能力不被削弱
- 桥接层正确表达 Claude Code 期望的工具 schema、tool_choice、多轮 tool_use/tool_result 往返语义
- 不通过“黑名单禁用工具”来换取稳定性

### 方案主体

1. 建立桥接专项联调基线
   - 对比 `claude-opus-4-6` 与 `claude-sonnet-4.5` 在同一 prompt 下的聊天记录
   - 抽取每轮工具调用数量、工具类型、stop_reason、错误类型
   - 结合后端请求日志确认桥接请求体与返回事件差异

2. 强化 `Anthropic -> Responses` 请求标准化
   - 让桥接路径统一经过 `_prepare_responses_request_body()`
   - 对齐 `store`、输入规范化、tool schema、tool_choice、reasoning 参数等兼容处理
   - 检查 Claude Code 所需的 Anthropic request 字段是否被无损转换到 Responses 请求

3. 强化 `Responses -> Anthropic SSE` 的事件还原
   - 对齐 `message_start` / `content_block_start` / `content_block_delta` / `content_block_stop` / `message_delta` / `message_stop` 的顺序与字段
   - 对齐 `tool_use.id`、工具名、`input_json_delta`、最终 `stop_reason=tool_use`
   - 检查多轮工具往返时 `tool_use` / `tool_result` / call_id 映射是否稳定

4. 完善桥接回归测试
   - 新增多工具、高风险工具、工具续轮的 Anthropic bridge 测试
   - 断言 tool schema、tool_choice、SSE 事件顺序、stop_reason、call_id 映射
   - 验证回归后不会破坏已有 Anthropic 基础兼容

## 影响范围分析

### 主要修改模块

- `backend/app/services/proxy_service.py`
- `backend/app/test/*` 或新增桥接专项测试文件
- `backend/test_anthropic_responses_bridge.py`

### 联调依赖

- 本地 MySQL：获取用户 API Key、查看渠道/模型映射、必要时读请求日志
- 本地后端服务：`uvicorn app.main:app --host 0.0.0.0 --port 8085 --reload`
- 本机 `claude` CLI：复现实测桥接模型与原生模型行为差异
- 本地 Claude 会话日志：`~/.claude/projects/-Volumes-project-modelInvocationSystem/`

### 风险点

- 如果问题主要来自 Claude Code 本地 worktree 竞争，单纯改桥接无法彻底消除
- 若桥接层错误地“替 Claude Code 做决策”，会出现看似稳定但与原生 Claude 行为不一致的问题
- 修改事件流转换时，可能影响已有 Anthropic 客户端兼容性

## To-Do

1. 连接本地数据库，确认：
   - `43.156.153.12-codex转claude`
   - `43.156.153.12-Claude` / `43.156.153.12-kiro`
   - `claude-opus-4-6`、`claude-sonnet-4.5` 模型映射
   - 一个可用 API Key
2. 启动本地后端并开启足够日志
3. 用本机 `claude` CLI 分别测试桥接模型和原生模型，固定同一 prompt
4. 抽取 Claude Code 本地会话 JSONL 中的：
   - 模型
   - 工具序列
   - stop_reason
   - 错误类型
5. 读取后端请求日志/运行日志，定位桥接请求与事件流差异
6. 修改桥接实现，优先处理：
   - 请求标准化不一致
   - 工具 schema / tool_choice / tool_result 映射不一致
   - Anthropic SSE 工具事件还原不一致
7. 补充测试，覆盖多工具、多轮工具和 Anthropic SSE 工具事件
8. 重新联调 `claude-opus-4-6`
9. 生成 impl 文档
10. 执行 review，并根据 review 结果迭代

## 验证标准

- `claude-opus-4-6` 在 Claude Code 中能够稳定执行 `Read`、`Bash`、`Glob`、文件编辑相关工具
- 同类 prompt 下，桥接模型的工具调用形态与原生 Claude 更接近
- 不再因为桥接层的工具 schema 或事件流偏差引发异常
- 对于需要子代理/worktree 的场景，桥接模型行为不明显劣于原生 Claude
- 新增自动化测试通过，现有桥接基础测试不回归
